"""What does the average EEG activity look like in ~500ms before vs after stimulation pulses?"""

from pathlib import Path

import mne
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

import matplotlib.image
import preprocessing

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ============================================================
# CONFIG
# ============================================================
INPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-stim-mod-50hz-pulse-run01.vhdr"

OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP04_TEP_analysis")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]

PULSE_ONSET_OFFSET_SAMPLES = 1008  # offset from block-start to actual pulse onset
EPOCH_TMIN_S = -2.0  # long window to contain both pre and post windows
EPOCH_TMAX_S = 2.5
BASELINE_WINDOW_S = (-1.9, -1.3)
CROP_TMIN_S = 0.08  # crop to TEP window after baseline
CROP_TMAX_S = 0.50
LOWPASS_FREQ_HZ = 42.0
DECAY_FIT_START_S = 0.02  # fit exponential decay on data after this time

PRE_WINDOW_S = (-1.0, -0.5)  # pre-pulse window
POST_WINDOW_S = (0.0, 0.5)   # post-pulse window

YLIM_UV = 6.0  # µV — shared y-axis range for joint plots


# ============================================================
# PIPELINE SKETCH
# ============================================================
# raw EEG (stim recording)
#   |
# detect pulse onsets (CP6 method)
#   |
# pulse-locked events
#   |
# long epochs (-2.0 to 2.5 s)
#   |
# TEP pipeline: baseline, crop, filter
#   |
# remove slow decay (per-channel exponential fit)
#   |
# average all pulses
#   |
# extract pre and post windows
#   |
# generate two joint plots


# ============================================================
# 1) LOAD STIMULATION RECORDING
# ============================================================
raw_stim = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)
raw_stim.pick_types(eeg=True).drop_channels(BAD_CHANNELS)

sfreq = float(raw_stim.info["sfreq"])
print(f"Loaded stim recording: {raw_stim.n_times / sfreq:.1f} s, sfreq={sfreq:.0f} Hz")
print(f"Retained channels: {len(raw_stim.ch_names)}")


# ============================================================
# 2) DETECT PULSE ONSETS FROM CP6
# ============================================================
# CP6 shows large first-derivative jumps at stimulation block starts.
cp6_data = raw_stim.copy().pick(["CP6"]).get_data()[0]
cp6_data = cp6_data - np.mean(cp6_data[:10000])  # demean on baseline

# Find block starts by first-derivative threshold.
candidate_onsets = np.where(np.abs(np.diff(cp6_data)) > 0.01)[0] + 1
if candidate_onsets.size == 0:
    raise ValueError("Pulse detection found no candidates.")

# Keep only the first jump in each block (blocks spaced > 1200 samples apart).
stim_block_onsets_samples = [int(candidate_onsets[0])]
for sample_index in candidate_onsets[1:]:
    if sample_index - stim_block_onsets_samples[-1] > 1200:
        stim_block_onsets_samples.append(int(sample_index))
stim_block_onsets_samples = np.asarray(stim_block_onsets_samples, dtype=int)

# Actual pulse is offset from block start.
stim_pulse_onsets_samples = stim_block_onsets_samples + PULSE_ONSET_OFFSET_SAMPLES
print(f"Detected stimulation pulses: {len(stim_pulse_onsets_samples)}")


# ============================================================
# 3) BUILD PULSE-LOCKED EVENTS
# ============================================================
# Create MNE event array from pulse sample indices.
# Only include complete epochs that fit within the recording.
valid_mask = (
    (stim_pulse_onsets_samples + int(EPOCH_TMIN_S * sfreq) >= 0) &
    (stim_pulse_onsets_samples + int(EPOCH_TMAX_S * sfreq) <= raw_stim.n_times)
)
valid_pulses = stim_pulse_onsets_samples[valid_mask]
events_stim = np.column_stack([valid_pulses, np.zeros_like(valid_pulses), np.ones_like(valid_pulses)])
print(f"Valid pulses (full epoch): {len(valid_pulses)}")


