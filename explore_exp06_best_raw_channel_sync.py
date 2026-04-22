"""Exploratory: Best raw channels (ITPC ≈ 100%) time course overlay with GT.

Identifies the single top-performing raw EEG channel per intensity block
based on GT-locked ITPC during the ON window, then visualizes the bandpass-
filtered time course alongside the GT trace to qualitatively confirm phase sync.
"""

from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import hilbert
import mne

import preprocessing

# ============================================================
# CONFIG
# ============================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES_PER_INTENSITY = 20
ON_WINDOW_S = (0.3, 1.5)
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}

TARGET_CENTER_HZ = 12.451172
SIGNAL_HALF_WIDTH_HZ = 0.5
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
RUN02_STIM_THRESHOLD_FRACTION = 0.08

INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]

OUTPUT_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_best_channel_sync_overlay.png"
OUTPUT_TABLE_PATH = OUTPUT_DIRECTORY / "exp06_run02_best_channel_summary.txt"


# ============================================================
# 1) LOAD DATA
# ============================================================
print("Loading run02 recording...")
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw_stim_full.info["sfreq"])
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]
gt_trace = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]

raw_eeg = raw_stim_full.copy().drop_channels(
    [ch for ch in raw_stim_full.ch_names
     if ch.lower() in {"stim", "ground_truth"} or ch.startswith("STI") or ch in EXCLUDED_CHANNELS]
)
print(f"Loaded: {len(raw_eeg.ch_names)} EEG channels, sfreq={sfreq:.0f} Hz")
print(f"Channels: {raw_eeg.ch_names}\n")

# ============================================================
# 2) DETECT STIMULUS TIMING
# ============================================================
print("Detecting stimulus blocks...")
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION
)

n_blocks = len(block_onsets_samples)
print(f"Detected {n_blocks} blocks (expected 5 intensities × 20 cycles = 100)")

on_window_start_shift = int(round(ON_WINDOW_S[0] * sfreq))
on_window_end_shift = int(round(ON_WINDOW_S[1] * sfreq))
on_window_samples = on_window_end_shift - on_window_start_shift

# ============================================================
# 3) EXTRACT ON-WINDOW CYCLES AND COMPUTE PLV PER CHANNEL
# ============================================================
print(f"\nComputing PLV (Phase Locking Value) for each channel in ON window ({ON_WINDOW_S[0]}–{ON_WINDOW_S[1]} s)...")
print("  (12.45 Hz bandpass -> Hilbert phase -> mean phase coherence across cycles)")

# Map blocks to intensity indices: 0–19 → 10%, 20–39 → 20%, etc.
blocks_per_intensity = BLOCK_CYCLES_PER_INTENSITY
intensity_indices = np.repeat(np.arange(5), blocks_per_intensity)  # [0,0,...,0,1,1,...,1,...]

# Store results: {intensity_idx → {channel_name → list of mean PLV values per epoch}}
plv_by_intensity_channel = {i: {} for i in range(5)}

eeg_data = raw_eeg.get_data()  # shape: (n_channels, n_samples)
gt_data = gt_trace  # shape: (n_samples,)

for block_idx in range(n_blocks):
    intensity_idx = intensity_indices[block_idx]
    onset_sample = block_onsets_samples[block_idx]
    offset_sample = block_offsets_samples[block_idx]

    # ON window: onset_sample + on_window_start_shift to onset_sample + on_window_end_shift
    on_start = onset_sample + on_window_start_shift
    on_end = onset_sample + on_window_end_shift

    if on_end > eeg_data.shape[1]:
        print(f"    Block {block_idx} ON window extends beyond recording; skipping.")
        continue

    # Extract ON-window traces for this block
    on_eeg = eeg_data[:, on_start:on_end]  # shape: (n_channels, on_window_samples)
    on_gt = gt_data[on_start:on_end]  # shape: (on_window_samples,)

    # Bandpass filter to isolate 12.45 Hz target before computing phase
    on_eeg_filt = preprocessing.filter_signal(
        on_eeg, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )
    on_gt_filt = preprocessing.filter_signal(
        on_gt, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )

    # Compute phase via Hilbert transform
    on_eeg_phase = np.angle(hilbert(on_eeg_filt, axis=-1))  # shape: (n_channels, on_window_samples)
    on_gt_phase = np.angle(hilbert(on_gt_filt, axis=-1))    # shape: (on_window_samples,)

    # PLV: mean of exp(i * phase_diff) across time (axis=-1 for this single epoch)
    phase_diff = on_eeg_phase - on_gt_phase[np.newaxis, :]  # shape: (n_channels, on_window_samples)
    plv_per_channel = np.abs(np.mean(np.exp(1j * phase_diff), axis=-1))  # shape: (n_channels,)

    # Store in dictionary keyed by channel name
    for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
        if ch_name not in plv_by_intensity_channel[intensity_idx]:
            plv_by_intensity_channel[intensity_idx][ch_name] = []
        plv_by_intensity_channel[intensity_idx][ch_name].append(plv_per_channel[ch_idx])

