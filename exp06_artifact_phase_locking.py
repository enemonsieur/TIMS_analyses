"""Ask: Is artifact (STIM) phase-locked to GT across intensities?

CLAIM: Artifact and ground truth track each other with similar phase relationships
       across all stimulus intensities. This reveals whether stimulus artifact is
       a phase-coherent signal (locked) or random noise (unlocked).

FIGURE 1: Dual ITPC time course (STIM vs GT) per intensity
         Shows when artifact phase locks to GT.

FIGURE 2: Summary bar plot (ITPC at 0.3–1.5 s window) across 5 intensities
         Shows intensity-dependent artifact phase locking trend.
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
EXCLUDED_CH = {"TP9", "Fp1", "TP10"}

TARGET_HZ = 12.451172
SIGNAL_BAND = (TARGET_HZ - 0.5, TARGET_HZ + 0.5)
SFREQ = 250.0


# ════════════════════════════════════════════════════════════════════════════
# LOAD & PREP
# ════════════════════════════════════════════════════════════════════════════
print("Loading run02...")
with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    raw = mne.io.read_raw_brainvision(str(STIM_VHDR), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
stim_trace = raw.copy().pick(["stim"]).get_data()[0]      # → (n_samples,)
gt_trace = raw.copy().pick(["ground_truth"]).get_data()[0]  # → (n_samples,)

print(f"Loaded: {raw.n_times / sfreq:.1f} s @ {sfreq:.0f} Hz")


# ════════════════════════════════════════════════════════════════════════════
# HELPER: Band-pass filter
# ════════════════════════════════════════════════════════════════════════════
def bandpass(sig, lo, hi, fs):
    """Filter 1D or 2D signal to [lo, hi] Hz. Returns same shape."""
    from scipy.signal import butter, sosfilt
    sos = butter(4, [lo, hi], btype='band', fs=fs, output='sos')
    if sig.ndim == 1:
        return sosfilt(sos, sig)
    else:  # (n_epochs, n_samples)
        return np.array([sosfilt(sos, sig[i, :]) for i in range(sig.shape[0])])


# ════════════════════════════════════════════════════════════════════════════
# DETECT BLOCKS & EPOCH
# ════════════════════════════════════════════════════════════════════════════
import preprocessing

block_onsets, block_offsets = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=0.08
)
print(f"Detected {len(block_onsets)} blocks (expected {len(INTENSITIES) * BLOCK_CYCLES})")

on_start_shift = int(round(ON_WINDOW[0] * sfreq))
on_end_shift = int(round(ON_WINDOW[1] * sfreq))
on_len = on_end_shift - on_start_shift  # → 300 samples @ 250 Hz


# ════════════════════════════════════════════════════════════════════════════
# COMPUTE: ITPC(STIM vs GT) PER INTENSITY
# ════════════════════════════════════════════════════════════════════════════
"""
ITPC (Inter-Trial Phase Coherence) measures whether phase is consistent
across epochs. High ITPC = phase repeatable; low ITPC = phase random.

For each intensity:
  1. Extract 20 ON-window cycles
  2. Filter both STIM and GT to signal band (11.95–12.95 Hz)
  3. Compute instantaneous phase via Hilbert
  4. Compute phase difference: phase_stim - phase_gt
  5. ITPC = |mean(exp(i * phase_diff))| across epochs
  6. Result: (n_samples,) = ITPC time course