# ============================================================
# 4) CREATE LONG EPOCHS
# ============================================================
epochs_stim = mne.Epochs(
    raw_stim,
    events_stim,
    event_id=1,
    tmin=EPOCH_TMIN_S,
    tmax=EPOCH_TMAX_S,
    baseline=None,
    preload=True,
    verbose=False,
)
print(f"Retained epochs: {len(epochs_stim)}")


# ============================================================
# 5) APPLY TEP PIPELINE WITH TWO SEPARATE BRANCHES
# ============================================================
# Apply baseline to full epoch first (baseline is pre-stimulus clean window).
epochs_stim.apply_baseline(BASELINE_WINDOW_S)

# Create separate epoch objects for PRE and POST windows to avoid
# filtering artifacts across the full long epoch boundaries.
epochs_pre = epochs_stim.copy().crop(tmin=PRE_WINDOW_S[0], tmax=PRE_WINDOW_S[1])
epochs_post = epochs_stim.copy().crop(tmin=POST_WINDOW_S[0], tmax=POST_WINDOW_S[1])

# Filter each window independently.
epochs_pre.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)
epochs_post.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)


# ============================================================
# 6) REMOVE SLOW POST-PULSE DECAY (per-channel exponential fit)
# ============================================================
# Fit and remove decay from POST window only (PRE window has no post-pulse decay).
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
# 8) GENERATE INDIVIDUAL JOINT PLOTS
# ============================================================
# Generate PRE and POST as separate joint plots, then combine them side-by-side
labels = ["pre", "post"]
evokeds = [evoked_pre, evoked_post]
titles = ["PRE-PULSE", "POST-PULSE"]
joint_paths = []

for label, evoked, title in zip(labels, evokeds, titles):
    fig_j = evoked.plot_joint(
        times="peaks",
        title=f"{title}  (n={evoked.nave})",
        show=False,
        ts_args={"gfp": True, "ylim": {"eeg": [-YLIM_UV, YLIM_UV]}},
        topomap_args={"outlines": "head"},
    )
    # Disable constrained layout to avoid zero-size rendering issues
    fig_j.set_constrained_layout(False)

    output_path = OUTPUT_DIRECTORY / f"exp04_within_pulse_tep_{label}.png"
    fig_j.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close(fig_j)
    joint_paths.append(output_path)
    print(f"Saved -> {output_path}")

# ============================================================
# 9) LOAD JOINT PLOT IMAGES AND STACK VERTICALLY INTO TRIPTYCH
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

triptych_path = OUTPUT_DIRECTORY / "exp04_within_pulse_tep_joint_triptych.png"

if combined.dtype in (np.float32, np.float64):
    combined_uint8 = np.clip(combined * 255, 0, 255).astype(np.uint8)
else:
    combined_uint8 = combined

if HAS_PIL:
    mode = "RGBA" if combined_uint8.shape[2] == 4 else "RGB"
    Image.fromarray(combined_uint8, mode=mode).save(str(triptych_path))
    print(f"Saved triptych with PIL -> {triptych_path}")
else:
    fig_height_inches = combined.shape[0] / 100
    fig_width_inches = combined.shape[1] / 100
    fig_out = plt.figure(figsize=(fig_width_inches, fig_height_inches), dpi=100)
    ax_out = fig_out.add_subplot(111)
    ax_out.imshow(combined_uint8)
    ax_out.axis("off")
    fig_out.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig_out.savefig(triptych_path, dpi=100, bbox_inches="tight")
    plt.close(fig_out)
    print(f"Saved triptych with matplotlib -> {triptych_path}")


# ============================================================
# 9) SUMMARY
# ============================================================
print(f"\nSummary:")
print(f"  Detected pulses: {len(stim_pulse_onsets_samples)}")
print(f"  Valid pulses: {len(valid_pulses)}")
print(f"  Retained epochs: {len(epochs_stim)}")
print(f"  Channels: {len(evoked_pre.ch_names)}")
print(f"  Pre-window: {PRE_WINDOW_S} s")
print(f"  Post-window: {POST_WINDOW_S} s")