# Compute mean PLV per channel per intensity
print("\nMean PLV per channel per intensity (averaged across cycles):")
best_channels = {}
FIXED_CHANNEL = None  # Will be set at 10% and locked for all intensities

for intensity_idx in range(5):
    intensity_label = RUN02_INTENSITY_LABELS[intensity_idx]
    print(f"\n{intensity_label}:")

    channel_mean_plv = {}
    for ch_name in raw_eeg.ch_names:
        if ch_name in plv_by_intensity_channel[intensity_idx] and plv_by_intensity_channel[intensity_idx][ch_name]:
            mean_plv = np.mean(plv_by_intensity_channel[intensity_idx][ch_name])
            channel_mean_plv[ch_name] = mean_plv
            print(f"  {ch_name:6s}: {mean_plv:.4f}")

    # Pick the top channel at 10%, then lock it for all other intensities
    if intensity_idx == 0:  # 10% intensity
        if channel_mean_plv:
            best_ch = max(channel_mean_plv, key=channel_mean_plv.get)
            best_plv = channel_mean_plv[best_ch]
            FIXED_CHANNEL = best_ch
            best_channels[intensity_idx] = (best_ch, best_plv)
            print(f"  > Best (LOCKED): {best_ch} (PLV = {best_plv:.4f})")
        else:
            print(f"  > No channels available for {intensity_label}")
    else:  # 20–50%, use fixed channel
        if FIXED_CHANNEL and FIXED_CHANNEL in channel_mean_plv:
            best_plv = channel_mean_plv[FIXED_CHANNEL]
            best_channels[intensity_idx] = (FIXED_CHANNEL, best_plv)
            print(f"  > Fixed: {FIXED_CHANNEL} (PLV = {best_plv:.4f})")
        else:
            print(f"  > Fixed channel not available at {intensity_label}")

# ============================================================
# 4) EXTRACT FILTERED TIME COURSES FOR BEST CHANNELS
# ============================================================
print("\nExtracting filtered time courses for best channels...")

# For each intensity, collect all ON-window cycles of the best channel + GT
best_channel_cycles = {i: [] for i in range(5)}
best_gt_cycles = {i: [] for i in range(5)}

for block_idx in range(n_blocks):
    intensity_idx = intensity_indices[block_idx]
    onset_sample = block_onsets_samples[block_idx]

    on_start = onset_sample + on_window_start_shift
    on_end = onset_sample + on_window_end_shift

    if on_end > eeg_data.shape[1]:
        continue

    if intensity_idx not in best_channels:
        continue

    best_ch, _ = best_channels[intensity_idx]
    ch_idx = raw_eeg.ch_names.index(best_ch)

    # Extract raw ON window
    on_eeg_raw = eeg_data[ch_idx, on_start:on_end]
    on_gt_raw = gt_data[on_start:on_end]

    # Bandpass filter to isolate target (11.95–12.95 Hz around 12.45 Hz)
    on_eeg_filt = preprocessing.filter_signal(
        on_eeg_raw, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )
    on_gt_filt = preprocessing.filter_signal(
        on_gt_raw, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )

    best_channel_cycles[intensity_idx].append(on_eeg_filt)
    best_gt_cycles[intensity_idx].append(on_gt_filt)

