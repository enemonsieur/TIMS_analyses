# Create vertically-stacked plot_joint triptych for EXP06 pre-stim-post
# This uses the image-stacking approach: generate individual plot_joint figures,
# load them as images, pad to same width, and stack vertically.

from pathlib import Path
import warnings
import mne
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image
from scipy.optimize import curve_fit

import plot_helpers
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
ROI_CHANNELS = ["FC5", "FC1", "Pz", "CP5", "CP6"]

YLIM_UV = 4.0  # µV — shared y-axis range for all three conditions
DPI = 220

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

# Keep EEG only and drop the same known bad channels (if they exist)
raw_full.pick_types(eeg=True).drop_channels(BAD_CHANNELS, on_missing='ignore')

# Select ROI channels (matching EXP04)
raw_full.pick(ROI_CHANNELS)

# Extract stim trace before dropping aux channels
raw_temp = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)
stim_trace = raw_temp.copy().pick(["stim"]).get_data()[0]

print(f"Retained EEG channels: {len(raw_full.ch_names)}")

# ============================================================
# 2) DETECT STIMULATION PULSE ONSETS
# ============================================================
stim_pulse_onsets, _, _, _ = preprocessing.detect_stim_onsets(stim_trace, sfreq)
print(f"Detected stim pulses: {stim_pulse_onsets.size}")

# ============================================================
# 3) BUILD MATCHED PRE / STIM / POST EVENTS
# ============================================================
# For a single continuous file, all three event arrays come from the same recording.
events_pre, events_stim, events_post = preprocessing.build_matched_triplet_events(
    stim_pulse_onsets_samples=stim_pulse_onsets,
    pre_n_times=raw_full.n_times,
    stim_n_times=raw_full.n_times,
    post_n_times=raw_full.n_times,
    sampling_rate_hz=sfreq,
    epoch_tmin_s=-2.0,
    epoch_tmax_s=2.5,
)

# ============================================================
# 4) BUILD EPOCHS WITH THE SAME LONG WINDOW
# ============================================================
epochs_pre = mne.Epochs(raw_full, events_pre, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)
epochs_stim = mne.Epochs(raw_full, events_stim, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)
epochs_post = mne.Epochs(raw_full, events_post, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)

# ============================================================
# 5) APPLY THE SAME TEP PIPELINE TO ALL THREE CONDITIONS
# ============================================================
for epochs in (epochs_pre, epochs_stim, epochs_post):
    epochs.apply_baseline((-1.9, -1.3))
    epochs.crop(tmin=0.08, tmax=0.50)
    epochs.filter(l_freq=None, h_freq=42.0, verbose=False)

# ============================================================
# 6) REMOVE THE SLOW POST-PULSE DECAY WITH A PER-CHANNEL EXPONENTIAL FIT
# ============================================================
for epochs in (epochs_pre, epochs_stim, epochs_post):
    evoked_for_decay = epochs.average()
    time_seconds = evoked_for_decay.times
    fit_mask = time_seconds > 0.02

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
        epochs._data[:, channel_index, :] -= fitted_decay[np.newaxis, :]

# ============================================================
# 7) AVERAGE EACH CONDITION
# ============================================================
evoked_pre = epochs_pre.average()
evoked_stim = epochs_stim.average()
evoked_post = epochs_post.average()

# ============================================================
# 8) GENERATE THREE INDIVIDUAL PLOT_JOINT FIGURES
# ============================================================
labels = ["pre", "stim", "post"]
evokeds = [evoked_pre, evoked_stim, evoked_post]
titles = ["PRE", "STIM", "POST"]
joint_paths = []

for label, evoked, title in zip(labels, evokeds, titles):
    fig_j = evoked.plot_joint(
        times="peaks",
        title=f"{title}  (n={evoked.nave})",
        show=False,
        ts_args={"gfp": True, "ylim": {"eeg": [-YLIM_UV, YLIM_UV]}},
        topomap_args={"outlines": "head"},
    )
    p = OUTPUT_DIR / f"exp06_run02_tep_{label}_joint.png"
    fig_j.savefig(p, dpi=DPI, bbox_inches="tight")
    plt.close(fig_j)
    joint_paths.append(p)
    print(f"Saved joint plot -> {p}")

# ============================================================
# 9) LOAD IMAGES AND STACK VERTICALLY WITH PADDING
# ============================================================
# Load images as numpy arrays
imgs = [matplotlib.image.imread(str(p)) for p in joint_paths]
heights = [img.shape[0] for img in imgs]
max_width = max(img.shape[1] for img in imgs)

print(f"Image dimensions: {[(img.shape[0], img.shape[1]) for img in imgs]}")
print(f"Max width: {max_width}")

# Pad all images to same width to align cleanly
padded = []
for img_idx, img in enumerate(imgs):
    pad_w = max_width - img.shape[1]
    if pad_w > 0:
        # Determine padding value based on image dtype
        pad_val = 1.0 if img.dtype in (np.float32, np.float64) else 255
        pad = np.full((img.shape[0], pad_w, img.shape[2]), pad_val, dtype=img.dtype)
        img_padded = np.concatenate([img, pad], axis=1)
        print(f"  Padded image {img_idx}: added {pad_w} pixels (dtype {img.dtype}, pad_val {pad_val})")
    else:
        img_padded = img
        print(f"  Image {img_idx}: no padding needed")
    padded.append(img_padded)

# Vertically stack all padded images
combined = np.vstack(padded)
print(f"Combined image shape: {combined.shape}")

# ============================================================
# 10) SAVE STACKED IMAGE DIRECTLY WITHOUT MATPLOTLIB (memory-efficient)
# ============================================================
triptych_path = OUTPUT_DIR / "exp06_run02_tep_pre_stim_post_joint_triptych_vertical.png"

# Convert to uint8 if needed for PIL
if combined.dtype in (np.float32, np.float64):
    # Clip to [0, 1] and convert to uint8
    combined_uint8 = np.clip(combined * 255, 0, 255).astype(np.uint8)
else:
    combined_uint8 = combined

# Use PIL if available, otherwise use matplotlib with a reduced array
if HAS_PIL:
    # PIL can handle the large array much more efficiently
    if combined_uint8.shape[2] == 4:
        # RGBA
        img = Image.fromarray(combined_uint8, mode='RGBA')
    elif combined_uint8.shape[2] == 3:
        # RGB
        img = Image.fromarray(combined_uint8, mode='RGB')
    else:
        raise ValueError(f"Unexpected number of channels: {combined_uint8.shape[2]}")
    img.save(str(triptych_path), quality=95)
    print(f"Saved vertical joint triptych with PIL -> {triptych_path}")
else:
    # Fallback: use matplotlib but with reduced resolution
    print(f"Warning: PIL not available, using matplotlib (may fail for very large images)")
    fig_height_inches = combined.shape[0] / DPI
    fig_width_inches = combined.shape[1] / DPI
    fig_out = plt.figure(figsize=(fig_width_inches, fig_height_inches), dpi=DPI)
    ax_out = fig_out.add_subplot(111)
    ax_out.imshow(combined_uint8)
    ax_out.axis("off")
    fig_out.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig_out.savefig(triptych_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig_out)
    print(f"Saved vertical joint triptych with matplotlib -> {triptych_path}")

# ============================================================
# 11) SUMMARY
# ============================================================
print(f"\nSaved vertical joint triptych -> {triptych_path}")
print(f"Matched epochs per condition: {len(epochs_stim)}")
