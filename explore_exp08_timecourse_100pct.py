"""Plot mean EEG timecourse at 100% intensity: 5 channels + ITPC overlayed with stimulus."""

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
CHANNELS_TO_PLOT = ["Pz", "P3", "P4", "Oz", "O1"]
 #["Cz", "C3", "C4", "Oz", "Pz"]  # easy to modify

# Post-pulse window definition
WINDOW_TMIN_S = -0.5
WINDOW_TMAX_S = 0.8

OUTPUT_PATH = EXP08_DIR / "exp08_timecourse_10pctFC_overlay.png"

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Epoch File (exp08_epochs_50pct-epo.fif, 20 epochs)
# ├─ Load: 50% intensity epochs
# ├─ Extract: target channels + stim trace
# │
# ├─ Average: mean timecourse across 20 epochs per channel
# │  └─ OUTPUT: (5 channels, n_samples) mean EEG
# │           (n_samples,) mean stim
# │
# └─ Plot: 6 subplots (5 channels + ITPC, dual y-axis per subplot)
#    └─ OUTPUT: exp08_timecourse_50pct_overlay.png

# ============================================================
# 1) LOAD EPOCHS & PREPARE
# ============================================================

# ══ 1.1 Load 100% intensity epochs ══
epochs_100pct_path = EXP08_DIR / "exp08_epochs_10pct-epo.fif"
epochs = mne.read_epochs(str(epochs_100pct_path), preload=True, verbose=False)
# → MNE Epochs: (20 epochs, channels, samples)

# print epochs min and max lenghts
print(f"Epochs loaded: {len(epochs)} epochs, {len(epochs.ch_names)} channels (before crop)")
sfreq = float(epochs.info["sfreq"])

print(f"Loaded: {len(epochs)} epochs @ {sfreq:.0f} Hz")

# ══ 1.2 Crop EEG epochs to display window ══
epochs.crop(tmin=WINDOW_TMIN_S, tmax=WINDOW_TMAX_S)
eeg_data_uv = epochs.copy().pick(CHANNELS_TO_PLOT).get_data() * 1e6
# → (20 epochs, 5 channels, n_samples) µV

# ══ 1.3 Load stim epochs (stored separately) and crop to same window ══
stim_epochs_path = EXP08_DIR / "exp08_stim_epochs_10pct_on-epo.fif"
stim_epochs = mne.read_epochs(str(stim_epochs_path), preload=True, verbose=False)
stim_epochs.crop(tmin=WINDOW_TMIN_S, tmax=WINDOW_TMAX_S)
stim_data = stim_epochs.get_data()[:, 0, :]
# → (20 epochs, n_samples) stim voltage, cropped to match EEG window

# ══ 1.4 Load GT epochs for ITPC ══
gt_epochs_path = EXP08_DIR / "exp08_gt_epochs_10pct_on-epo.fif"
gt_epochs = mne.read_epochs(str(gt_epochs_path), preload=True, verbose=False)
gt_epochs.crop(tmin=WINDOW_TMIN_S, tmax=WINDOW_TMAX_S)
gt_data = gt_epochs.get_data().squeeze()  # (20 epochs, n_samples)

# ══ 1.5 Verify all data arrays have the same length ══
assert eeg_data_uv.shape[2] == stim_data.shape[1] == gt_data.shape[1], \
    f"Shape mismatch: EEG {eeg_data_uv.shape[2]}, stim {stim_data.shape[1]}, GT {gt_data.shape[1]}"

# ============================================================
# 2) COMPUTE MEAN TIMECOURSE
# ============================================================

# ══ 2.0 Extract time axis from cropped epochs ══
time_s = epochs.times  # (n_samples,) after cropping
n_samples = len(time_s)
print(f"Samples: {n_samples}, window: {WINDOW_TMIN_S} to {WINDOW_TMAX_S} s")

# ══ 2.1 Average across 20 epochs ══
eeg_mean_uv = eeg_data_uv.mean(axis=0)
# → (5 channels, n_samples) mean EEG µV

stim_mean = stim_data.mean(axis=0)
# → (n_samples,) mean stim voltage

# ══ 2.2 Baseline correction: use pre-pulse + post-artifact periods (exclude 0.1–0.4 s artifact) ══
# Baseline window: pre-pulse (-0.1 to 0.0 s) + post-artifact (0.4 to 0.5 s)
baseline_mask_pre = time_s <= 0.0
baseline_mask_post = time_s >= 0.4
baseline_mask = baseline_mask_pre | baseline_mask_post

print("\nPER-CHANNEL BASELINE CORRECTION:")
for ch_idx in range(eeg_mean_uv.shape[0]):
    baseline_mean = eeg_mean_uv[ch_idx, baseline_mask].mean()
    baseline_std = eeg_mean_uv[ch_idx, baseline_mask].std()
    eeg_mean_uv[ch_idx] -= baseline_mean
    corrected_mean = eeg_mean_uv[ch_idx, baseline_mask].mean()
    corrected_std = eeg_mean_uv[ch_idx, baseline_mask].std()
    print(f"  {CHANNELS_TO_PLOT[ch_idx]}: baseline_mean={baseline_mean:.2f}µV, after_correction={corrected_mean:.2f}µV, overall_range=({eeg_mean_uv[ch_idx].min():.2f}, {eeg_mean_uv[ch_idx].max():.2f})µV")

# ══ 2.3 Compute ITPC per channel (phase coherence vs GT) ══
itpc_by_channel = {}
for ch_idx in range(eeg_data_uv.shape[1]):
    ch_data = eeg_data_uv[:, ch_idx, :]  # (20 epochs, n_samples)
    itpc = preprocessing.compute_itpc_timecourse(ch_data, gt_data, sfreq, (12.5, 13.5))
    itpc_by_channel[CHANNELS_TO_PLOT[ch_idx]] = itpc