# Concatenate all cycles for each intensity
best_channel_timecourses = {}
best_gt_timecourses = {}
for intensity_idx in range(5):
    if best_channel_cycles[intensity_idx]:
        best_channel_timecourses[intensity_idx] = np.concatenate(best_channel_cycles[intensity_idx])
        best_gt_timecourses[intensity_idx] = np.concatenate(best_gt_cycles[intensity_idx])
    else:
        best_channel_timecourses[intensity_idx] = None
        best_gt_timecourses[intensity_idx] = None

# ============================================================
# 5) PLOT OVERLAY (5 panels, one per intensity)
# ============================================================
print("\nCreating multi-panel overlay figure...")

fig, axes = plt.subplots(5, 1, figsize=(14, 12))
fig.suptitle("Best Raw Channels (Top ITPC) vs GT Time Course — ON Window (0.3–1.5 s post-onset)",
             fontsize=14, fontweight="bold")

for intensity_idx in range(5):
    ax = axes[intensity_idx]
    intensity_label = RUN02_INTENSITY_LABELS[intensity_idx]
    color = INTENSITY_COLORS[intensity_idx]

    if intensity_idx not in best_channels or best_channel_timecourses[intensity_idx] is None:
        ax.text(0.5, 0.5, f"No data for {intensity_label}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="red")
        ax.set_title(f"{intensity_label}: No data")
        continue

    best_ch, best_itpc = best_channels[intensity_idx]
    ch_timecourse = best_channel_timecourses[intensity_idx]
    gt_timecourse = best_gt_timecourses[intensity_idx]

    # Time axis in seconds (one ON window = 1.2 s, repeated 20 times = 24 s total)
    time_axis_s = np.arange(len(ch_timecourse)) / sfreq

    # Plot GT (reference, black, thicker)
    ax.plot(time_axis_s, gt_timecourse, "k-", linewidth=2.0, label="GT (reference)", zorder=3)

    # Plot best channel (color-coded by intensity)
    ax.plot(time_axis_s, ch_timecourse, color=color, linewidth=1.5, label=f"{best_ch} (ITPC={best_itpc:.4f})", zorder=2)

    ax.set_title(f"{intensity_label}: {best_ch} vs GT", fontsize=11, fontweight="bold")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (µV)")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_FIGURE_PATH, dpi=150, bbox_inches="tight")
print(f"Saved figure: {OUTPUT_FIGURE_PATH}")
plt.close()

# ============================================================
# 6) EXPORT SUMMARY TABLE
# ============================================================
print("\nExporting summary table...")

summary_lines = [
    "BEST RAW CHANNELS (ITPC ~ 100%) -- EXP06 RUN02 ON-WINDOW SYNC CHECK",
    "=" * 80,
    f"Target frequency: {TARGET_CENTER_HZ:.3f} Hz (band: {SIGNAL_BAND_HZ[0]:.2f}–{SIGNAL_BAND_HZ[1]:.2f} Hz)",
    f"ON window: {ON_WINDOW_S[0]}–{ON_WINDOW_S[1]} s post-onset",
    f"Per-intensity cycles: {BLOCK_CYCLES_PER_INTENSITY}",
    "",
    "Intensity | Best Channel | Mean PLV  | Qualitative Sync Check",
    "-" * 80,
]

for intensity_idx in range(5):
    intensity_label = RUN02_INTENSITY_LABELS[intensity_idx]
    if intensity_idx in best_channels:
        best_ch, best_itpc = best_channels[intensity_idx]
        summary_lines.append(f"{intensity_label:10s} | {best_ch:12s} | {best_itpc:.4f}   | See plot panel")
    else:
        summary_lines.append(f"{intensity_label:10s} | {'N/A':12s} | N/A       | No data")

summary_lines.extend([
    "",
    "INTERPRETATION:",
    "- High ITPC (>0.95) indicates phase-locked recovery in best raw channel.",
    "- Overlay plot shows whether GT and best channel oscillations align visually.",
    "- Expected: 10–30% show clean sync; 40–50% may show phase drift or artifact artifact.",
    "",
])

summary_text = "\n".join(summary_lines)
with open(OUTPUT_TABLE_PATH, "w") as f:
    f.write(summary_text)

print(summary_text)
print(f"Saved summary: {OUTPUT_TABLE_PATH}")

print("\nDone!")
