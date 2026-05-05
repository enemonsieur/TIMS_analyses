"""Compare baseline with and without GT: temporal profile and PSD."""
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne

# ── Config ──────────────────────────────────────────────────────
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
NO_GT_VHDR = DATA_DIR / "exp05-phantom-rs-GT-cTBS-run01.vhdr"
GT_VHDR = DATA_DIR / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
OUT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP05_baseline_comparison")
OUT.mkdir(parents=True, exist_ok=True)

BAND = (6.0, 8.0)
PSD_RANGE = (2.0, 15.0)
GT_PEAK = 7.08
N_CHANNELS = 5
EPOCH_DURATION = 5.0

# ── Load both datasets ──────────────────────────────────────────
raw_no_gt = mne.io.read_raw_brainvision(str(NO_GT_VHDR), preload=True, verbose="ERROR")
raw_no_gt.drop_channels([ch for ch in raw_no_gt.ch_names
                         if ch.lower() in ("stim", "ground_truth") or ch.startswith("STI")])
raw_no_gt.set_montage("standard_1020", on_missing="ignore")

raw_gt = mne.io.read_raw_brainvision(str(GT_VHDR), preload=True, verbose="ERROR")
raw_gt.drop_channels([ch for ch in raw_gt.ch_names
                      if ch.lower() in ("stim", "ground_truth") or ch.startswith("STI")])
raw_gt.set_montage("standard_1020", on_missing="ignore")

sfreq = raw_gt.info["sfreq"]
print(f"Loaded: no GT {raw_no_gt.n_times / sfreq:.1f}s, GT {raw_gt.n_times / sfreq:.1f}s, "
      f"{len(raw_gt.ch_names)} channels, sfreq={sfreq} Hz")

# ── Epochs and PSD (high resolution) ────────────────────────────
epochs_no_gt = mne.make_fixed_length_epochs(raw_no_gt, duration=EPOCH_DURATION, overlap=0.0,
                                             preload=True, verbose=False)
epochs_gt = mne.make_fixed_length_epochs(raw_gt, duration=EPOCH_DURATION, overlap=0.0,
                                         preload=True, verbose=False)

psd_no_gt = epochs_no_gt.compute_psd(method="welch", fmin=PSD_RANGE[0], fmax=PSD_RANGE[1],
                                      n_fft=int(EPOCH_DURATION * sfreq), verbose=False)
psd_gt = epochs_gt.compute_psd(method="welch", fmin=PSD_RANGE[0], fmax=PSD_RANGE[1],
                                n_fft=int(EPOCH_DURATION * sfreq), verbose=False)

# ── Fig 1: PSD comparison ───────────────────────────────────────
fig1, ax = plt.subplots(figsize=(10, 4))
for label, psd, color in [("No GT (run01)", psd_no_gt, "gray"), ("GT (run02)", psd_gt, "steelblue")]:
    mean_db = 10 * np.log10(psd.get_data().mean(axis=(0, 1)) + 1e-30)
    ax.plot(psd.freqs, mean_db, label=label, color=color, lw=1.5)
ax.axvline(GT_PEAK, color="red", lw=1.5, ls="--", alpha=.7, label=f"GT peak ({GT_PEAK} Hz)")
ax.axvspan(*BAND, alpha=.15, color="orange", label="Signal band")
ax.set_xlim(PSD_RANGE)
ax.set_xlabel("Frequency (Hz)", fontweight="bold")
ax.set_ylabel("Power (dB)", fontweight="bold")
ax.set_title("PSD: baseline with vs without GT (high resolution)")
ax.legend(fontsize=9)
ax.grid(alpha=0.25)
fig1.tight_layout()
fig1.savefig(OUT / "fig1_psd_comparison.png", dpi=200)
plt.close(fig1)
print(f"Saved -> {OUT / 'fig1_psd_comparison.png'}")

# ── Temporal profiles ───────────────────────────────────────────
raw_no_gt_band = raw_no_gt.copy().filter(*BAND, verbose=False)
raw_gt_band = raw_gt.copy().filter(*BAND, verbose=False)

epochs_no_gt_band = mne.make_fixed_length_epochs(raw_no_gt_band, duration=EPOCH_DURATION, overlap=0.0,
                                                  preload=True, verbose=False)
epochs_gt_band = mne.make_fixed_length_epochs(raw_gt_band, duration=EPOCH_DURATION, overlap=0.0,
                                              preload=True, verbose=False)

evoked_no_gt = epochs_no_gt_band.average()
evoked_gt = epochs_gt_band.average()

# Select top N_CHANNELS by RMS in GT evoked (most informative)
top_ch_indices = np.argsort(np.abs(evoked_gt.data).mean(axis=1))[-N_CHANNELS:][::-1]
top_ch_names = [evoked_gt.ch_names[i] for i in top_ch_indices]

# ── Fig 2: Temporal comparison ──────────────────────────────────
fig2, axes = plt.subplots(N_CHANNELS, 1, figsize=(10, 2.5 * N_CHANNELS), sharex=True)
for ax, ch in zip(axes, top_ch_names):
    ax.plot(evoked_no_gt.times, evoked_no_gt.copy().pick([ch]).data[0] * 1e6,
            label="No GT (run01)", color="gray", lw=1.5)
    ax.plot(evoked_gt.times, evoked_gt.copy().pick([ch]).data[0] * 1e6,
            label="GT (run02)", color="steelblue", lw=1.5)
    ax.axhline(0, color="black", lw=0.5, ls="--", alpha=0.3)
    ax.set_ylabel(f"{ch} (µV)", fontweight="bold", fontsize=9)
    ax.grid(alpha=0.25)
    if ax == axes[0]:
        ax.legend(fontsize=9, loc="upper right")

axes[-1].set_xlabel("Time (s)", fontweight="bold")
fig2.suptitle(f"Temporal profile: top {N_CHANNELS} channels (6–8 Hz band, {len(epochs_gt_band)} epochs)",
              fontweight="bold")
fig2.tight_layout()
fig2.savefig(OUT / "fig2_temporal_comparison.png", dpi=200)
plt.close(fig2)
print(f"Saved -> {OUT / 'fig2_temporal_comparison.png'}")

print("\nDone.")
