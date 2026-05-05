"""Power spectral density (PSD) across 10 intensities: compare Raw, SASS, and SSD paths.

Single-pulse dose-response (10–100%) with fixed raw channel (10%), per-intensity SASS,
and per-intensity SSD. Visualize 13 Hz signal peak behavior across intensity levels.
"""

import os
from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy import linalg

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import preprocessing
import sass


# ============================================================
# CONFIG
# ============================================================

EPOCH_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY = EPOCH_DIRECTORY
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]

ON_WINDOW_S = (-0.1, 0.5)
LATE_OFF_WINDOW_S = (1.5, 3.2)

N_FFT = 512  # Welch PSD FFT length (500 ms window, 1000 Hz sfreq)

TARGET_CENTER_HZ = 13.0
SIGNAL_HALF_WIDTH_HZ = 0.5
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
VIEW_BAND_HZ = (4.0, 20.0)
N_SSD_COMPONENTS = 6

PSD_FIGURE_PATH = OUTPUT_DIRECTORY / "exp08_psd_by_method.png"


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Pre-extracted epochs (10 intensities, 2 windows, 28 EEG channels, 1000 Hz)
# ├─ ON epochs: -0.1 to +0.5 s (stimulus + recovery)
# └─ late-OFF epochs: 1.5 to 3.2 s (noise baseline)
#        │
#        ├─────────────┬──────────────┬──────────────┐
#        ▼             ▼              ▼              ▼
#    RAW PATH     SASS PATH       SSD PATH
#    (fixed ch)   (covariance)    (eigendecomp)
#        │             │              │
#        └─────────────┴──────────────┘
#                      │
#         10×3 grid: PSD by intensity & method


# ============================================================
# 1) LOAD PRE-EXTRACTED EPOCHS
# ============================================================

print("Loading pre-extracted epochs...")
epochs_on_all = {}
epochs_lateoff_all = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 1.1 Load ON epochs ══
    epochs_on_path = EPOCH_DIRECTORY / f"exp08_epochs_{intensity_pct}pct_on-epo.fif"
    epochs_on = mne.read_epochs(str(epochs_on_path), preload=True, verbose=False)
    epochs_on_all[intensity_pct] = epochs_on

    # ══ 1.2 Load late-OFF epochs ══
    epochs_lateoff_path = EPOCH_DIRECTORY / f"exp08_epochs_{intensity_pct}pct_lateoff-epo.fif"
    epochs_lateoff = mne.read_epochs(str(epochs_lateoff_path), preload=True, verbose=False)
    epochs_lateoff_all[intensity_pct] = epochs_lateoff

    print(f"  {label}: {len(epochs_on)} ON epochs, {len(epochs_lateoff)} late-OFF epochs")

sfreq = float(epochs_on.info["sfreq"])
channel_names = epochs_on.ch_names
print(f"\nLoaded: {sfreq:.0f} Hz, {len(channel_names)} EEG channels")


# ============================================================
# 2) RAW PATH (FIXED CHANNEL AT 10%)
# ============================================================

print("\nRaw path: detecting best channel at 10%...")

