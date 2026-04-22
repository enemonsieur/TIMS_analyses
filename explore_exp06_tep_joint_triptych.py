# Pre-pulse vs post-pulse TEP comparison for EXP06 run02 (within-pulse approach).
# Uses a single stim file: epochs are split into a pre-pulse control window and a
# post-pulse TEP window. Outputs two plot_joint figures stacked vertically.

from pathlib import Path
import warnings

import mne
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image
from scipy.optimize import curve_fit

import preprocessing

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ============================================================
# CONFIG
# ============================================================
DATA_DIR = Path(r"c:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
VHDR_PATH = DATA_DIR / "exp06-STIM-iTBS_run02.vhdr"
OUTPUT_DIR = Path(r"c:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]

EPOCH_TMIN_S = -2.0
EPOCH_TMAX_S = 2.5
BASELINE_WINDOW_S = (-2.0, -1.85)  # clean reference window kept separate from the displayed PRE panel
PRE_WINDOW_S = (-1.8, -1.3)   # true pre-pulse control window
POST_WINDOW_S = (0.0, 0.5)    # TEP window
LOWPASS_FREQ_HZ = 42.0
DECAY_FIT_START_S = 0.02
YLIM_UV = 4.0
DPI = 220
PLOT_FIGSIZE_IN = (10.0, 6.0)
MAX_EXPORT_HEIGHT_PX = 5000
MAX_EXPORT_WIDTH_PX = 5000
PRE_TOPO_TIMES_S = [-1.75, -1.60, -1.45]
POST_TOPO_TIMES_S = [0.03, 0.10, 0.20]


# ============================================================
# 1) LOAD THE RUN02 RECORDING
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information*")
    warnings.filterwarnings("ignore", message="Online software filter*")
    warnings.filterwarnings("ignore", message="Not setting positions*")
    raw_full = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_full.ch_names or "ground_truth" not in raw_full.ch_names:
    raise RuntimeError("Missing required stim and/or ground_truth channels.")

sfreq = float(raw_full.info["sfreq"])

# Extract stim trace before dropping auxiliary channels.
with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    raw_temp = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)
stim_trace = raw_temp.copy().pick(["stim"]).get_data()[0]
del raw_temp

raw_full.pick_types(eeg=True).drop_channels(BAD_CHANNELS, on_missing="ignore")

print(f"Retained EEG channels: {raw_full.ch_names}")


# ============================================================
# 2) DETECT STIMULATION PULSE ONSETS
# ============================================================
stim_pulse_onsets, _, _, _ = preprocessing.detect_stim_onsets(stim_trace, sfreq)
print(f"Detected stim pulses: {stim_pulse_onsets.size}")


# ============================================================
# 3) BUILD PULSE-LOCKED EVENTS
# ============================================================
valid_mask = (
    (stim_pulse_onsets + int(EPOCH_TMIN_S * sfreq) >= 0) &
    (stim_pulse_onsets + int(EPOCH_TMAX_S * sfreq) <= raw_full.n_times)
)
valid_pulses = stim_pulse_onsets[valid_mask]
events = np.column_stack([valid_pulses, np.zeros_like(valid_pulses), np.ones_like(valid_pulses)])
print(f"Valid pulses (full epoch fits): {len(valid_pulses)}")


# ============================================================
# 4) CREATE LONG EPOCHS
# ============================================================
epochs_long = mne.Epochs(
    raw_full,
    events,
    event_id=1,
    tmin=EPOCH_TMIN_S,
    tmax=EPOCH_TMAX_S,
    baseline=None,
    preload=True,
    verbose=False,
)
print(f"Retained epochs: {len(epochs_long)}")


# ============================================================
# 5) TEP PIPELINE — TWO BRANCHES FROM THE SAME LONG EPOCHS
# ============================================================
# Apply baseline on the full long epoch (baseline is a clean pre-stimulus window).
epochs_long.apply_baseline(BASELINE_WINDOW_S)

# Crop to pre-pulse and post-pulse windows independently.
epochs_pre = epochs_long.copy().crop(tmin=PRE_WINDOW_S[0], tmax=PRE_WINDOW_S[1])
epochs_post = epochs_long.copy().crop(tmin=POST_WINDOW_S[0], tmax=POST_WINDOW_S[1])

# Filter each window independently to avoid edge artifacts.
epochs_pre.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)
epochs_post.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)


# ============================================================
# 6) REMOVE SLOW POST-PULSE DECAY (POST WINDOW ONLY)
# ============================================================
evoked_for_decay = epochs_post.average()
time_seconds = evoked_for_decay.times
fit_mask = time_seconds > DECAY_FIT_START_S

