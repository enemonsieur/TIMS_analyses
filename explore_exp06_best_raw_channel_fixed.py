"""Find best raw EEG channel at 10% intensity (by PLV to GT) and lock it for all intensities.

This script identifies the single top-performing raw EEG channel at 10% based on
PLV (Phase Locking Value) to the ground-truth signal, then computes how that
fixed channel's PLV degrades across intensities (20%, 30%, 40%, 50%).

Output: metadata JSON + summary table + 5-panel overlay figure.
"""

from pathlib import Path
import warnings
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
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
VIEW_BAND_HZ = (4.0, 20.0)
RUN02_STIM_THRESHOLD_FRACTION = 0.08

INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]

METADATA_PATH = OUTPUT_DIRECTORY / "exp06_run02_fixed_raw_channel_metadata.json"
SUMMARY_TABLE_PATH = OUTPUT_DIRECTORY / "exp06_run02_fixed_raw_channel_summary.txt"
OVERLAY_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_fixed_raw_channel_overlay.png"


# ============================================================
# 1) LOAD DATA
# ============================================================
print("Loading run02 recording...")
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_stim_full.ch_names or "ground_truth" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channels: stim and ground_truth.")

sfreq = float(raw_stim_full.info["sfreq"])
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]
gt_trace = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]

raw_eeg = raw_stim_full.copy().drop_channels(
    [ch for ch in raw_stim_full.ch_names
     if ch.lower() in {"stim", "ground_truth"} or ch.startswith("STI") or ch in EXCLUDED_CHANNELS]
)
raw_data_2d = raw_eeg.get_data()

print(f"Loaded: {len(raw_eeg.ch_names)} EEG channels, sfreq={sfreq:.0f} Hz")
print(f"Channels: {raw_eeg.ch_names}\n")


# ============================================================
# 2) DETECT STIMULUS BLOCKS AND BUILD WINDOW PARAMS
# ============================================================
print("Detecting stimulus blocks...")
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION
)

on_window_size = int(round((ON_WINDOW_S[1] - ON_WINDOW_S[0]) * sfreq))
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))

print(f"Detected {len(block_onsets_samples)} blocks (expected 100)")


# ============================================================
# 3) EXTRACT 10% ON WINDOWS AND COMPUTE PLV PER CHANNEL
# ============================================================
print(f"\nAnalyzing 10% intensity (blocks 0–19)...")

# 10% intensity = blocks 0–19
block_indices_10pct = list(range(BLOCK_CYCLES_PER_INTENSITY))

on_raw_epochs_10pct = []
on_gt_epochs_10pct = []

for block_idx in block_indices_10pct:
    onset_sample = block_onsets_samples[block_idx]
    on_start = onset_sample + on_start_shift
    on_end = on_start + on_window_size

    if on_end > raw_data_2d.shape[1]:
        print(f"  Block {block_idx} ON window extends beyond recording; skipping.")
        continue

    on_eeg = raw_data_2d[:, on_start:on_end]  # (n_channels, samples)
    on_gt = gt_trace[on_start:on_end]  # (samples,)

    on_raw_epochs_10pct.append(on_eeg)
    on_gt_epochs_10pct.append(on_gt)

on_raw_epochs_10pct = np.asarray(on_raw_epochs_10pct, dtype=float)  # (n_cycles, n_channels, samples)
on_gt_epochs_10pct = np.asarray(on_gt_epochs_10pct, dtype=float)  # (n_cycles, samples)

print(f"Extracted {len(on_raw_epochs_10pct)} ON cycles at 10%")

# Compute PLV for each channel at 10%
print("\nComputing PLV for each channel at 10%...")
channel_plv_info_10pct = {}