# ══ 2.1 Detect best channel @ 10% intensity ══
on_data_10pct = epochs_on_all[10].get_data()  # (20, 28, 600) µV
snr_scores_10pct = []
for ch_idx, ch_name in enumerate(channel_names):
    ch_data_10pct = on_data_10pct[:, ch_idx, :]  # (20, 600)
    snr = preprocessing.compute_snr_linear(ch_data_10pct, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
    snr_scores_10pct.append((ch_name, float(snr)))

best_channel_name = max(snr_scores_10pct, key=lambda x: x[1])[0]
best_channel_idx = channel_names.index(best_channel_name)
print(f"  Best channel: {best_channel_name}")

# ══ 2.2 Compute PSD per intensity ══
raw_psd_by_intensity = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    on_data = epochs_on_all[intensity_pct].get_data()[:, best_channel_idx, :]  # (20, 600)
    freqs, psd = preprocessing.compute_mean_epoch_psd(on_data, sfreq, VIEW_BAND_HZ, N_FFT)
    raw_psd_by_intensity[intensity_pct] = (freqs, psd)


# ============================================================
# 3) SASS PATH (COVARIANCE-BASED ARTIFACT SUPPRESSION)
# ============================================================

print("\nSASS path: computing PSD per intensity...")
sass_psd_by_intensity = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 3.1 Get filtered data for covariance ══
    on_data = epochs_on_all[intensity_pct].copy().filter(*VIEW_BAND_HZ, verbose=False, l_trans_bandwidth=0.5, h_trans_bandwidth=0.5).get_data()
    lateoff_data = epochs_lateoff_all[intensity_pct].copy().filter(*VIEW_BAND_HZ, verbose=False, l_trans_bandwidth=0.5, h_trans_bandwidth=0.5).get_data()

    # ══ 3.2 Compute covariance matrices ══
    n_epochs_on, n_channels, n_samples_on = on_data.shape
    n_epochs_off, _, n_samples_off = lateoff_data.shape

    on_concat = on_data.transpose(1, 0, 2).reshape(n_channels, -1)
    lateoff_concat = lateoff_data.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_on = np.cov(on_concat)
    cov_lateoff = np.cov(lateoff_concat)

    # ══ 3.3 Apply SASS and rank channels ══
    sass_concat = sass.sass(on_concat, cov_on, cov_lateoff)
    sass_data = sass_concat.reshape(n_channels, n_epochs_on, n_samples_on).transpose(1, 0, 2)

    gt_on = epochs_on_all[intensity_pct].get_data() * 0  # dummy for SNR ranking
    sass_snr_scores = []
    for ch_idx, ch_name in enumerate(channel_names):
        ch_sass_data = sass_data[:, ch_idx, :]
        snr = preprocessing.compute_snr_linear(ch_sass_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        sass_snr_scores.append((ch_name, float(snr), ch_sass_data))

    best_sass_ch_name, best_sass_snr, best_sass_data = max(sass_snr_scores, key=lambda x: x[1])

    # ══ 3.4 Compute PSD on best SASS channel ══
    freqs, psd = preprocessing.compute_mean_epoch_psd(best_sass_data, sfreq, VIEW_BAND_HZ, N_FFT)
    sass_psd_by_intensity[intensity_pct] = (freqs, psd)


# ============================================================
# 4) SSD PATH (SIGNAL DOMINANCE VIA EIGENDECOMPOSITION)
# ============================================================

print("\nSSD path: computing PSD per intensity...")
ssd_psd_by_intensity = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 4.1 Prepare signal and view band data ══
    on_data_full = epochs_on_all[intensity_pct].get_data()  # (20, 28, 600)
    on_data_flat = on_data_full.transpose(1, 0, 2).reshape(on_data_full.shape[1], -1)  # (28, 12000)

    on_signal = preprocessing.filter_signal(on_data_flat, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    on_view = preprocessing.filter_signal(on_data_flat, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    # ══ 4.2 Eigendecompose signal vs view ══
    cov_signal = np.cov(on_signal)
    cov_view = np.cov(on_view)

    evals, evecs = linalg.eig(cov_signal, cov_view)
    idx = np.argsort(np.real(evals))[::-1]
    evals, evecs = np.real(evals[idx]), evecs[:, idx]
    W = evecs.T[:N_SSD_COMPONENTS]  # (N_SSD_COMPONENTS, 28)

    # ══ 4.3 Rank components by SNR ══
    ssd_snr_scores = []
    for comp_idx in range(W.shape[0]):
        comp_data = W[comp_idx] @ on_data_flat
        comp_epochs = comp_data.reshape(on_data_full.shape[0], -1)
        snr = preprocessing.compute_snr_linear(comp_epochs, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        ssd_snr_scores.append((comp_idx, float(snr), comp_epochs))

    best_ssd_comp_idx, best_ssd_snr, best_ssd_data = max(ssd_snr_scores, key=lambda x: x[1])

    # ══ 4.4 Compute PSD on best SSD component ══
    freqs, psd = preprocessing.compute_mean_epoch_psd(best_ssd_data, sfreq, VIEW_BAND_HZ, N_FFT)
    ssd_psd_by_intensity[intensity_pct] = (freqs, psd)


# ============================================================
# 5) PLOT 10×3 GRID
# ============================================================

print("\nGenerating PSD figure...")

intensity_pcts = [int(level * 100) for level in INTENSITY_LEVELS]
fig, axes = plt.subplots(
    len(intensity_pcts), 3,
    figsize=(14, 22),
    constrained_layout=True,
    sharex=True,
    sharey="row"  # share y-axis within each row only
)

for row, (intensity_pct, label) in enumerate(zip(intensity_pcts, INTENSITY_LABELS)):
    # ── Column 0: Raw ──
    freqs_raw, psd_raw = raw_psd_by_intensity[intensity_pct]
    psd_raw_db = 10 * np.log10(psd_raw + 1e-12)
    axes[row, 0].plot(freqs_raw, psd_raw_db, color="#1f77b4", lw=1.5)
    axes[row, 0].axvline(TARGET_CENTER_HZ, color="red", linestyle=":", alpha=0.5, linewidth=1.0)
    axes[row, 0].grid(True, alpha=0.1, linestyle=":", linewidth=0.5)
    if row == 0:
        axes[row, 0].set_title("Raw (fixed channel)", fontsize=11, fontweight="bold")
    axes[row, 0].set_ylabel(label, fontsize=9, color="#333")

    # ── Column 1: SASS ──
    freqs_sass, psd_sass = sass_psd_by_intensity[intensity_pct]
    psd_sass_db = 10 * np.log10(psd_sass + 1e-12)
    axes[row, 1].plot(freqs_sass, psd_sass_db, color="#ff7f0e", lw=1.5)
    axes[row, 1].axvline(TARGET_CENTER_HZ, color="red", linestyle=":", alpha=0.5, linewidth=1.0)
    axes[row, 1].grid(True, alpha=0.1, linestyle=":", linewidth=0.5)
    if row == 0:
        axes[row, 1].set_title("SASS", fontsize=11, fontweight="bold")
    axes[row, 1].set_ylabel("")

    # ── Column 2: SSD ──
    freqs_ssd, psd_ssd = ssd_psd_by_intensity[intensity_pct]
    psd_ssd_db = 10 * np.log10(psd_ssd + 1e-12)
    axes[row, 2].plot(freqs_ssd, psd_ssd_db, color="#2ca02c", lw=1.5)
    axes[row, 2].axvline(TARGET_CENTER_HZ, color="red", linestyle=":", alpha=0.5, linewidth=1.0)
    axes[row, 2].grid(True, alpha=0.1, linestyle=":", linewidth=0.5)
    if row == 0:
        axes[row, 2].set_title("SSD", fontsize=11, fontweight="bold")
    axes[row, 2].set_ylabel("")

# ── Set x-axis label ──
axes[-1, 0].set_xlabel("Frequency (Hz)", fontsize=11, fontweight="bold")
axes[-1, 1].set_xlabel("Frequency (Hz)", fontsize=11, fontweight="bold")
axes[-1, 2].set_xlabel("Frequency (Hz)", fontsize=11, fontweight="bold")

# ── Set y-axis label globally ──
fig.supylabel("Power (dB µV²/Hz)", fontsize=11, fontweight="bold", x=0.00)

fig.suptitle(
    "Power Spectral Density: Single-Pulse Dose-Response (Raw vs. SASS vs. SSD)",
    fontsize=13, fontweight="bold", y=0.995
)

fig.savefig(PSD_FIGURE_PATH, dpi=220)
plt.close(fig)
print(f"  Saved: {PSD_FIGURE_PATH.name}")

print("\n" + "=" * 80)
print("EXP08 PSD ANALYSIS COMPLETE")
print("=" * 80)
print(f"\nOutput: {PSD_FIGURE_PATH}")