"""

itpc_results = {}
stim_gt_phase_diffs = {}  # Store for later polar histogram

for intensity_idx, intensity_label in enumerate(INTENSITIES):
    block_start = intensity_idx * BLOCK_CYCLES
    block_stop = block_start + BLOCK_CYCLES

    # Extract ON-window epochs for this intensity
    on_stim_epochs = []
    on_gt_epochs = []

    for block_idx in range(block_start, block_stop):
        onset = block_onsets[block_idx]
        on_start = onset + on_start_shift
        on_end = onset + on_end_shift

        if on_end > len(stim_trace):
            continue

        on_stim_epochs.append(stim_trace[on_start:on_end])
        on_gt_epochs.append(gt_trace[on_start:on_end])

    # → (20, 300) each
    on_stim_epochs = np.array(on_stim_epochs)
    on_gt_epochs = np.array(on_gt_epochs)

    # Band-pass to signal band
    stim_filt = bandpass(on_stim_epochs, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)
    gt_filt = bandpass(on_gt_epochs, SIGNAL_BAND[0], SIGNAL_BAND[1], sfreq)

    # Hilbert phase
    stim_phase = np.angle(signal.hilbert(stim_filt, axis=-1))  # → (20, 300)
    gt_phase = np.angle(signal.hilbert(gt_filt, axis=-1))

    # Phase difference per sample (20 epochs × 300 samples)
    phase_diff = stim_phase - gt_phase  # → (20, 300)

    # ITPC per sample: |mean(exp(i * phase_diff))|
    itpc_ts = np.abs(np.mean(np.exp(1j * phase_diff), axis=0))  # → (300,)

    itpc_results[intensity_label] = itpc_ts
    stim_gt_phase_diffs[intensity_label] = phase_diff.flatten()  # Store flattened for histogram

    # Summary: mean ITPC in ON window
    mean_itpc = np.mean(itpc_ts)
    print(f"{intensity_label}: ITPC(STIM vs GT) = {mean_itpc:.4f}")


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 1: Dual ITPC Time Courses (One per Intensity)
# ════════════════════════════════════════════════════════════════════════════
"""
CLAIM: Artifact phase locking to GT increases or decreases with stimulus intensity.

CHART FAMILY: Line plot (time course per intensity)

LAYOUT: 5 panels (one per intensity), each showing ITPC(STIM vs GT) over time
"""

fig, axes = plt.subplots(5, 1, figsize=(10, 10))
fig.suptitle("Is Artifact (STIM) Phase-Locked to GT?\nITPC(STIM vs GT) Time Course per Intensity",
             fontsize=12, fontweight="bold")

colors = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]
time_s = np.arange(on_len) / sfreq

for idx, (intensity_label, ax) in enumerate(zip(INTENSITIES, axes)):
    itpc_ts = itpc_results[intensity_label]
    mean_itpc = np.mean(itpc_ts)

    ax.plot(time_s, itpc_ts, color=colors[idx], linewidth=2, label=f"ITPC = {mean_itpc:.3f}")
    ax.fill_between(time_s, 0, itpc_ts, alpha=0.3, color=colors[idx])
    ax.set_ylim([0, 1])
    ax.set_ylabel("ITPC", fontsize=9)
    ax.set_title(f"{intensity_label}: STIM phase locking to GT", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)

axes[-1].set_xlabel("Time (s)", fontsize=9)
plt.tight_layout()
fig_path_1 = OUT_DIR / "exp06_artifact_itpc_timecourse.png"
plt.savefig(fig_path_1, dpi=150, bbox_inches="tight")
print(f"\nSaved Figure 1: {fig_path_1}")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 2: Summary Bar Plot (Mean ITPC per Intensity)
# ════════════════════════════════════════════════════════════════════════════
"""
CLAIM: Artifact phase locking follows a systematic trend across stimulus intensities.

CHART FAMILY: Bar plot (one value per category)

