"""Recover ground-truth signal across 10 intensity levels using raw, SASS, and SSD spatial filters.

Compare three artifact suppression paths ranked by SNR: fixed raw channel (locked at 10%),
SASS (covariance-based artifact subtraction), and SSD (signal-dominance eigendecomposition).
Visualize ITPC recovery timecourse and SNR per path per intensity.
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

import plot_helpers
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

ON_WINDOW_S = (-0.5, 1.0)
LATE_OFF_WINDOW_S = (1.5, 3.2)
ITPC_WINDOW_S = (-0.2, 0.3)  # window used for ITPC/PLV computation

TARGET_CENTER_HZ = 13.0 # TODO: our current target is 13Hz, not 12
SIGNAL_HALF_WIDTH_HZ = 0.5
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
VIEW_BAND_HZ = (4.0, 20.0)
N_SSD_COMPONENTS = 6

METHOD_COLORS = {
    "raw": "#1f77b4",         # muted blue
    "sass": "#ff7f0e",        # muted orange
    "ssd": "#2ca02c",         # muted green
    "gt_ref": "#d62728",      # red for reference
}

ITPC_TIMECOURSE_FIGURE_PATH = OUTPUT_DIRECTORY / "exp08_art_filtering_itpc_timecourse_by_intensity.png"
ITPC_SUMMARY_FIGURE_PATH = OUTPUT_DIRECTORY / "exp08_art_filtering_itpc_summary.png"
PLV_SUMMARY_FIGURE_PATH = OUTPUT_DIRECTORY / "exp08_art_filtering_plv_summary.png"
PHASE_GRID_PATH = OUTPUT_DIRECTORY / "exp08_art_filtering_phase_grid.png"
MANIFEST_PATH = OUTPUT_DIRECTORY / "exp08_art_filtering_summary.txt"


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Pre-extracted epochs (10 intensities, 2 windows, 2 traces)
# ├─ ON epochs (28 EEG, 20×28×601 per intensity)
# ├─ late-OFF epochs (28 EEG, 20×28×601 per intensity)
# ├─ GT ON epochs (1 channel, 20×1×601 per intensity)
# └─ GT late-OFF epochs (1 channel, 20×1×601 per intensity)
#        │
#        ├─ Covariance matrices (ON vs. late-OFF per intensity)
#        │
#        ├─────────────┬──────────────┬──────────────┐
#        ▼             ▼              ▼              ▼
#    RAW PATH     SASS PATH       SSD PATH      GT REFERENCE
#    (fixed ch)   (covariance)    (eigendecomp) (per intensity)
#        │             │              │              │
#        └─────────────┴──────────────┴──────────────┘
#                      │
#            SNR rank & ITPC per path
#                      │
#    ┌─────────────────┴─────────────────┐
#    ▼                                   ▼
#  ITPC course figure              SNR course figure
#  (3 lines: raw/SASS/SSD)         (3 lines: raw/SASS/SSD)
#


# ============================================================
# 1) LOAD PRE-EXTRACTED EPOCHS
# ============================================================

print("Loading pre-extracted epochs...")
epochs_on_all = {}
epochs_lateoff_all = {}
gt_on_all = {}
gt_lateoff_all = {}
stim_on_all = {}
stim_lateoff_all = {}

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

    # ══ 1.3 Load GT ON epochs ══
    gt_on_path = EPOCH_DIRECTORY / f"exp08_gt_epochs_{intensity_pct}pct_on-epo.fif"
    gt_on = mne.read_epochs(str(gt_on_path), preload=True, verbose=False)
    gt_on_all[intensity_pct] = gt_on

    # ══ 1.4 Load GT late-OFF epochs ══
    gt_lateoff_path = EPOCH_DIRECTORY / f"exp08_gt_epochs_{intensity_pct}pct_lateoff-epo.fif"
    gt_lateoff = mne.read_epochs(str(gt_lateoff_path), preload=True, verbose=False)
    gt_lateoff_all[intensity_pct] = gt_lateoff

    # ══ 1.5 Load stimulus ON epochs ══
    stim_on_path = EPOCH_DIRECTORY / f"exp08_stim_epochs_{intensity_pct}pct_on-epo.fif"
    stim_on = mne.read_epochs(str(stim_on_path), preload=True, verbose=False)
    stim_on_all[intensity_pct] = stim_on

    # ══ 1.6 Load stimulus late-OFF epochs ══
    stim_lateoff_path = EPOCH_DIRECTORY / f"exp08_stim_epochs_{intensity_pct}pct_lateoff-epo.fif"
    stim_lateoff = mne.read_epochs(str(stim_lateoff_path), preload=True, verbose=False)
    stim_lateoff_all[intensity_pct] = stim_lateoff

    print(f"  {label}: {len(epochs_on)} ON epochs, {len(epochs_lateoff)} late-OFF epochs")

sfreq = float(epochs_on.info["sfreq"])
print(f"\nLoaded: {sfreq:.0f} Hz, {len(epochs_on.ch_names)} EEG channels")


# ============================================================
# 2) PREPARE COVARIANCE MATRICES (per-intensity baseline)
# ============================================================

print("\nComputing covariance matrices...")
cov_on_by_intensity = {}
cov_lateoff_by_intensity = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 2.1 Extract and filter ON/late-OFF epochs ══
    on_data = epochs_on_all[intensity_pct].copy().filter(*VIEW_BAND_HZ, verbose=False).get_data()
    lateoff_data = epochs_lateoff_all[intensity_pct].copy().filter(*VIEW_BAND_HZ, verbose=False).get_data()

    # ══ 2.2 Compute mean covariance (concatenate all epochs across channel-time) ══
    n_epochs_on, n_channels, n_samples_on = on_data.shape
    n_epochs_off, _, n_samples_off = lateoff_data.shape

    on_concat = on_data.transpose(1, 0, 2).reshape(n_channels, -1)
    lateoff_concat = lateoff_data.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_on = np.cov(on_concat)
    cov_lateoff = np.cov(lateoff_concat)

    cov_on_by_intensity[intensity_pct] = cov_on
    cov_lateoff_by_intensity[intensity_pct] = cov_lateoff


# ============================================================
# 3) RAW CHANNEL PATH (FIXED AT 10%)
# ============================================================

print("\nRaw channel path: detecting best channel at 10%...")

# ══ 3.1 Detect best channel @ 10% intensity ══
on_data_10pct = epochs_on_all[10].get_data()  # (20, 28, 601) µV
gt_on_10pct = gt_on_all[10].get_data().squeeze()  # (20, 601) µV
channel_names = epochs_on_all[10].ch_names

snr_scores_10pct = []
for ch_idx, ch_name in enumerate(channel_names):
    ch_data_10pct = on_data_10pct[:, ch_idx, :]  # (20, 601)
    snr = preprocessing.compute_snr_linear(ch_data_10pct, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
    snr_scores_10pct.append((ch_name, float(snr)))

best_channel_name = max(snr_scores_10pct, key=lambda x: x[1])[0]
best_channel_idx = channel_names.index(best_channel_name)
print(f"  Best channel: {best_channel_name} (SNR={snr_scores_10pct[best_channel_idx][1]:.3f})")

# ══ 3.2 Lock and analyze across all intensities ══
raw_snr_by_intensity = []
raw_itpc_curves = {}  # timecourse per intensity

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    on_data = epochs_on_all[intensity_pct].get_data()[:, best_channel_idx, :]  # (20, 601)
    gt_on = gt_on_all[intensity_pct].get_data().squeeze()  # (20, 601)

    snr = preprocessing.compute_snr_linear(on_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
    itpc_curve = preprocessing.compute_itpc_timecourse(on_data, gt_on, sfreq, SIGNAL_BAND_HZ)

    raw_snr_by_intensity.append(float(snr))
    raw_itpc_curves[intensity_pct] = itpc_curve


# ============================================================
# 4) SASS PATH (COVARIANCE-BASED ARTIFACT SUPPRESSION)
# ============================================================

print("\nSASS path: applying covariance-based artifact suppression...")
sass_snr_by_intensity = []
sass_itpc_curves = {}  # timecourse per intensity
sass_channels_by_intensity = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 4.1 Get covariance matrices ══
    cov_on = cov_on_by_intensity[intensity_pct]
    cov_lateoff = cov_lateoff_by_intensity[intensity_pct]

    # ══ 4.2 Apply SASS ══
    on_data = epochs_on_all[intensity_pct].copy().filter(*VIEW_BAND_HZ, verbose=False).get_data()
    n_epochs, n_channels, n_samples = on_data.shape
    on_concat = on_data.transpose(1, 0, 2).reshape(n_channels, -1)

    sass_concat = sass.sass(on_concat, cov_on, cov_lateoff)
    sass_data = sass_concat.reshape(n_channels, n_epochs, n_samples).transpose(1, 0, 2)

    # ══ 4.3 Rank all SASS-cleaned channels by SNR ══
    gt_on = gt_on_all[intensity_pct].get_data().squeeze()

    sass_snr_scores = []
    for ch_idx, ch_name in enumerate(channel_names):
        ch_sass_data = sass_data[:, ch_idx, :]
        snr = preprocessing.compute_snr_linear(ch_sass_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        sass_snr_scores.append((ch_name, float(snr), ch_sass_data))

    # ══ 4.4 Select best SASS channel by SNR ══
    best_sass_ch_name, best_sass_snr, best_sass_data = max(sass_snr_scores, key=lambda x: x[1])
    sass_channels_by_intensity[intensity_pct] = best_sass_ch_name

    itpc_curve = preprocessing.compute_itpc_timecourse(best_sass_data, gt_on, sfreq, SIGNAL_BAND_HZ)

    sass_snr_by_intensity.append(best_sass_snr)
    sass_itpc_curves[intensity_pct] = itpc_curve


# ============================================================
# 5) SSD PATH (SIGNAL DOMINANCE VIA EIGENDECOMPOSITION)
# ============================================================

print("\nSSD path: eigendecomposing signal vs. view bands...")
ssd_snr_by_intensity = []
ssd_itpc_curves = {}  # timecourse per intensity
ssd_components_by_intensity = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 5.1 Load raw data and filter to signal/view bands ══
    on_data_full = epochs_on_all[intensity_pct].get_data()  # (20, 28, 601)

    # Manual SSD: compute covariance in signal and view bands
    # Flatten all epochs to (28 channels, 20*601 samples) for covariance
    on_data_flat = on_data_full.transpose(1, 0, 2).reshape(on_data_full.shape[1], -1)  # (28, 12020)

    on_signal = preprocessing.filter_signal(on_data_flat, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    on_view = preprocessing.filter_signal(on_data_flat, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_signal_concat = on_signal
    on_view_concat = on_view

    cov_signal = np.cov(on_signal_concat)
    cov_view = np.cov(on_view_concat)

    # ══ 5.2 Eigendecompose and rank components by SNR ══
    evals, evecs = linalg.eig(cov_signal, cov_view)
    idx = np.argsort(np.real(evals))[::-1]
    evals, evecs = np.real(evals[idx]), evecs[:, idx]
    W = evecs.T[:N_SSD_COMPONENTS]  # (N_SSD_COMPONENTS, n_channels) spatial filters

    # ══ 5.3 Extract components and rank by SNR ══
    gt_on = gt_on_all[intensity_pct].get_data().squeeze()

    ssd_snr_scores = []
    for comp_idx in range(W.shape[0]):
        comp_data = W[comp_idx] @ on_data_full.transpose(1, 0, 2).reshape(on_data_full.shape[1], -1)
        comp_epochs = comp_data.reshape(on_data_full.shape[0], -1)

        snr = preprocessing.compute_snr_linear(comp_epochs, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        ssd_snr_scores.append((comp_idx, float(snr), comp_epochs))

    # ══ 5.4 Select best SSD component by SNR ══
    best_ssd_comp_idx, best_ssd_snr, best_ssd_data = max(ssd_snr_scores, key=lambda x: x[1])
    ssd_components_by_intensity[intensity_pct] = best_ssd_comp_idx

    itpc_curve = preprocessing.compute_itpc_timecourse(best_ssd_data, gt_on, sfreq, SIGNAL_BAND_HZ)

    ssd_snr_by_intensity.append(best_ssd_snr)
    ssd_itpc_curves[intensity_pct] = itpc_curve


# ============================================================
# 6) STIMULUS REFERENCE (NEGATIVE CONTROL - LOW ITPC EXPECTED)
# ============================================================

print("\nComputing stimulus reference curves (GT vs stim)...")
stim_itpc_curves = {}  # GT vs stim (should be LOW, confirming separation)

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 6.1 GT vs stimulus as negative control ══
    gt_on = gt_on_all[intensity_pct].get_data().squeeze()  # (20, 601)
    stim_on = stim_on_all[intensity_pct].get_data().squeeze()  # (20, 601)

    itpc_curve_stim = preprocessing.compute_itpc_timecourse(gt_on, stim_on, sfreq, SIGNAL_BAND_HZ)
    stim_itpc_curves[intensity_pct] = itpc_curve_stim


# ============================================================
# 7) COMPUTE PLV ON ON-WINDOWS
# ============================================================

print("\nComputing PLV on ON windows...")

# Determine reference peak frequency from 10% intensity GT
gt_on_10pct = gt_on_all[10].get_data().squeeze()
gt_signal = preprocessing.filter_signal(gt_on_10pct, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
gt_psd = np.mean(np.abs(np.fft.rfft(gt_signal, axis=-1)) ** 2, axis=0)
freqs = np.fft.rfftfreq(gt_signal.shape[-1], 1 / sfreq)
target_peak_hz = freqs[np.argmax(gt_psd)]

raw_plv_by_intensity = []
sass_plv_by_intensity = []
ssd_plv_by_intensity = []
stim_plv_by_intensity = []

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # ══ 7.1 Extract ON window data ══
    on_data = epochs_on_all[intensity_pct].get_data()  # (20, 28, 601)
    gt_on = gt_on_all[intensity_pct].get_data().squeeze()  # (20, 601)
    stim_on = stim_on_all[intensity_pct].get_data().squeeze()  # (20, 601)

    # ══ 7.2 Compute raw PLV ══
    raw_on_data = on_data[:, best_channel_idx, :]  # (20, 601)
    raw_plv_metrics = preprocessing.compute_epoch_plv_summary(
        raw_on_data, gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz    )
    raw_plv_by_intensity.append(float(raw_plv_metrics["plv"]))

    # ══ 7.3 Compute SASS PLV ══
    sass_on_data_best = np.zeros((on_data.shape[0], on_data.shape[2]))
    on_data_view = preprocessing.filter_signal(on_data, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    lateoff_data = epochs_lateoff_all[intensity_pct].get_data()
    lateoff_data_view = preprocessing.filter_signal(lateoff_data, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    n_epochs_on, n_channels_on, n_samples_on = on_data_view.shape
    n_epochs_off = lateoff_data_view.shape[0]

    on_view_concat = on_data_view.transpose(1, 0, 2).reshape(n_channels_on, -1)
    lateoff_view_concat = lateoff_data_view.transpose(1, 0, 2).reshape(n_channels_on, -1)

    cov_on_sass = np.cov(on_view_concat)
    cov_lateoff_sass = np.cov(lateoff_view_concat)
    sass_cleaned = sass.sass(on_view_concat, cov_on_sass, cov_lateoff_sass)
    sass_data = sass_cleaned.reshape(n_channels_on, n_epochs_on, n_samples_on).transpose(1, 0, 2)

    best_sass_ch_name = sass_channels_by_intensity[intensity_pct]
    best_sass_ch_idx = epochs_on_all[intensity_pct].ch_names.index(best_sass_ch_name)
    sass_on_data_best = sass_data[:, best_sass_ch_idx, :]

    sass_plv_metrics = preprocessing.compute_epoch_plv_summary(
        sass_on_data_best, gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz    )
    sass_plv_by_intensity.append(float(sass_plv_metrics["plv"]))

    # ══ 7.4 Compute SSD PLV ══
    on_data_flat = on_data.transpose(1, 0, 2).reshape(on_data.shape[1], -1)
    on_signal_ssd = preprocessing.filter_signal(on_data_flat, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    on_view_ssd = preprocessing.filter_signal(on_data_flat, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    cov_signal_ssd = np.cov(on_signal_ssd)
    cov_view_ssd = np.cov(on_view_ssd)

    evals_ssd, evecs_ssd = linalg.eig(cov_signal_ssd, cov_view_ssd)
    idx_ssd = np.argsort(np.real(evals_ssd))[::-1]
    evecs_ssd = evecs_ssd[:, idx_ssd]
    W_ssd = evecs_ssd.T[:N_SSD_COMPONENTS]

    best_ssd_comp_idx = ssd_components_by_intensity[intensity_pct]
    ssd_comp_filter = W_ssd[best_ssd_comp_idx]
    ssd_on_data_best = (ssd_comp_filter @ on_data_flat).reshape(on_data.shape[0], -1)

    ssd_plv_metrics = preprocessing.compute_epoch_plv_summary(
        ssd_on_data_best, gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz    )
    ssd_plv_by_intensity.append(float(ssd_plv_metrics["plv"]))

    # ══ 7.5 Compute STIM reference PLV ══
    stim_plv_metrics = preprocessing.compute_epoch_plv_summary(
        stim_on, gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz    )
    stim_plv_by_intensity.append(float(stim_plv_metrics["plv"]))

    # ══ 7.6 Create individual phase grid figure per intensity (no GT-STIM) ══
    intensity_phase_grid = [
        [
            {
                "title": f"Raw {best_channel_name}\nPLV={float(raw_plv_metrics['plv']):.2f}",
                "phases": raw_plv_metrics.get("phase_samples", np.array([0.0])),
                "plv": float(raw_plv_metrics["plv"]),
                "p_value": float(raw_plv_metrics.get("p_value", 1.0)),
                "color": METHOD_COLORS["raw"],
            },
            {
                "title": f"SASS {best_sass_ch_name}\nPLV={float(sass_plv_metrics['plv']):.2f}",
                "phases": sass_plv_metrics.get("phase_samples", np.array([0.0])),
                "plv": float(sass_plv_metrics["plv"]),
                "p_value": float(sass_plv_metrics.get("p_value", 1.0)),
                "color": METHOD_COLORS["sass"],
            },
            {
                "title": f"SSD Comp{best_ssd_comp_idx + 1}\nPLV={float(ssd_plv_metrics['plv']):.2f}",
                "phases": ssd_plv_metrics.get("phase_samples", np.array([0.0])),
                "plv": float(ssd_plv_metrics["plv"]),
                "p_value": float(ssd_plv_metrics.get("p_value", 1.0)),
                "color": METHOD_COLORS["ssd"],
            },
        ]
    ]
    intensity_phase_path = OUTPUT_DIRECTORY / f"exp08_art_filtering_phase_grid_{intensity_pct}pct.png"
    plot_helpers.save_phase_histogram_grid(
        phase_grid_rows=intensity_phase_grid,
        output_path=intensity_phase_path,
        title=f"{label} ON window phase distributions against GT",
        n_columns=3,
    )


# ============================================================
# 8) VISUALIZE & SAVE
# ============================================================

print("\nGenerating figures...")

# ══ 8.1 ITPC timecourse figure: 10 subplots (one per intensity) ══
intensity_pcts = [int(level * 100) for level in INTENSITY_LEVELS]
n_samples = len(next(iter(raw_itpc_curves.values())))
time_s = np.arange(n_samples) / sfreq + ITPC_WINDOW_S[0]

fig, axes = plt.subplots(len(intensity_pcts), 1, figsize=(11, 22),
                         constrained_layout=True, sharex=True, sharey=True)

for i, (ax, intensity_pct, label) in enumerate(zip(np.atleast_1d(axes), intensity_pcts, INTENSITY_LABELS)):
    # ─ Negative control: GT vs stim (should be LOW, confirming artifact separation)
    ax.plot(time_s, stim_itpc_curves[intensity_pct], color=METHOD_COLORS["gt_ref"],
            lw=2.0, label="GT vs stim (negative control)", linestyle="--", alpha=0.6)

    # ─ Method curves: attempt to recover GT from EEG
    ax.plot(time_s, raw_itpc_curves[intensity_pct], color=METHOD_COLORS["raw"],
            lw=1.8, label="Raw fixed channel")
    ax.plot(time_s, sass_itpc_curves[intensity_pct], color=METHOD_COLORS["sass"],
            lw=1.8, label="SASS")
    ax.plot(time_s, ssd_itpc_curves[intensity_pct], color=METHOD_COLORS["ssd"],
            lw=1.8, label="SSD")

    ax.set(ylim=(0, 1.05), xlim=(ON_WINDOW_S[0], ON_WINDOW_S[1]))
    ax.set_ylabel("ITPC", fontsize=10)
    ax.set_title(f"{label} intensity (n=20 epochs)", fontsize=11, color="#333")
    ax.grid(True, alpha=0.15, linestyle=":", linewidth=0.5)
    ax.axhline(y=1.0, color="red", linestyle=":", alpha=0.3, linewidth=0.8)
    if i == 0:
        ax.legend(frameon=False, loc="lower right", fontsize=9)

axes = np.atleast_1d(axes)
axes[-1].set_xlabel("Time within stimulus window (s)", fontsize=11, fontweight="bold")
fig.suptitle("Ground-Truth Signal Recovery: ITPC vs. Stimulus Artifact Control",
             fontsize=13, fontweight="bold", y=0.995)

fig.savefig(ITPC_TIMECOURSE_FIGURE_PATH, dpi=220)
plt.close(fig)
print(f"  Saved: {ITPC_TIMECOURSE_FIGURE_PATH.name}")

# ══ 7.2 ITPC summary figure: mean ITPC vs. intensity (all methods) ══
intensity_values = np.asarray([int(level * 100) for level in INTENSITY_LEVELS], dtype=float)
raw_mean_itpc_values = np.asarray([np.mean(raw_itpc_curves[int(level * 100)]) for level in INTENSITY_LEVELS], dtype=float)
sass_mean_itpc_values = np.asarray([np.mean(sass_itpc_curves[int(level * 100)]) for level in INTENSITY_LEVELS], dtype=float)
ssd_mean_itpc_values = np.asarray([np.mean(ssd_itpc_curves[int(level * 100)]) for level in INTENSITY_LEVELS], dtype=float)

summary_fig, summary_ax = plt.subplots(figsize=(10.2, 5.2))
summary_ax.plot(intensity_values, raw_mean_itpc_values, color=METHOD_COLORS["raw"], lw=1.8, marker="o", ms=6, label="Raw")
summary_ax.plot(intensity_values, sass_mean_itpc_values, color=METHOD_COLORS["sass"], lw=1.8, marker="o", ms=6, label="SASS")
summary_ax.plot(intensity_values, ssd_mean_itpc_values, color=METHOD_COLORS["ssd"], lw=1.8, marker="o", ms=6, label="SSD")
summary_ax.set(
    xticks=intensity_values,
    xlabel="Stimulus intensity (%)",
    ylabel="Mean ON-window ITPC",
    title="Ground-Truth Signal Recovery: ITPC vs. Stimulus Intensity",
)
summary_ax.set_ylim((0, 1.05))
summary_ax.legend(frameon=False, loc="upper right")
summary_ax.grid(True, alpha=0.15, linestyle=":", linewidth=0.5)
summary_fig.tight_layout()
summary_fig.savefig(ITPC_SUMMARY_FIGURE_PATH, dpi=220)
plt.close(summary_fig)
print(f"  Saved: {ITPC_SUMMARY_FIGURE_PATH.name}")

# ══ 8.3 PLV summary figure ══
intensity_values_plv = np.asarray([int(level * 100) for level in INTENSITY_LEVELS], dtype=int)
event_counts = np.asarray([20] * len(INTENSITY_LEVELS), dtype=int)

plot_helpers.save_plv_method_summary_figure(
    x_values=intensity_values_plv,
    event_counts=event_counts,
    method_series=[
        {"label": "Raw", "values": np.asarray(raw_plv_by_intensity, dtype=float), "color": METHOD_COLORS["raw"], "linewidth": 1.8},
        {"label": "SASS", "values": np.asarray(sass_plv_by_intensity, dtype=float), "color": METHOD_COLORS["sass"], "linewidth": 1.8},
        {"label": "SSD", "values": np.asarray(ssd_plv_by_intensity, dtype=float), "color": METHOD_COLORS["ssd"], "linewidth": 1.8},
        {"label": "GT vs STIM", "values": np.asarray(stim_plv_by_intensity, dtype=float), "color": METHOD_COLORS["gt_ref"], "linewidth": 1.8},
    ],
    output_path=PLV_SUMMARY_FIGURE_PATH,
    title="Ground-Truth Signal Recovery: PLV on ON windows vs. Stimulus Intensity",
)
print(f"  Saved: {PLV_SUMMARY_FIGURE_PATH.name}")


# ══ 8.5 Write summary report ══
print(f"  Writing summary...")
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    f.write("=" * 80 + "\n")
    f.write("EXP08 ARTIFACT FILTERING SUMMARY: Raw vs. SASS vs. SSD\n")
    f.write("=" * 80 + "\n\n")

    f.write("ANALYSIS OVERVIEW:\n")
    f.write("  Compared three spatial filter paths for stimulus artifact suppression:\n")
    f.write("    1. Raw: Fixed channel locked at 10% intensity (best SNR)\n")
    f.write("    2. SASS: Covariance-based artifact subtraction (ON − late-OFF)\n")
    f.write("    3. SSD: Signal-dominance eigendecomposition (signal vs. view bands)\n\n")

    f.write("RANKING CRITERION: SNR (signal-band power / view-band power, linear ratio)\n\n")

    f.write("TIME WINDOWS:\n")
    f.write(f"    ON: {ON_WINDOW_S[0]:.1f} to {ON_WINDOW_S[1]:.1f} s (stimulus present, full epoch)\n")
    f.write(f"    ITPC/PLV: {ON_WINDOW_S[0]:.1f} to {ON_WINDOW_S[1]:.1f} s (phase locking analysis window)\n")
    f.write(f"    late-OFF: {LATE_OFF_WINDOW_S[0]:.1f} to {LATE_OFF_WINDOW_S[1]:.1f} s (noise reference)\n\n")

    f.write("FREQUENCY BANDS:\n")
    f.write(f"    Signal band: {SIGNAL_BAND_HZ[0]:.1f}–{SIGNAL_BAND_HZ[1]:.1f} Hz (stimulus fundamental)\n")
    f.write(f"    View band: {VIEW_BAND_HZ[0]:.1f}–{VIEW_BAND_HZ[1]:.1f} Hz (broadband reference)\n\n")

    f.write("=" * 80 + "\n")
    f.write("RESULTS BY INTENSITY\n")
    f.write("=" * 80 + "\n")
    f.write(f"{'Intensity':<12} {'Raw SNR':<12} {'SASS SNR':<12} {'SSD SNR':<12} {'Raw ITPC':<12} {'SASS ITPC':<12} {'SSD ITPC':<12}\n")
    f.write("-" * 80 + "\n")

    for i, intensity_label in enumerate(INTENSITY_LABELS):
        intensity_pct = intensity_pcts[i]
        raw_mean_itpc = np.mean(raw_itpc_curves[intensity_pct])
        sass_mean_itpc = np.mean(sass_itpc_curves[intensity_pct])
        ssd_mean_itpc = np.mean(ssd_itpc_curves[intensity_pct])
        f.write(f"{intensity_label:<12} {raw_snr_by_intensity[i]:<12.3f} {sass_snr_by_intensity[i]:<12.3f} {ssd_snr_by_intensity[i]:<12.3f} ")
        f.write(f"{raw_mean_itpc:<12.3f} {sass_mean_itpc:<12.3f} {ssd_mean_itpc:<12.3f}\n")

    f.write("=" * 80 + "\n\n")

    f.write("SELECTED CHANNELS/COMPONENTS:\n")
    f.write(f"    Raw (locked): {best_channel_name}\n")
    f.write("    SASS by intensity:\n")
    for intensity_pct in intensity_pcts:
        f.write(f"      {intensity_pct}%: {sass_channels_by_intensity[intensity_pct]}\n")
    f.write("    SSD by intensity:\n")
    for intensity_pct in intensity_pcts:
        f.write(f"      {intensity_pct}%: Component {ssd_components_by_intensity[intensity_pct]}\n")

    f.write("\n" + "=" * 80 + "\n")
    f.write("OUTPUT FILES\n")
    f.write("=" * 80 + "\n")
    f.write(f"  {ITPC_TIMECOURSE_FIGURE_PATH.name}\n")
    f.write(f"  {ITPC_SUMMARY_FIGURE_PATH.name}\n")
    f.write(f"  {PLV_SUMMARY_FIGURE_PATH.name}\n")
    f.write("  exp08_art_filtering_phase_grid_*pct.png (5 files, one per intensity)\n")
    f.write(f"  {MANIFEST_PATH.name}\n")

print(f"  Saved: {MANIFEST_PATH.name}")

# ══ 7.4 Print summary ══
print("\n" + "=" * 80)
print("EXP08 ARTIFACT FILTERING ANALYSIS COMPLETE")
print("=" * 80)
print(f"\nSummary:")
print(f"  Raw SNR: {raw_snr_by_intensity[0]:.3f} (10%) -> {raw_snr_by_intensity[-1]:.3f} (100%)")
print(f"  SASS SNR: {sass_snr_by_intensity[0]:.3f} (10%) -> {sass_snr_by_intensity[-1]:.3f} (100%)")
print(f"  SSD SNR: {ssd_snr_by_intensity[0]:.3f} (10%) -> {ssd_snr_by_intensity[-1]:.3f} (100%)")
print(f"\nOutput directory: {OUTPUT_DIRECTORY}")
print(f"See {MANIFEST_PATH.name} for detailed results.\n")
