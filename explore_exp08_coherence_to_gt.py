"""Analyze ITPC (inter-trial phase coherence) with ground-truth across all intensities and channels."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import preprocessing

# ============================================================
# CONFIG
# ============================================================

EXP08_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
INTENSITIES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
FREQ_BAND = (12.5, 13.5)  # 13 Hz GT ± 0.5 Hz

# OFF-window: quiet region far from artifact (0.4–0.5 s post-pulse)
OFF_WINDOW_TMIN_S = 0.4
OFF_WINDOW_TMAX_S = 0.5

OUTPUT_HEATMAP = EXP08_DIR / "exp08_coherence_to_gt_heatmap.png"
OUTPUT_SUMMARY = EXP08_DIR / "exp08_coherence_to_gt_summary.png"

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Epoch Files (exp08_epochs_*pct_on-epo.fif, 20 epochs per intensity)
# ├─ Loop over 10 intensity levels (10%, 20%, ..., 100%)
# │
# ├─ For each intensity:
# │  ├─ Load EEG epochs (28 channels, 20 epochs)
# │  ├─ Load GT epochs (20 epochs)
# │  ├─ Crop to OFF-window (0.4–0.5 s, quiet region)
# │  └─ Compute ITPC per channel vs GT → (28 channels,) ITPC values
# │
# ├─ Aggregate: (28 channels, 10 intensities) ITPC matrix
# │
# └─ Visualize: 2-panel figure
#    ├─ Panel 1: Heatmap (channels × intensities, color = ITPC)
#    └─ Panel 2: Line plot (intensity vs mean ITPC ± std across channels)

# ============================================================
# 1) SETUP
# ============================================================

# ══ 1.1 Load first epoch to extract channel names ══
epochs_test_path = EXP08_DIR / "exp08_epochs_10pct_on-epo.fif"
epochs_test = mne.read_epochs(str(epochs_test_path), preload=True, verbose=False)
ch_names = epochs_test.ch_names
n_channels = len(ch_names)
sfreq = float(epochs_test.info["sfreq"])
print(f"Channels: {n_channels}, sfreq: {sfreq} Hz")

# ══ 1.2 Compute 0% baseline (pre-pulse) ══
baseline_itpc = np.zeros(n_channels)
print("\n[0/10] Computing 0% baseline (pre-pulse -1.0 to 0.0 s)...")
for ch_idx in range(n_channels):
    ch_data_baseline_list = []
    gt_data_baseline_list = []
    # Average baseline across all 10 intensities (baseline is same everywhere)
    for intensity in INTENSITIES:
        eeg_path = EXP08_DIR / f"exp08_epochs_{intensity}pct_on-epo.fif"
        eeg_epochs = mne.read_epochs(str(eeg_path), preload=True, verbose=False)
        eeg_epochs.crop(tmin=-1.0, tmax=0.0)  # Pre-pulse window
        ch_data_baseline_list.append(eeg_epochs.get_data()[:, ch_idx, :] * 1e6)

        gt_path = EXP08_DIR / f"exp08_gt_epochs_{intensity}pct_on-epo.fif"
        gt_epochs = mne.read_epochs(str(gt_path), preload=True, verbose=False)
        gt_epochs.crop(tmin=-1.0, tmax=0.0)
        gt_data_baseline_list.append(gt_epochs.get_data().squeeze())

    ch_data_baseline = np.concatenate(ch_data_baseline_list, axis=0)  # (200 epochs, samples)
    gt_data_baseline = np.concatenate(gt_data_baseline_list, axis=0)
    baseline_itpc[ch_idx] = preprocessing.compute_itpc_timecourse(ch_data_baseline, gt_data_baseline, sfreq, FREQ_BAND).mean()

print(f"  Mean ITPC @ 0% (baseline): {baseline_itpc.mean():.4f} ± {baseline_itpc.std():.4f}")

# ══ 1.3 Initialize storage ══
itpc_matrix = np.zeros((n_channels, len(INTENSITIES) + 1))  # +1 for baseline
print(f"\nITPC matrix shape: {itpc_matrix.shape}")

# ============================================================
# 2) LOOP OVER INTENSITIES AND COMPUTE ITPC
# ============================================================

# ══ 2.1 Insert baseline at index 0 ══
itpc_matrix[:, 0] = baseline_itpc

for intensity_idx, intensity in enumerate(INTENSITIES):
    matrix_idx = intensity_idx + 1  # Shift by 1 (0% is at index 0)
    print(f"\n[{intensity_idx+1}/10] Processing {intensity}% intensity...")

    # ══ 2.2 Load EEG epochs ══
    eeg_path = EXP08_DIR / f"exp08_epochs_{intensity}pct_on-epo.fif"
    eeg_epochs = mne.read_epochs(str(eeg_path), preload=True, verbose=False)
    eeg_data_uv = eeg_epochs.copy().get_data() * 1e6  # (20 epochs, channels, samples) µV

    # ══ 2.3 Load GT epochs and crop to OFF-window ══
    gt_path = EXP08_DIR / f"exp08_gt_epochs_{intensity}pct_on-epo.fif"
    gt_epochs = mne.read_epochs(str(gt_path), preload=True, verbose=False)
    gt_epochs.crop(tmin=OFF_WINDOW_TMIN_S, tmax=OFF_WINDOW_TMAX_S)
    gt_data = gt_epochs.get_data().squeeze()  # (20 epochs, n_samples)

    # ══ 2.4 Crop EEG to OFF-window for ITPC ══
    eeg_epochs.crop(tmin=OFF_WINDOW_TMIN_S, tmax=OFF_WINDOW_TMAX_S)
    eeg_data_cropped = eeg_epochs.get_data() * 1e6  # (20 epochs, channels, n_samples) µV

    # ══ 2.5 Compute ITPC per channel ══
    for ch_idx in range(n_channels):
        ch_data = eeg_data_cropped[:, ch_idx, :]  # (20 epochs, n_samples)
        itpc_val = preprocessing.compute_itpc_timecourse(ch_data, gt_data, sfreq, FREQ_BAND)
        # compute_itpc_timecourse returns (n_samples,) timecourse; take mean across time
        itpc_matrix[ch_idx, matrix_idx] = itpc_val.mean()

    print(f"  Mean ITPC @ {intensity}%: {itpc_matrix[:, matrix_idx].mean():.4f} ± {itpc_matrix[:, matrix_idx].std():.4f}")

# ============================================================
# 3) PLOT 2-PANEL FIGURE
# ============================================================

fig, (ax_hm, ax_line) = plt.subplots(1, 2, figsize=(14, 6))

# ══ 3.1 Heatmap panel (channels × intensities) ══
im = ax_hm.imshow(itpc_matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
ax_hm.set_xlabel("Intensity (%)", fontsize=11, fontweight="bold")
ax_hm.set_ylabel("Channel", fontsize=11, fontweight="bold")
intensity_labels = [0] + INTENSITIES
ax_hm.set_xticks(range(len(intensity_labels)))
ax_hm.set_xticklabels(intensity_labels, rotation=45)
ax_hm.set_yticks(range(0, n_channels, 5))
ax_hm.set_yticklabels([ch_names[i] for i in range(0, n_channels, 5)])
ax_hm.set_title("ITPC vs GT (OFF-window)", fontsize=12, fontweight="bold")
cbar = plt.colorbar(im, ax=ax_hm)
cbar.set_label("ITPC (0–1)", fontsize=10)

# ══ 3.2 Summary line plot (intensity vs mean ITPC) ══
mean_itpc = itpc_matrix.mean(axis=0)  # (11 intensities: 0% + 10 stim levels)
std_itpc = itpc_matrix.std(axis=0)
intensity_axis = [0] + INTENSITIES
ax_line.plot(intensity_axis, mean_itpc, marker="o", linewidth=2.5, markersize=8, color="#1f77b4", label="Mean ITPC")
ax_line.fill_between(intensity_axis, mean_itpc - std_itpc, mean_itpc + std_itpc, alpha=0.3, color="#1f77b4", label="±1 SD (channels)")
ax_line.axvline(0, color="red", linestyle=":", linewidth=2, alpha=0.5, label="Stim onset")
ax_line.axhline(0.5, color="gray", linestyle="--", linewidth=1, alpha=0.5, label="50% coherence threshold")
ax_line.set_xlabel("Intensity (%)", fontsize=11, fontweight="bold")
ax_line.set_ylabel("ITPC", fontsize=11, fontweight="bold")
ax_line.set_xlim(-5, 105)
ax_line.set_ylim(0, 1)
ax_line.grid(True, alpha=0.2)
ax_line.legend(fontsize=9, loc="best")
ax_line.set_title("ITPC Trend: Baseline vs Stimulation", fontsize=12, fontweight="bold")

# ══ 3.3 Format and save ══
fig.suptitle("EXP08: Ground-Truth Phase Coherence Analysis (OFF-window 0.4-0.5 s)", fontsize=13, fontweight="bold", y=1.00)
fig.tight_layout()
fig.savefig(OUTPUT_HEATMAP, dpi=220, bbox_inches="tight")
plt.close()

# ============================================================
# 4) SAVE SUMMARY STATISTICS
# ============================================================

print("\n" + "="*60)
print("ITPC SUMMARY STATISTICS")
print("="*60)
print(f"{'Intensity':<12} {'Mean ITPC':<12} {'Std Dev':<12} {'Min':<12} {'Max':<12} {'Window':<20}")
print("-"*85)
# Baseline (0%)
col = itpc_matrix[:, 0]
print(f"{'  0% (pre)':>10} {col.mean():>11.4f} {col.std():>11.4f} {col.min():>11.4f} {col.max():>11.4f} {'-1.0 to 0.0 s':>20}")
# Stimulation levels (OFF-window)
for intensity_idx, intensity in enumerate(INTENSITIES):
    col = itpc_matrix[:, intensity_idx + 1]
    print(f"{intensity:>10}% {col.mean():>11.4f} {col.std():>11.4f} {col.min():>11.4f} {col.max():>11.4f} {'0.4 to 0.5 s':>20}")

print(f"\n[OK] Saved heatmap: {OUTPUT_HEATMAP.name}")
