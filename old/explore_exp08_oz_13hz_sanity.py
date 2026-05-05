"""Is 13 Hz signal visible in raw Oz before ITPC? Compare 10% vs 100% intensity."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne

# ============================================================
# CONFIG
# ============================================================

EPOCH_DIR  = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIR = EPOCH_DIR

CHANNEL       = "Oz"
SIGNAL_BAND   = (11.0, 14.0)    # Hz — wider band: 330 ms ring time vs 2 s at 1 Hz width
CROP_WINDOW   = (-0.3, 1.5)     # s — centered on pulse onset
INTENSITIES   = [10, 100]       # pct — the two extremes to compare


# ============================================================
# 1) LOAD, FILTER, AVERAGE
# ============================================================

fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

for ax, pct in zip(axes, INTENSITIES):

    # ── EEG: Oz filtered to signal band ──
    epochs = mne.read_epochs(str(EPOCH_DIR / f"exp08_epochs_{pct}pct_on-epo.fif"),
                             preload=True, verbose=False)
    epochs.crop(*CROP_WINDOW)
    epochs_oz = epochs.copy().pick([CHANNEL])
    epochs_oz.filter(*SIGNAL_BAND, verbose=False)
    oz_mean = epochs_oz.get_data().mean(axis=0)[0] * 1e6   # → (n_samples,) µV, mean across 20 epochs

    # ── GT: filtered to same band ──
    gt_epochs = mne.read_epochs(str(EPOCH_DIR / f"exp08_gt_epochs_{pct}pct_on-epo.fif"),
                                preload=True, verbose=False)
    gt_epochs.crop(*CROP_WINDOW)
    gt_epochs.filter(*SIGNAL_BAND, picks="all", verbose=False)
    gt_mean = gt_epochs.get_data().mean(axis=0)[0] * 1e6   # → (n_samples,) µV

    time_s = epochs.times


    # ============================================================
    # 2) PLOT — dual y-axis (Oz and GT amplitudes differ)
    # ============================================================

    color_oz = "#1f77b4"
    color_gt = "#d62728"

    ax.plot(time_s, oz_mean, color=color_oz, linewidth=1.2, label=f"{CHANNEL} (13 Hz filtered)")
    ax.axvline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_ylabel(f"{CHANNEL} (µV)", color=color_oz)
    ax.tick_params(axis="y", labelcolor=color_oz)
    ax.set_title(f"{pct}% intensity  —  mean across 20 epochs", fontsize=11)
    ax.grid(True, alpha=0.2)

    ax_gt = ax.twinx()
    ax_gt.plot(time_s, gt_mean, color=color_gt, linewidth=1.2, linestyle="--", label="GT (13 Hz filtered)")
    ax_gt.set_ylabel("GT (µV)", color=color_gt)
    ax_gt.tick_params(axis="y", labelcolor=color_gt)

    # Combined legend
    lines = ax.get_lines() + ax_gt.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], loc="upper right", fontsize=9)

axes[-1].set_xlabel("Time relative to pulse (s)")
fig.suptitle("EXP08 — Oz vs GT, 13 Hz filtered: sanity check before ITPC", fontsize=12)

fig.tight_layout()
out_path = OUTPUT_DIR / "exp08_oz_13hz_sanity.png"
fig.savefig(out_path, dpi=150)
plt.close()

print(f"Saved: {out_path}")
