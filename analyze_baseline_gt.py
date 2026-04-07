"""Baseline GT signal: spectral, spatial, and temporal views using MNE builtins."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne

# ── Config ──────────────────────────────────────────────────────
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
VHDR = DATA_DIR / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
OUT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP05_baseline_gt_analysis")
OUT.mkdir(parents=True, exist_ok=True)

BAND = (6.0, 8.0)          # signal band of interest (Hz)
PSD_RANGE = (2.0, 15.0)    # frequency range for PSD plots
GT_PEAK = 7.08             # known GT peak frequency

# ── Load & prepare ──────────────────────────────────────────────
raw = mne.io.read_raw_brainvision(str(VHDR), preload=True, verbose="ERROR")
non_eeg = [ch for ch in raw.ch_names
           if ch.lower() in ("stim", "ground_truth") or ch.startswith("STI")]
raw.drop_channels(non_eeg)
raw.set_montage("standard_1020", on_missing="ignore")

print(f"Loaded: {raw.n_times / raw.info['sfreq']:.1f}s, "
      f"{len(raw.ch_names)} channels, sfreq={raw.info['sfreq']} Hz")

# ── Epochs (5s, dense stride) ──────────────────────────────────
epochs = mne.make_fixed_length_epochs(raw, duration=5.0, overlap=0.0,
                                       preload=True, verbose=False)
print(f"Epochs: {len(epochs)} × 5.0 s")

# ── PSD object (reused for spectral + spatial) ─────────────────
psd = epochs.compute_psd(method="welch", fmin=PSD_RANGE[0], fmax=PSD_RANGE[1],
                          verbose=False, n_fft=int(epochs.info["sfreq"] * 5.0), n_overlap=0)

# ── Fig 1: Spectral — PSD averaged across channels ─────────────
fig1 = psd.plot(average=True, show=False, ci=None)
ax = fig1.axes[0]
ax.axvline(GT_PEAK, color="red", lw=1.5, ls="--", alpha=.7, label=f"GT peak ({GT_PEAK} Hz)")
ax.axvspan(*BAND, alpha=.15, color="orange", label="Signal band")
ax.legend(fontsize=9)
ax.set_title("Baseline PSD (channel average)")
fig1.savefig(OUT / "baseline_gt_psd.png", dpi=200)
plt.close(fig1)

# ── Fig 2: Spectral — PSD per channel ──────────────────────────
fig2 = psd.plot(average=True, show=False, ci=None)
ax = fig2.axes[0]
ax.axvline(GT_PEAK, color="red", lw=1.5, ls="--", alpha=.7)
ax.axvspan(*BAND, alpha=.15, color="orange")
ax.set_title("Baseline PSD (individual channels)")
fig2.savefig(OUT / "baseline_gt_psd_channels.png", dpi=200)
plt.close(fig2)

# ── Fig 3: Spatial — topomap of band power ─────────────────────
fig3 = psd.plot_topomap(bands={"6–8 Hz": BAND}, show=False)
fig3.savefig(OUT / "baseline_gt_topomap.png", dpi=200, bbox_inches="tight")
plt.close(fig3)

# ── Fig 4: Temporal — evoked (band-filtered) ───────────────────
raw_band = raw.copy().filter(*BAND, verbose=False)
epochs_band = mne.make_fixed_length_epochs(raw_band, duration=5.0, overlap=0.0,
                                            preload=True, verbose=False)
evoked = epochs_band.average()
fig4 = evoked.plot(picks="C4", show=False, spatial_colors=True)
fig4.suptitle("Baseline evoked (6–8 Hz band)", fontweight="bold")
fig4.savefig(OUT / "baseline_gt_temporal_profile.png", dpi=200)
plt.close(fig4)

# ── Fig 5: Spatial — topomap of RMS across time ────────────────
fig5 = evoked.plot_topomap(times="auto", show=False)
fig5.savefig(OUT / "baseline_gt_topomap_rms.png", dpi=200, bbox_inches="tight")
plt.close(fig5)

# ── Fig 6: Spectral × Spatial — PSD heatmap per channel ────────
fig6 = psd.plot(average=False, show=False)
ax = fig6.axes[0]
ax.axvline(GT_PEAK, color="red", lw=2, ls="--", alpha=.7)
ax.set_title("PSD heatmap per channel (baseline)")
fig6.savefig(OUT / "baseline_gt_psd_heatmap.png", dpi=200)
plt.close(fig6)

print(f"\nAll figures saved to {OUT}")
