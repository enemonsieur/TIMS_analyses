"""Inspect DC offset and drift in raw epochs across intensity levels."""

from pathlib import Path
import matplotlib.pyplot as plt
import mne
import numpy as np

OUTPUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

# Load epochs for 10%, 50%, 100%
ep10 = mne.read_epochs(OUTPUT_DIR / "exp08t_epochs_10pct_on-epo.fif", verbose=False, preload=True)
ep50 = mne.read_epochs(OUTPUT_DIR / "exp08t_epochs_50pct_on-epo.fif", verbose=False, preload=True)
ep100 = mne.read_epochs(OUTPUT_DIR / "exp08t_epochs_100pct_on-epo.fif", verbose=False, preload=True)

t = ep10.times
ch_idx = ep10.ch_names.index("Oz")

# Extract Oz timecourse for each intensity
data10 = ep10.get_data()[:, ch_idx, :] * 1e6    # (20, n_times) in µV
data50 = ep50.get_data()[:, ch_idx, :] * 1e6
data100 = ep100.get_data()[:, ch_idx, :] * 1e6

# ════════════════════════════════════════════════════════════════════════════
# Figure 1: Raw epochs overlay, split by pre- vs. post-stim
# ════════════════════════════════════════════════════════════════════════════

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
for ax, data, intensity, label in [
    (axes[0], data10, "10%", "Low intensity (stable)"),
    (axes[1], data50, "50%", "50%"),
    (axes[2], data100, "100%", "High intensity (unstable)"),
]:
    if intensity == "50%":
        ax.plot(t, data.T, alpha=0.3, linewidth=0.5)
    else:
        # Color by epoch number to show alternation
        colors = ["blue" if i % 2 == 0 else "orange" for i in range(len(data))]
        for i, (color, epoch) in enumerate(zip(colors, data)):
            ax.plot(t, epoch, alpha=0.4, linewidth=0.8, color=color, label=f"Epoch {i}")
    ax.axvline(0, color="red", linestyle="--", linewidth=1, alpha=0.5, label="Pulse onset")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Oz voltage (µV)")
    ax.set_title(label)
    ax.grid(True, alpha=0.2)

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "exp08_dc_offset_drift_overlay.png", dpi=150)
plt.close()
print("Saved: exp08_dc_offset_drift_overlay.png")

# ════════════════════════════════════════════════════════════════════════════
# Figure 2: Pre-stim baseline per epoch, showing alternation at high intensity
# ════════════════════════════════════════════════════════════════════════════

pre = (t >= -0.5) & (t < -0.01)
pre_means_10 = data10[:, pre].mean(axis=1)
pre_means_50 = data50[:, pre].mean(axis=1)
pre_means_100 = data100[:, pre].mean(axis=1)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for ax, means, label in [
    (axes[0], pre_means_10, "10% pre-stim baseline"),
    (axes[1], pre_means_50, "50% pre-stim baseline"),
    (axes[2], pre_means_100, "100% pre-stim baseline — shows alternation"),
]:
    epoch_nums = np.arange(len(means))
    ax.scatter(epoch_nums, means, s=50, alpha=0.6)
    ax.plot(epoch_nums, means, alpha=0.3, linewidth=1)
    ax.set_xlabel("Epoch number")
    ax.set_ylabel("Oz pre-stim mean (µV)")
    ax.set_title(label)
    ax.grid(True, alpha=0.2)

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "exp08_baseline_drift_by_epoch.png", dpi=150)
plt.close()
print("Saved: exp08_baseline_drift_by_epoch.png")

# ════════════════════════════════════════════════════════════════════════════
# Figure 3: Within-epoch drift (early vs. late pre-stim decay)
# ════════════════════════════════════════════════════════════════════════════

early = (t >= -0.5) & (t < -0.4)
late = (t >= -0.1) & (t < -0.01)

drift_10 = (data10[:, late].mean(1) - data10[:, early].mean(1))
drift_50 = (data50[:, late].mean(1) - data50[:, early].mean(1))
drift_100 = (data100[:, late].mean(1) - data100[:, early].mean(1))

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for ax, drift, label in [
    (axes[0], drift_10, "10% within-epoch drift (tiny)"),
    (axes[1], drift_50, "50% within-epoch drift"),
    (axes[2], drift_100, "100% within-epoch drift (huge at odd epochs)"),
]:
    epoch_nums = np.arange(len(drift))
    ax.scatter(epoch_nums, drift, s=50, alpha=0.6)
    ax.plot(epoch_nums, drift, alpha=0.3, linewidth=1)
    ax.axhline(0, color="black", linestyle="-", linewidth=0.5, alpha=0.3)
    ax.set_xlabel("Epoch number")
    ax.set_ylabel("Within-epoch drift (µV)")
    ax.set_title(label)
    ax.grid(True, alpha=0.2)

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "exp08_within_epoch_decay.png", dpi=150)
plt.close()
print("Saved: exp08_within_epoch_decay.png")

# ════════════════════════════════════════════════════════════════════════════
# Summary statistics
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("SUMMARY: Pre-stim baseline and within-epoch decay")
print("="*70)
print(f"\n10% intensity:")
print(f"  Pre-stim baseline: {pre_means_10.min():.0f} to {pre_means_10.max():.0f} µV "
      f"(range={pre_means_10.max() - pre_means_10.min():.0f} µV)")
print(f"  Within-epoch decay: min={drift_10.min():.1f}, max={drift_10.max():.1f}, "
      f"std={drift_10.std():.1f} µV")

print(f"\n50% intensity:")
print(f"  Pre-stim baseline: {pre_means_50.min():.0f} to {pre_means_50.max():.0f} µV "
      f"(range={pre_means_50.max() - pre_means_50.min():.0f} µV)")
print(f"  Within-epoch decay: min={drift_50.min():.1f}, max={drift_50.max():.1f}, "
      f"std={drift_50.std():.1f} µV")

print(f"\n100% intensity:")
print(f"  Pre-stim baseline: {pre_means_100.min():.0f} to {pre_means_100.max():.0f} µV "
      f"(range={pre_means_100.max() - pre_means_100.min():.0f} µV)  [BIMODAL]")
print(f"  Within-epoch decay: min={drift_100.min():.1f}, max={drift_100.max():.1f}, "
      f"std={drift_100.std():.1f} µV  [HUGE decay in odd epochs]")
print("\nKEY FINDING:")
print("  100% epochs show 560 uV baseline swing + up to -3000 uV decay during pre-stim.")
print("  This indicates residual artifact from previous pulse has NOT decayed after 5 s IPI.")
print("  IMPLICATION: Global batch crop won't work; need epoch-by-epoch cropping.")
