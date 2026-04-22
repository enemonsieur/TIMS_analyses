"""Why is STIM phase-locked to GT? Visual comparison of actual signals.

CLAIM: Ground truth (GT) and stimulation (STIM) voltage traces are actually
       the same signal, or GT is derived from STIM, or they're coupled by hardware.
       Visual overlay will reveal the relationship.

APPROACH: Plot GT and STIM side-by-side with independent y-axes (amplitude scaling)
          so we can see phase alignment without amplitude confounding.
"""

import os
from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

import mne

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR = DATA_DIR / "exp06-STIM-iTBS_run02.vhdr"
OUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTENSITIES = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES = 20
ON_WINDOW = (0.3, 1.5)

TARGET_HZ = 12.451172
SIGNAL_BAND = (TARGET_HZ - 0.5, TARGET_HZ + 0.5)


# ════════════════════════════════════════════════════════════════════════════
# LOAD
# ════════════════════════════════════════════════════════════════════════════
print("Loading run02...")
with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    raw = mne.io.read_raw_brainvision(str(STIM_VHDR), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
stim_trace = raw.copy().pick(["stim"]).get_data()[0]
gt_trace = raw.copy().pick(["ground_truth"]).get_data()[0]

print(f"Loaded: {raw.n_times / sfreq:.1f} s @ {sfreq:.0f} Hz")


# ════════════════════════════════════════════════════════════════════════════
# HELPER: Band-pass filter
# ════════════════════════════════════════════════════════════════════════════
def bandpass(sig, lo, hi, fs):
    """Filter 1D or 2D signal to [lo, hi] Hz."""
    from scipy.signal import butter, sosfilt
    sos = butter(4, [lo, hi], btype='band', fs=fs, output='sos')
    if sig.ndim == 1:
        return sosfilt(sos, sig)
    else:
        return np.array([sosfilt(sos, sig[i, :]) for i in range(sig.shape[0])])


# ════════════════════════════════════════════════════════════════════════════
# DETECT BLOCKS & EPOCH
# ════════════════════════════════════════════════════════════════════════════
import preprocessing

block_onsets, block_offsets = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=0.08
)

on_start_shift = int(round(ON_WINDOW[0] * sfreq))
on_end_shift = int(round(ON_WINDOW[1] * sfreq))
on_len = on_end_shift - on_start_shift


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 1: Raw Time Courses (Unfiltered) — One Per Intensity
# ════════════════════════════════════════════════════════════════════════════
"""
CLAIM: GT and STIM traces look identical when overlaid (independent axes).

Shows raw, unfiltered signals to see amplitude differences and timing offset.
"""

fig, axes = plt.subplots(5, 1, figsize=(12, 10))
fig.suptitle("GT vs STIM Raw Time Courses (Unfiltered)\nIndependent y-axes to show phase relationship",
             fontsize=12, fontweight="bold")

colors_gt = "#000000"  # Black
colors_stim = "#FF6B6B"  # Red

for intensity_idx, intensity_label in enumerate(INTENSITIES):
    ax = axes[intensity_idx]
    block_start = intensity_idx * BLOCK_CYCLES
    block_stop = block_start + BLOCK_CYCLES

    # Extract first 3 cycles for clarity
    onset_first = block_onsets[block_start]
    on_start = onset_first + on_start_shift
    on_end = onset_first + on_end_shift

    on_gt = gt_trace[on_start:on_end]
    on_stim = stim_trace[on_start:on_end]

    time_s = np.arange(len(on_gt)) / sfreq

    # Create dual y-axes
    ax1 = ax
    ax2 = ax1.twinx()

    # GT on left axis (black)
    ax1.plot(time_s, on_gt, color=colors_gt, linewidth=2, label="GT", alpha=0.9)
    ax1.set_ylabel("GT (V)", fontsize=9, color=colors_gt, fontweight="bold")
    ax1.tick_params(axis='y', labelcolor=colors_gt, labelsize=8)

    # STIM on right axis (red)
    ax2.plot(time_s, on_stim, color=colors_stim, linewidth=2, label="STIM", alpha=0.9)
    ax2.set_ylabel("STIM (V)", fontsize=9, color=colors_stim, fontweight="bold")
    ax2.tick_params(axis='y', labelcolor=colors_stim, labelsize=8)

    ax1.set_title(f"{intensity_label}: Raw GT (black, left) vs STIM (red, right) — First cycle",
                  fontsize=10, fontweight="bold")
    ax1.set_xlabel("Time (s)", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)