Shows overall phase-locking strength per intensity (mean ITPC over 0.3–1.5 s window)
"""

mean_itpcs = np.array([np.mean(itpc_results[label]) for label in INTENSITIES])

fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(INTENSITIES, mean_itpcs, color=colors, edgecolor="black", linewidth=1.5, alpha=0.8)

# Add value labels on bars
for bar, val in zip(bars, mean_itpcs):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.3f}",
            ha="center", va="bottom", fontsize=9, fontweight="bold")

ax.set_ylabel("Mean ITPC (0.3–1.5 s)", fontsize=11, fontweight="bold")
ax.set_xlabel("Stimulus Intensity", fontsize=11, fontweight="bold")
ax.set_ylim([0, 1.0])
ax.set_title("Artifact Phase Locking to Ground Truth vs Stimulus Intensity",
             fontsize=12, fontweight="bold")
ax.grid(True, alpha=0.3, axis="y")

plt.tight_layout()
fig_path_2 = OUT_DIR / "exp06_artifact_itpc_summary.png"
plt.savefig(fig_path_2, dpi=150, bbox_inches="tight")
print(f"Saved Figure 2: {fig_path_2}")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 3: Phase Difference Polar Histograms (Companion to Figure 1)
# ════════════════════════════════════════════════════════════════════════════
"""
CLAIM: Artifact phase offset from GT is consistent (concentrated) or random (spread).

CHART FAMILY: Polar histogram (circular distribution)

Shows whether phase_diff = phase_stim - phase_gt clusters at 0 rad (locked)
or spreads uniformly (unlocked).
"""

fig = plt.figure(figsize=(14, 5))

for idx, intensity_label in enumerate(INTENSITIES):
    ax = fig.add_subplot(1, 5, idx + 1, projection='polar')

    phase_diffs = stim_gt_phase_diffs[intensity_label]

    # Histogram in polar coordinates
    n_bins = 36
    ax.hist(phase_diffs, bins=n_bins, color=colors[idx], alpha=0.7, edgecolor="black")

    ax.set_theta_zero_location("E")
    ax.set_theta_direction(-1)
    ax.set_title(f"{intensity_label}", fontsize=10, fontweight="bold")
    ax.set_ylim([0, np.max([np.histogram(stim_gt_phase_diffs[l], bins=n_bins)[0].max()
                             for l in INTENSITIES]) * 1.1])

fig.suptitle("Phase Difference Distribution: STIM − GT\n(Clustered = Locked, Spread = Unlocked)",
             fontsize=12, fontweight="bold", y=1.02)
plt.tight_layout()
fig_path_3 = OUT_DIR / "exp06_artifact_phase_distribution.png"
plt.savefig(fig_path_3, dpi=150, bbox_inches="tight")
print(f"Saved Figure 3: {fig_path_3}")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ════════════════════════════════════════════════════════════════════════════

summary_lines = [
    "ARTIFACT PHASE LOCKING ANALYSIS: Is STIM Phase-Locked to GT?",
    "=" * 70,
    f"Target frequency: {TARGET_HZ:.3f} Hz (band: {SIGNAL_BAND[0]:.2f}–{SIGNAL_BAND[1]:.2f} Hz)",
    f"ON window: {ON_WINDOW[0]}–{ON_WINDOW[1]} s post-onset",
    "",
    "Intensity | Mean ITPC | Interpretation",
    "-" * 70,
]

for intensity_label, mean_itpc in zip(INTENSITIES, mean_itpcs):
    if mean_itpc > 0.8:
        interp = "High phase lock (artifact is coherent)"
    elif mean_itpc > 0.5:
        interp = "Moderate phase lock"
    else:
        interp = "Low phase lock (artifact is noisy)"

    summary_lines.append(f"{intensity_label:10s} | {mean_itpc:.4f}    | {interp}")

summary_lines.extend([
    "",
    "INTERPRETATION:",
    "- ITPC ≈ 1.0: STIM and GT phases track perfectly (highly correlated signals)",
    "- ITPC ≈ 0.5: Partial phase locking (mixed behavior)",
    "- ITPC ≈ 0.0: No phase locking (random phase relationship)",
    "",
    "KEY INSIGHT:",
    "If ITPC(STIM vs GT) is high, artifact and GT are phase-coherent.",
    "This explains why extracted signals lock to both equally well.",
])

summary_text = "\n".join(summary_lines)
summary_path = OUT_DIR / "exp06_artifact_phase_locking.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write(summary_text)

print(f"\nSaved Summary: {summary_path}")
# print("\n" + summary_text)  # Skip unicode print to console

print("\nDone!")
