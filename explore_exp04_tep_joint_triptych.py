"""Compare true pre-pulse and post-pulse TEP responses within the EXP04 stim run."""

from pathlib import Path

import matplotlib.image
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.optimize import curve_fit

try:
    from PIL import Image
except ImportError as exc:
    raise RuntimeError("PIL is required for export-size validation and final image saving.") from exc


# ============================================================
# CONFIG
# ============================================================
INPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-stim-mod-50hz-pulse-run01.vhdr"

OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP04_TEP_analysis")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]

PULSE_ONSET_OFFSET_SAMPLES = 1008  # offset from CP6 block-start to actual pulse onset
EPOCH_TMIN_S = -2.0  # long pulse-locked window
EPOCH_TMAX_S = 2.5
BASELINE_WINDOW_S = (-2.0, -1.85)  # clean reference window kept separate from displayed PRE data
PRE_WINDOW_S = (-1.8, -1.3)  # true pre-pulse control interval
POST_WINDOW_S = (0.0, 0.5)  # TEP interval
LOWPASS_FREQ_HZ = 42.0
DECAY_FIT_START_S = 0.02
YLIM_UV = 6.0
DPI = 220

PLOT_FIGSIZE_IN = (10.0, 6.0)
MAX_EXPORT_WIDTH_PX = 5000
MAX_EXPORT_HEIGHT_PX = 5000
PRE_TOPO_TIMES_S = [-1.75, -1.60, -1.45]
POST_TOPO_TIMES_S = [0.03, 0.10, 0.20]


# ============================================================
# 1) LOAD THE EXP04 STIM RECORDING
# ============================================================
raw_stim = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)
raw_stim.pick_types(eeg=True).drop_channels(BAD_CHANNELS, on_missing="ignore")

sfreq = float(raw_stim.info["sfreq"])
print(f"Loaded EXP04 stim run: {raw_stim.n_times / sfreq:.1f} s, sfreq={sfreq:.0f} Hz")
print(f"Retained EEG channels: {raw_stim.ch_names}")


# ============================================================
# 2) DETECT PULSE ONSETS FROM CP6 WITHIN THE STIM RUN
# ============================================================
# CP6 shows the repeated stimulation-block transitions in this recording.
cp6_data = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False).pick(["CP6"]).get_data()[0]
cp6_data = cp6_data - np.mean(cp6_data[:10000])

candidate_onsets = np.where(np.abs(np.diff(cp6_data)) > 0.01)[0] + 1
if candidate_onsets.size == 0:
    raise ValueError("CP6-based onset detection found no candidates.")

stim_block_onsets_samples = [int(candidate_onsets[0])]
for sample_index in candidate_onsets[1:]:
    if sample_index - stim_block_onsets_samples[-1] > 1200:
        stim_block_onsets_samples.append(int(sample_index))
stim_block_onsets_samples = np.asarray(stim_block_onsets_samples, dtype=int)

stim_pulse_onsets_samples = stim_block_onsets_samples + PULSE_ONSET_OFFSET_SAMPLES
print(f"Detected stim pulses: {stim_pulse_onsets_samples.size}")


# ============================================================
# 3) BUILD VALID PULSE-LOCKED EVENTS
# ============================================================
valid_mask = (
    (stim_pulse_onsets_samples + int(EPOCH_TMIN_S * sfreq) >= 0)
    & (stim_pulse_onsets_samples + int(EPOCH_TMAX_S * sfreq) <= raw_stim.n_times)
)
valid_pulses = stim_pulse_onsets_samples[valid_mask]
events = np.column_stack([valid_pulses, np.zeros_like(valid_pulses), np.ones_like(valid_pulses)])
print(f"Valid pulses (full epoch fits): {len(valid_pulses)}")


# ============================================================
# 4) CREATE LONG PULSE-LOCKED EPOCHS
# ============================================================
epochs_long = mne.Epochs(
    raw_stim,
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
# 5) APPLY THE PRE/POST TEP PIPELINE
# ============================================================
# Baseline is applied before splitting so PRE and POST share the same reference.
epochs_long.apply_baseline(BASELINE_WINDOW_S)

epochs_pre = epochs_long.copy().crop(tmin=PRE_WINDOW_S[0], tmax=PRE_WINDOW_S[1])
epochs_post = epochs_long.copy().crop(tmin=POST_WINDOW_S[0], tmax=POST_WINDOW_S[1])

epochs_pre.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)
epochs_post.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)


# ============================================================
# 6) REMOVE SLOW POST-PULSE DECAY
# ============================================================
# Fit the slow artifact tail on the averaged POST branch, then subtract it from each epoch.
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
# 8) SAVE GUARDED PRE AND POST JOINT FIGURES
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

    output_path = OUTPUT_DIRECTORY / f"exp04_tep_{label}_joint.png"
    fig_j.savefig(output_path, dpi=DPI)
    plt.close(fig_j)

    with Image.open(output_path) as saved_image:
        saved_width_px, saved_height_px = saved_image.size

    print(f"{label.upper()} joint size: {saved_width_px} x {saved_height_px}")
    if saved_width_px > MAX_EXPORT_WIDTH_PX or saved_height_px > MAX_EXPORT_HEIGHT_PX:
        raise RuntimeError(
            f"{label} joint export is pathological: {saved_width_px} x {saved_height_px} px."
        )

    joint_paths.append(output_path)
    print(f"Saved joint plot -> {output_path}")


# ============================================================
# 9) LOAD, PAD, AND STACK THE TWO PANELS
# ============================================================
imgs = [matplotlib.image.imread(str(path)) for path in joint_paths]
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
# 10) SAVE FINAL COMBINED PNG
# ============================================================
triptych_path = OUTPUT_DIRECTORY / "exp04_tep_joint_triptych.png"

if combined.dtype in (np.float32, np.float64):
    combined_uint8 = np.clip(combined * 255, 0, 255).astype(np.uint8)
else:
    combined_uint8 = combined

mode = "RGBA" if combined_uint8.shape[2] == 4 else "RGB"
Image.fromarray(combined_uint8, mode=mode).save(str(triptych_path))
print(f"Saved triptych -> {triptych_path}")


# ============================================================
# 11) SUMMARY
# ============================================================
print(f"Detected pulses: {stim_pulse_onsets_samples.size}")
print(f"Valid pulses:    {len(valid_pulses)}")
print(f"Retained epochs: {len(epochs_long)}")
print(f"Pre-window:  {PRE_WINDOW_S} s")
print(f"Post-window: {POST_WINDOW_S} s")