plt.tight_layout()
fig_path_1 = OUT_DIR / "exp06_gt_stim_raw_overlay.png"
plt.savefig(fig_path_1, dpi=150, bbox_inches="tight")
print(f"Saved Figure 1: {fig_path_1}")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 2: Filtered Time Courses (12.45 Hz Band)
# ════════════════════════════════════════════════════════════════════════════
"""
CLAIM: After filtering to 12.45 Hz band, GT and STIM oscillations align in phase.

Shows whether the phase locking is real or a filtering artifact.
"""

fig, axes = plt.subplots(5, 1, figsize=(12, 10))
fig.suptitle("GT vs STIM Filtered to 12.45 Hz (Signal Band)\nShowing phase alignment",
             fontsize=12, fontweight="bold")

for intensity_idx, intensity_label in enumerate(INTENSITIES):
    ax = axes[intensity_idx]
    block_start = intensity_idx * BLOCK_CYCLES
    onset_first = block_onsets[block_start]
    on_start = onset_first + on_start_shift
    on_end = onset_first + on_end_shift

    on_gt = gt_trace[on_start:on_end]
    on_stim = stim_trace[on_start:on_end]

    # Filter to signal band
    gt_filt = bandpass(on_gt, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)
    stim_filt = bandpass(on_stim, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)

    time_s = np.arange(len(gt_filt)) / sfreq

    ax1 = ax
    ax2 = ax1.twinx()

    ax1.plot(time_s, gt_filt, color=colors_gt, linewidth=2, label="GT", alpha=0.9)
    ax1.set_ylabel("GT (V)", fontsize=9, color=colors_gt, fontweight="bold")
    ax1.tick_params(axis='y', labelcolor=colors_gt, labelsize=8)

    ax2.plot(time_s, stim_filt, color=colors_stim, linewidth=2, label="STIM", alpha=0.9)
    ax2.set_ylabel("STIM (V)", fontsize=9, color=colors_stim, fontweight="bold")
    ax2.tick_params(axis='y', labelcolor=colors_stim, labelsize=8)

    ax1.set_title(f"{intensity_label}: Filtered GT (black, left) vs STIM (red, right) — 11.95-12.95 Hz",
                  fontsize=10, fontweight="bold")
    ax1.set_xlabel("Time (s)", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)

plt.tight_layout()
fig_path_2 = OUT_DIR / "exp06_gt_stim_filtered_overlay.png"
plt.savefig(fig_path_2, dpi=150, bbox_inches="tight")
print(f"Saved Figure 2: {fig_path_2}")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 3: Multi-Cycle View (All 20 Cycles Concatenated)
# ════════════════════════════════════════════════════════════════════════════
"""
CLAIM: Across 20 cycles, GT and STIM remain phase-locked consistently.

Shows whether phase locking is stable or drifts.
"""

fig, axes = plt.subplots(5, 1, figsize=(14, 10))
fig.suptitle("GT vs STIM Across All 20 Cycles (Filtered 12.45 Hz)\nShowing consistency of phase lock",
             fontsize=12, fontweight="bold")

for intensity_idx, intensity_label in enumerate(INTENSITIES):
    ax = axes[intensity_idx]
    block_start = intensity_idx * BLOCK_CYCLES
    block_stop = block_start + BLOCK_CYCLES

    # Concatenate all 20 cycles
    gt_all = []
    stim_all = []
    for block_idx in range(block_start, block_stop):
        onset = block_onsets[block_idx]
        on_start = onset + on_start_shift
        on_end = onset + on_end_shift

        if on_end > len(gt_trace):
            continue

        gt_all.append(gt_trace[on_start:on_end])
        stim_all.append(stim_trace[on_start:on_end])

    gt_concat = np.concatenate(gt_all)
    stim_concat = np.concatenate(stim_all)

    # Filter
    gt_filt = bandpass(gt_concat, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)
    stim_filt = bandpass(stim_concat, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)

    time_s = np.arange(len(gt_filt)) / sfreq

    ax1 = ax
    ax2 = ax1.twinx()

    ax1.plot(time_s, gt_filt, color=colors_gt, linewidth=1.5, label="GT", alpha=0.8)
    ax1.set_ylabel("GT (V)", fontsize=9, color=colors_gt, fontweight="bold")
    ax1.tick_params(axis='y', labelcolor=colors_gt, labelsize=8)

    ax2.plot(time_s, stim_filt, color=colors_stim, linewidth=1.5, label="STIM", alpha=0.8)
    ax2.set_ylabel("STIM (V)", fontsize=9, color=colors_stim, fontweight="bold")
    ax2.tick_params(axis='y', labelcolor=colors_stim, labelsize=8)

    ax1.set_title(f"{intensity_label}: All 20 cycles concatenated (~24 s)",
                  fontsize=10, fontweight="bold")
    ax1.set_xlabel("Time (s)", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)