for channel_index in range(len(evoked_for_decay.ch_names)):
    channel_trace = evoked_for_decay.data[channel_index]
    fit_parameters, _ = curve_fit(
        lambda t, amplitude, tau, offset: amplitude * np.exp(-t / tau) + offset,
        time_seconds[fit_mask],
        channel_trace[fit_mask],
        maxfev=10000,
    )
    fitted_decay = (
        fit_parameters[0] * np.exp(-time_seconds / fit_parameters[1]) + fit_parameters[2]
    )
    epochs_post._data[:, channel_index, :] -= fitted_decay[np.newaxis, :]


# ============================================================
# 7) AVERAGE PRE AND POST WINDOWS
# ============================================================
evoked_pre = epochs_pre.average()
evoked_post = epochs_post.average()


# ============================================================
# 8) GENERATE TWO INDIVIDUAL PLOT_JOINT FIGURES
# ============================================================
labels = ["pre", "post"]
evokeds = [evoked_pre, evoked_post]
titles = ["PRE-PULSE", "POST-PULSE"]
topomap_times = [PRE_TOPO_TIMES_S, POST_TOPO_TIMES_S]
joint_paths = []

for label, evoked, title, times_s in zip(labels, evokeds, titles, topomap_times):
    fig_j = evoked.plot_joint(
        times=times_s,
        title=f"{title}  (n={evoked.nave})",
        show=False,
        ts_args={"gfp": True, "ylim": {"eeg": [-YLIM_UV, YLIM_UV]}},
        topomap_args={"outlines": "head"},
    )
    fig_j.set_size_inches(*PLOT_FIGSIZE_IN, forward=True)
    output_path = OUTPUT_DIR / f"exp06_run02_tep_{label}_joint.png"
    fig_j.savefig(output_path, dpi=DPI)
    plt.close(fig_j)

    if not HAS_PIL:
        raise RuntimeError("PIL is required for export-size validation.")

    with Image.open(output_path) as saved_image:
        saved_width_px, saved_height_px = saved_image.size

    print(f"{label.upper()} joint size: {saved_width_px} x {saved_height_px}")
    if saved_width_px > MAX_EXPORT_WIDTH_PX or saved_height_px > MAX_EXPORT_HEIGHT_PX:
        raise RuntimeError(
            f"{label} joint export is pathological: "
            f"{saved_width_px} x {saved_height_px} px."
        )

    joint_paths.append(output_path)
    print(f"Saved joint plot -> {output_path}")


# ============================================================
# 9) LOAD IMAGES AND STACK VERTICALLY WITH PADDING
# ============================================================
imgs = [matplotlib.image.imread(str(p)) for p in joint_paths]
max_width = max(img.shape[1] for img in imgs)

padded = []
for img in imgs:
    pad_w = max_width - img.shape[1]
    if pad_w > 0:
        pad_val = 1.0 if img.dtype in (np.float32, np.float64) else 255
        pad = np.full((img.shape[0], pad_w, img.shape[2]), pad_val, dtype=img.dtype)
        padded.append(np.concatenate([img, pad], axis=1))
    else:
        padded.append(img)

combined = np.vstack(padded)
print(f"Combined image shape: {combined.shape}")


# ============================================================
# 10) SAVE STACKED TRIPTYCH
# ============================================================
triptych_path = OUTPUT_DIR / "exp06_run02_tep_joint_triptych.png"

if combined.dtype in (np.float32, np.float64):
    combined_uint8 = np.clip(combined * 255, 0, 255).astype(np.uint8)
else:
    combined_uint8 = combined

if HAS_PIL:
    mode = "RGBA" if combined_uint8.shape[2] == 4 else "RGB"
    Image.fromarray(combined_uint8, mode=mode).save(str(triptych_path))
    print(f"Saved triptych with PIL -> {triptych_path}")
else:
    fig_height_inches = combined.shape[0] / DPI
    fig_width_inches = combined.shape[1] / DPI
    fig_out = plt.figure(figsize=(fig_width_inches, fig_height_inches), dpi=DPI)
    ax_out = fig_out.add_subplot(111)
    ax_out.imshow(combined_uint8)
    ax_out.axis("off")
    fig_out.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig_out.savefig(triptych_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig_out)
    print(f"Saved triptych with matplotlib -> {triptych_path}")


# ============================================================
# 11) SUMMARY
# ============================================================
print(f"\nDetected pulses: {stim_pulse_onsets.size}")
print(f"Valid pulses:    {len(valid_pulses)}")
print(f"Retained epochs: {len(epochs_long)}")
print(f"Channels: {evoked_pre.ch_names}")
print(f"Pre-window:  {PRE_WINDOW_S} s")
print(f"Post-window: {POST_WINDOW_S} s")