for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
    ch_data = on_raw_epochs_10pct[:, ch_idx, :]  # (n_cycles, samples)

    # Compute PLV
    metrics = preprocessing.compute_epoch_plv_summary(
        ch_data,
        on_gt_epochs_10pct,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # Compute peak frequency via PSD
    ch_signal = preprocessing.filter_signal(ch_data, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    ch_psd = np.mean(np.abs(np.fft.rfft(ch_signal, axis=-1)) ** 2, axis=0)
    freqs_ch = np.fft.rfftfreq(ch_signal.shape[-1], 1 / sfreq)
    ch_peak_hz = float(freqs_ch[np.argmax(ch_psd)])

    channel_plv_info_10pct[ch_name] = {
        "plv": float(metrics["plv"]),
        "p_value": float(metrics["p_value"]),
        "mean_gt_locking": float(metrics["mean_gt_locking"]),
        "peak_hz": ch_peak_hz,
    }

    print(f"  {ch_name:8s}: PLV={metrics['plv']:.4f}, peak={ch_peak_hz:.2f} Hz")

# Select best channel at 10%
best_ch = max(channel_plv_info_10pct, key=lambda ch: channel_plv_info_10pct[ch]["plv"])
best_plv_10pct = channel_plv_info_10pct[best_ch]["plv"]
best_peak_hz_10pct = channel_plv_info_10pct[best_ch]["peak_hz"]

print(f"\n>>> BEST CHANNEL AT 10%: {best_ch} (PLV={best_plv_10pct:.4f}, peak={best_peak_hz_10pct:.2f} Hz)")


# ============================================================
# 4) COMPUTE PLV FOR BEST CHANNEL ACROSS ALL INTENSITIES
# ============================================================
print(f"\nComputing PLV for {best_ch} across all intensities...")

best_ch_idx = raw_eeg.ch_names.index(best_ch)
plv_per_intensity = {}
peak_hz_per_intensity = {}

for intensity_idx, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    # Extract ON windows for this intensity
    block_start_idx = intensity_idx * BLOCK_CYCLES_PER_INTENSITY
    block_stop_idx = block_start_idx + BLOCK_CYCLES_PER_INTENSITY
    block_indices = list(range(block_start_idx, block_stop_idx))

    on_raw_epochs = []
    on_gt_epochs = []

    for block_idx in block_indices:
        onset_sample = block_onsets_samples[block_idx]
        on_start = onset_sample + on_start_shift
        on_end = on_start + on_window_size

        if on_end > raw_data_2d.shape[1]:
            continue

        on_eeg = raw_data_2d[:, on_start:on_end]
        on_gt = gt_trace[on_start:on_end]

        on_raw_epochs.append(on_eeg)
        on_gt_epochs.append(on_gt)

    if not on_raw_epochs:
        print(f"  {intensity_label}: No valid windows; skipping.")
        plv_per_intensity[intensity_label] = None
        peak_hz_per_intensity[intensity_label] = None
        continue

    on_raw_epochs = np.asarray(on_raw_epochs, dtype=float)
    on_gt_epochs = np.asarray(on_gt_epochs, dtype=float)

    # Extract best channel and compute PLV
    ch_data = on_raw_epochs[:, best_ch_idx, :]
    metrics = preprocessing.compute_epoch_plv_summary(
        ch_data,
        on_gt_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # Compute peak frequency
    ch_signal = preprocessing.filter_signal(ch_data, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    ch_psd = np.mean(np.abs(np.fft.rfft(ch_signal, axis=-1)) ** 2, axis=0)
    freqs_ch = np.fft.rfftfreq(ch_signal.shape[-1], 1 / sfreq)
    ch_peak_hz = float(freqs_ch[np.argmax(ch_psd)])

    plv_per_intensity[intensity_label] = float(metrics["plv"])
    peak_hz_per_intensity[intensity_label] = ch_peak_hz

    print(f"  {intensity_label}: PLV={metrics['plv']:.4f}, peak={ch_peak_hz:.2f} Hz")


# ============================================================
# 5) EXTRACT FILTERED TIME COURSES FOR VISUALIZATION
# ============================================================
print(f"\nExtracting filtered time courses for {best_ch}...")

best_ch_timecourses = {}
best_gt_timecourses = {}

for intensity_idx, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    block_start_idx = intensity_idx * BLOCK_CYCLES_PER_INTENSITY
    block_stop_idx = block_start_idx + BLOCK_CYCLES_PER_INTENSITY
    block_indices = list(range(block_start_idx, block_stop_idx))

    ch_cycles = []
    gt_cycles = []

    for block_idx in block_indices:
        onset_sample = block_onsets_samples[block_idx]
        on_start = onset_sample + on_start_shift
        on_end = on_start + on_window_size

        if on_end > raw_data_2d.shape[1]:
            continue

        # Extract raw ON window
        on_eeg_raw = raw_data_2d[best_ch_idx, on_start:on_end]
        on_gt_raw = gt_trace[on_start:on_end]

        # Bandpass to signal band
        on_eeg_filt = preprocessing.filter_signal(
            on_eeg_raw[np.newaxis, :], sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
        )[0]
        on_gt_filt = preprocessing.filter_signal(
            on_gt_raw[np.newaxis, :], sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
        )[0]

        ch_cycles.append(on_eeg_filt)
        gt_cycles.append(on_gt_filt)

    if ch_cycles:
        best_ch_timecourses[intensity_label] = np.concatenate(ch_cycles)
        best_gt_timecourses[intensity_label] = np.concatenate(gt_cycles)
    else:
        best_ch_timecourses[intensity_label] = None
        best_gt_timecourses[intensity_label] = None


# ============================================================
# 6) PLOT 5-PANEL OVERLAY FIGURE
# ============================================================
print(f"\nCreating 5-panel overlay figure...")

fig, axes = plt.subplots(5, 1, figsize=(14, 12))
fig.suptitle(f"Fixed Raw Channel ({best_ch}) vs GT — ON Window (0.3–1.5 s post-onset)",
             fontsize=14, fontweight="bold")

for intensity_idx, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    ax = axes[intensity_idx]
    color = INTENSITY_COLORS[intensity_idx]

    if best_ch_timecourses[intensity_label] is None:
        ax.text(0.5, 0.5, f"No data for {intensity_label}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="red")
        ax.set_title(f"{intensity_label}: No data")
        continue

    ch_tc = best_ch_timecourses[intensity_label]
    gt_tc = best_gt_timecourses[intensity_label]
    time_axis_s = np.arange(len(ch_tc)) / sfreq

    plv_val = plv_per_intensity[intensity_label]
    peak_hz_val = peak_hz_per_intensity[intensity_label]

    # Plot GT (reference, black, thick)
    ax.plot(time_axis_s, gt_tc, "k-", linewidth=2.0, label="GT (reference)", zorder=3)

    # Plot best channel (color-coded by intensity)
    ax.plot(time_axis_s, ch_tc, color=color, linewidth=1.5,
            label=f"{best_ch} (PLV={plv_val:.4f})", zorder=2)

    ax.set_title(f"{intensity_label}: {best_ch} vs GT (peak={peak_hz_val:.2f} Hz)",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (µV)")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OVERLAY_FIGURE_PATH, dpi=150, bbox_inches="tight")
print(f"Saved figure: {OVERLAY_FIGURE_PATH}")
plt.close()


# ============================================================
# 7) EXPORT METADATA JSON
# ============================================================
print(f"\nExporting metadata JSON...")

metadata = {
    "reference_channel_name": best_ch,
    "reference_channel_index": best_ch_idx,
    "reference_intensity": "10%",
    "reference_plv": best_plv_10pct,
    "reference_peak_hz": best_peak_hz_10pct,
    "plv_per_intensity": plv_per_intensity,
    "peak_hz_per_intensity": peak_hz_per_intensity,
    "all_channel_plv_at_10pct": channel_plv_info_10pct,
}

with open(METADATA_PATH, "w") as f:
    json.dump(metadata, f, indent=2)

print(f"Saved metadata: {METADATA_PATH}")


# ============================================================
# 8) EXPORT SUMMARY TABLE
# ============================================================
print(f"\nExporting summary table...")

summary_lines = [
    "FIXED RAW CHANNEL — EXP06 RUN02 ACROSS INTENSITIES",
    "=" * 100,
    f"Target frequency: {TARGET_CENTER_HZ:.3f} Hz (band: {SIGNAL_BAND_HZ[0]:.2f}–{SIGNAL_BAND_HZ[1]:.2f} Hz)",
    f"ON window: {ON_WINDOW_S[0]}–{ON_WINDOW_S[1]} s post-onset",
    f"Per-intensity cycles: {BLOCK_CYCLES_PER_INTENSITY}",
    f"\nSelected Channel: {best_ch}",
    f"Selection Criterion: Highest PLV at 10% intensity",
    f"PLV at 10%: {best_plv_10pct:.4f}",
    f"Peak Hz at 10%: {best_peak_hz_10pct:.2f} Hz",
    "",
    "Intensity | PLV        | Peak Hz | Cycles | Notes",
    "-" * 100,
]

for intensity_label in RUN02_INTENSITY_LABELS:
    plv_val = plv_per_intensity[intensity_label]
    peak_hz_val = peak_hz_per_intensity[intensity_label]

    if plv_val is None:
        summary_lines.append(f"{intensity_label:10s} | N/A        | N/A     | N/A    | No data")
    else:
        if intensity_label == "10%":
            note = "Reference (selection basis)"
        else:
            note = "Fixed channel across intensities"
        summary_lines.append(f"{intensity_label:10s} | {plv_val:.4f}     | {peak_hz_val:6.2f}  | 20     | {note}")

summary_lines.extend([
    "",
    "INTERPRETATION:",
    f"- {best_ch} selected as best-aligned channel to GT at 10% intensity (PLV={best_plv_10pct:.4f})",
    "- Same channel used across all intensities to isolate dose effect on single electrode",
    "- Expected: PLV decreases with stimulation intensity as artifact contaminates the channel",
    "- Peak frequency may shift at high intensities due to artifact harmonics",
    "",
])

summary_text = "\n".join(summary_lines)
with open(SUMMARY_TABLE_PATH, "w") as f:
    f.write(summary_text)

print(summary_text)
print(f"Saved summary: {SUMMARY_TABLE_PATH}")

print("\nDone!")