# Stim: min-subtract for visibility (voltage always ≥ 0)
stim_mean = stim_mean - np.min(stim_mean)
print(f"\nOverall EEG range: {eeg_mean_uv.min():.2f} to {eeg_mean_uv.max():.2f} µV")
print(f"Overall stim range: {stim_mean.min():.2f} to {stim_mean.max():.2f} V")

# ============================================================
# 3) PLOT 5 SUBPLOTS (CHANNEL + STIM DUAL-AXIS)
# ============================================================

# ══ 3.1 Create 6-panel figure (5 channels + ITPC) ══
fig, axes = plt.subplots(6, 1, figsize=(10, 14))

# Define OFF-window for y-axis scaling (post-artifact quiet region)
off_window_mask = (time_s < -0.05) | ((time_s >= 0.1) & (time_s <= 0.5))
# show off windows mask data shape and examples , not sums to understand its structure
print(f"Time axis shape: {time_s.shape}, OFF-window mask shape: {off_window_mask.shape}")
print(f"OFF-window mask example (first 20 samples): {off_window_mask[:20]}")

print(f"\nOFF-window mask: {off_window_mask.sum()} samples from {time_s[off_window_mask][0]:.2f} to {time_s[off_window_mask][-1]:.2f} s")
# ══ 3.2 Plot each channel with stim overlay ══
for idx, (ch_name, ax) in enumerate(zip(CHANNELS_TO_PLOT, axes)):
    # EEG on left y-axis
    color_eeg = "#08519c"
    ax.plot(time_s, eeg_mean_uv[idx], color=color_eeg, linewidth=1.5, label="EEG")
    ax.set_ylabel(f"{ch_name} (µV)", fontsize=10, fontweight="bold", color=color_eeg)
    ax.tick_params(axis="y", labelcolor=color_eeg)
    ax.grid(True, alpha=0.2)
    ax.axvline(0, color="gray", linestyle="--", alpha=0.5, linewidth=1)
    # Scale y-axis to OFF-window range (artifact clipped, signal visible)
    off_data = eeg_mean_uv[idx, off_window_mask]
    off_range = max(abs(off_data.min()), abs(off_data.max()))
    print(f"{ch_name} OFF-window range: {off_data.min():.2f} to {off_data.max():.2f} µV")
    ax.set_ylim(off_data.min()*0.995 , off_data.max()*1.005) 
    
    # Stim on right y-axis (secondary)
    ax_stim = ax.twinx()
    color_stim = "#e74c3c"
    ax_stim.plot(time_s, stim_mean, color=color_stim, linewidth=1.5, linestyle="--", label="Stim")
    ax_stim.set_ylabel("Stim (V)", fontsize=10, fontweight="bold", color=color_stim)
    ax_stim.tick_params(axis="y", labelcolor=color_stim)
    # Scale stim y-axis to OFF-window range (pulse clipped, recovery visible)
    stim_off_data = stim_mean[off_window_mask]
    ax_stim.set_ylim(stim_off_data.min() * 0.25, stim_off_data.max() * 1.75)  # add headroom for pulse visibility

    # GT on far-right y-axis (tertiary)
    ax_gt = ax.twinx()
    ax_gt.spines["right"].set_position(("outward", 60))  # offset third axis
    color_gt = "#2ca02c"
    gt_mean = gt_data.mean(axis=0)
    ax_gt.plot(time_s, gt_mean, color=color_gt, linewidth=1.5, linestyle=":", label="GT")
    ax_gt.set_ylabel("GT (µV)", fontsize=10, fontweight="bold", color=color_gt)
    ax_gt.tick_params(axis="y", labelcolor=color_gt)
    gt_off_data = gt_mean[off_window_mask]
    gt_range = max(abs(gt_off_data.min()), abs(gt_off_data.max()))
    ax_gt.set_ylim(-gt_range * 1.2, gt_range * 1.2)

    # Legend in top-left corner (all three axes)
    lines = ax.get_lines() + ax_stim.get_lines() + ax_gt.get_lines()
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, loc="upper left", fontsize=9)

# ══ 3.3 Plot ITPC summary (6th panel) ══
ax_itpc = axes[-1]
colors_itpc = ["#08519c", "#e74c3c", "#2ca02c", "#ff7f0e", "#9467bd"]
for ch_name, color in zip(CHANNELS_TO_PLOT, colors_itpc):
    ax_itpc.plot(time_s, itpc_by_channel[ch_name], label=ch_name, color=color, linewidth=1.5)
ax_itpc.axvline(0, color="gray", linestyle="--", alpha=0.5, linewidth=1)
ax_itpc.axhline(0.5, color="gray", linestyle=":", alpha=0.3, linewidth=1)
ax_itpc.set_ylabel("ITPC (vs GT)", fontsize=10, fontweight="bold")
ax_itpc.set_ylim(0, 1)
ax_itpc.grid(True, alpha=0.2)
ax_itpc.legend(loc="upper left", fontsize=8, ncol=5)

# ══ 3.4 Format bottom axis ══
axes[-1].set_xlabel("Time (s, centered on pulse)", fontsize=11, fontweight="bold")

# ══ 3.5 Add title ══
fig.suptitle("EXP08 @ 100% Intensity: 5-Channel Timecourse + ITPC + Stimulus", fontsize=13, fontweight="bold", y=0.995)

# ============================================================
# 4) SAVE & REPORT
# ============================================================

fig.tight_layout()
fig.savefig(OUTPUT_PATH, dpi=220, bbox_inches="tight")
plt.close()

print(f"\nSaved: {OUTPUT_PATH.name}")