plt.tight_layout()
fig_path_3 = OUT_DIR / "exp06_gt_stim_multicycle_overlay.png"
plt.savefig(fig_path_3, dpi=150, bbox_inches="tight")
print(f"Saved Figure 3: {fig_path_3}")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# ANALYSIS: Compute correlation + amplitude ratio
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("ANALYSIS: What is the relationship between GT and STIM?")
print("=" * 70)

summary_lines = [
    "GT vs STIM RELATIONSHIP ANALYSIS",
    "=" * 70,
    "",
]

for intensity_idx, intensity_label in enumerate(INTENSITIES):
    block_start = intensity_idx * BLOCK_CYCLES
    block_stop = block_start + BLOCK_CYCLES

    # Concatenate all 20 cycles
    gt_all = []
    stim_all = []
    for block_idx in range(block_start, block_stop):
        onset = block_onsets[block_idx]
        on_start = onset + on_start_shift
        on_end = onset + on_end_shift

        if on_end > len(gt_trace):
            continue

        gt_all.append(gt_trace[on_start:on_end])
        stim_all.append(stim_trace[on_start:on_end])

    gt_concat = np.concatenate(gt_all)
    stim_concat = np.concatenate(stim_all)

    # Filter
    gt_filt = bandpass(gt_concat, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)
    stim_filt = bandpass(stim_concat, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)

    # Correlation
    corr = np.corrcoef(gt_filt, stim_filt)[0, 1]

    # Amplitude ratio
    gt_amp = np.std(gt_filt)
    stim_amp = np.std(stim_filt)
    amp_ratio = stim_amp / gt_amp

    # Peak frequencies
    gt_fft = np.abs(np.fft.rfft(gt_filt))
    stim_fft = np.abs(np.fft.rfft(stim_filt))
    freqs = np.fft.rfftfreq(len(gt_filt), 1 / sfreq)
    gt_peak_hz = freqs[np.argmax(gt_fft)]
    stim_peak_hz = freqs[np.argmax(stim_fft)]

    print(f"\n{intensity_label}:")
    print(f"  Correlation (GT vs STIM): {corr:.4f}")
    print(f"  Amplitude ratio (STIM / GT): {amp_ratio:.4f}")
    print(f"  GT peak frequency: {gt_peak_hz:.2f} Hz")
    print(f"  STIM peak frequency: {stim_peak_hz:.2f} Hz")

    summary_lines.append(f"{intensity_label}:")
    summary_lines.append(f"  Correlation: {corr:.4f}")
    summary_lines.append(f"  Amplitude ratio (STIM / GT): {amp_ratio:.4f}")
    summary_lines.append(f"  GT peak: {gt_peak_hz:.2f} Hz | STIM peak: {stim_peak_hz:.2f} Hz")
    summary_lines.append("")

summary_lines.extend([
    "=" * 70,
    "INTERPRETATION:",
    "",
    "Correlation near 1.0 = GT and STIM are essentially the same signal",
    "Correlation near 0.0 = GT and STIM are independent",
    "",
    "If corr > 0.95: GT is likely DERIVED FROM STIM (hardware feedback loop)",
    "If corr < 0.5: Phase locking is due to external timing, not signal copying",
])

summary_text = "\n".join(summary_lines)
summary_path = OUT_DIR / "exp06_gt_stim_analysis.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write(summary_text)

print(f"\nSaved summary: {summary_path}")

print("\nDone!")
