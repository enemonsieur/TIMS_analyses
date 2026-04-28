"""Recover ground-truth signal across 10 intensity levels using raw, SASS, and SSD on triplet epochs.

Compare three artifact suppression paths ranked by SNR: fixed raw channel (locked at 10%),
SASS (covariance-based artifact subtraction), and SSD (signal-dominance eigendecomposition).
Visualize ITPC recovery timecourse and SNR per path per intensity.

No bandpass filtering applied to epochs — this is artifact suppression only (spatial domain).
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

EPOCH_DIR   = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUT_DIR     = EPOCH_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]

# Match the epoch extraction ON window (explore_exp08_triplet_epochs.py)
ON_WINDOW_S       = (-0.6, 0.7)   # -> epoch time axis used for ITPC plot limits
LATE_OFF_WINDOW_S = (2.5, 4.2)    # quiet period: noise reference for covariance
ITPC_WINDOW_S     = (-0.2, 0.5)   # region of interest for ITPC plot (for reporting; does not clip data)

TARGET_CENTER_HZ     = 13.0
SIGNAL_HALF_WIDTH_HZ = 0.5
SIGNAL_BAND_HZ  = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
VIEW_BAND_HZ    = (4.0, 20.0)
N_SSD_COMPONENTS = 6

METHOD_COLORS = {
    "raw":    "#1f77b4",
    "sass":   "#ff7f0e",
    "ssd":    "#2ca02c",
    "gt_ref": "#d62728",
}

ITPC_TIMECOURSE_FIG = OUT_DIR / "exp08t_art_filtering_itpc_timecourse_by_intensity.png"
ITPC_SUMMARY_FIG    = OUT_DIR / "exp08t_art_filtering_itpc_summary.png"
PLV_SUMMARY_FIG     = OUT_DIR / "exp08t_art_filtering_plv_summary.png"
MANIFEST_PATH       = OUT_DIR / "exp08t_art_filtering_summary.txt"


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Pre-extracted triplet epochs (exp08t_ prefix, 10 intensities, 2 windows)
# ├─ ON epochs   (28 EEG, 20 per intensity, -0.6 to +0.7 s)
# ├─ late-OFF epochs (noise reference, 2.5 to 4.2 s)
# ├─ GT ON + late-OFF epochs (1 channel each)
# └─ stim ON epochs (1 channel, negative control)
#       │
#       ├─ Covariance matrices (ON vs. late-OFF, view band)
#       ├─────────────┬──────────────┬──────────────┐
#       ▼             ▼              ▼              ▼
#   RAW PATH     SASS PATH       SSD PATH      GT REFERENCE
#   (fixed ch)   (covariance)    (eigendecomp) (per intensity)
#       └─────────────┴──────────────┴──────────────┘
#                     │
#           SNR + ITPC timecourse per path -> figures + summary


# ============================================================
# 1) LOAD PRE-EXTRACTED EPOCHS
# ============================================================

print("Loading triplet epochs (exp08t_ prefix)...")
epochs_on_all     = {}
epochs_lateoff_all = {}
gt_on_all         = {}
gt_lateoff_all    = {}
stim_on_all       = {}
stim_lateoff_all  = {}

for level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    pct = int(level * 100)

    # ══ 1.1 EEG ON + late-OFF ══
    epochs_on_all[pct]      = mne.read_epochs(str(EPOCH_DIR / f"exp08t_epochs_{pct}pct_on-epo.fif"),      preload=True, verbose=False)
    epochs_lateoff_all[pct] = mne.read_epochs(str(EPOCH_DIR / f"exp08t_epochs_{pct}pct_lateoff-epo.fif"), preload=True, verbose=False)

    # ══ 1.2 GT ON + late-OFF ══
    gt_on_all[pct]      = mne.read_epochs(str(EPOCH_DIR / f"exp08t_gt_epochs_{pct}pct_on-epo.fif"),      preload=True, verbose=False)
    gt_lateoff_all[pct] = mne.read_epochs(str(EPOCH_DIR / f"exp08t_gt_epochs_{pct}pct_lateoff-epo.fif"), preload=True, verbose=False)

    # ══ 1.3 Stim ON + late-OFF (negative control) ══
    stim_on_all[pct]      = mne.read_epochs(str(EPOCH_DIR / f"exp08t_stim_epochs_{pct}pct_on-epo.fif"),      preload=True, verbose=False)
    stim_lateoff_all[pct] = mne.read_epochs(str(EPOCH_DIR / f"exp08t_stim_epochs_{pct}pct_lateoff-epo.fif"), preload=True, verbose=False)

    print(f"  {label}: {len(epochs_on_all[pct])} ON, {len(epochs_lateoff_all[pct])} late-OFF")

sfreq        = float(epochs_on_all[10].info["sfreq"])
channel_names = epochs_on_all[10].ch_names
print(f"\nLoaded: {sfreq:.0f} Hz, {len(channel_names)} EEG channels")


# ============================================================
# 2) COVARIANCE MATRICES (per-intensity, view band)
# ============================================================

print("\nComputing covariance matrices...")
cov_on_by_intensity     = {}
cov_lateoff_by_intensity = {}

for level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    pct = int(level * 100)

    # ══ 2.1 Filter to view band and concatenate epochs -> covariance ══
    on_data      = epochs_on_all[pct].copy().filter(*VIEW_BAND_HZ, verbose=False).get_data()
    lateoff_data = epochs_lateoff_all[pct].copy().filter(*VIEW_BAND_HZ, verbose=False).get_data()

    n_ch = on_data.shape[1]
    cov_on_by_intensity[pct]      = np.cov(on_data.transpose(1, 0, 2).reshape(n_ch, -1))
    cov_lateoff_by_intensity[pct] = np.cov(lateoff_data.transpose(1, 0, 2).reshape(n_ch, -1))


# ============================================================
# 3) RAW CHANNEL PATH (locked to best channel at 10%)
# ============================================================

print("\nRaw path: selecting best channel at 10% intensity...")
on_data_10pct   = epochs_on_all[10].get_data()   # -> (20, n_ch, n_t)
gt_on_10pct     = gt_on_all[10].get_data().squeeze()  # -> (20, n_t)

snr_10pct = [
    (ch, float(preprocessing.compute_snr_linear(on_data_10pct[:, i, :], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)))
    for i, ch in enumerate(channel_names)
]
best_channel_name = max(snr_10pct, key=lambda x: x[1])[0]
best_channel_idx  = channel_names.index(best_channel_name)
print(f"  Best channel: {best_channel_name} (SNR={max(snr_10pct, key=lambda x: x[1])[1]:.3f})")

raw_snr_by_intensity  = []
raw_itpc_curves       = {}
for level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    pct = int(level * 100)
    on_data = epochs_on_all[pct].get_data()[:, best_channel_idx, :]  # -> (20, n_t)
    gt_on   = gt_on_all[pct].get_data().squeeze()
    raw_snr_by_intensity.append(float(preprocessing.compute_snr_linear(on_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)))
    raw_itpc_curves[pct] = preprocessing.compute_itpc_timecourse(on_data, gt_on, sfreq, SIGNAL_BAND_HZ)


# ============================================================
# 4) SASS PATH (covariance-based artifact suppression)
# ============================================================

print("\nSASS path: covariance-based artifact suppression...")
sass_snr_by_intensity     = []
sass_itpc_curves          = {}
sass_channels_by_intensity = {}

for level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    pct = int(level * 100)

    # ══ 4.1 Apply SASS on view-band data ══
    on_data    = epochs_on_all[pct].copy().filter(*VIEW_BAND_HZ, verbose=False).get_data()
    n_ep, n_ch, n_t = on_data.shape
    on_concat  = on_data.transpose(1, 0, 2).reshape(n_ch, -1)
    sass_concat = sass.sass(on_concat, cov_on_by_intensity[pct], cov_lateoff_by_intensity[pct])
    sass_data  = sass_concat.reshape(n_ch, n_ep, n_t).transpose(1, 0, 2)

    # ══ 4.2 Rank SASS channels by SNR; keep best ══
    gt_on = gt_on_all[pct].get_data().squeeze()
    scores = [
        (ch, float(preprocessing.compute_snr_linear(sass_data[:, i, :], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)), sass_data[:, i, :])
        for i, ch in enumerate(channel_names)
    ]
    best_name, best_snr, best_data = max(scores, key=lambda x: x[1])
    sass_channels_by_intensity[pct] = best_name
    sass_snr_by_intensity.append(best_snr)
    sass_itpc_curves[pct] = preprocessing.compute_itpc_timecourse(best_data, gt_on, sfreq, SIGNAL_BAND_HZ)


# ============================================================
# 5) SSD PATH (signal-dominance eigendecomposition)
# ============================================================

print("\nSSD path: eigendecomposing signal vs. view bands...")
ssd_snr_by_intensity      = []
ssd_itpc_curves           = {}
ssd_components_by_intensity = {}

for level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    pct = int(level * 100)

    # ══ 5.1 Covariance in signal and view bands ══
    on_data_full = epochs_on_all[pct].get_data()   # -> (20, n_ch, n_t)
    on_flat = on_data_full.transpose(1, 0, 2).reshape(on_data_full.shape[1], -1)
    cov_signal = np.cov(preprocessing.filter_signal(on_flat, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]))
    cov_view   = np.cov(preprocessing.filter_signal(on_flat, sfreq, VIEW_BAND_HZ[0],   VIEW_BAND_HZ[1]))

    # ══ 5.2 Eigendecompose; rank components by SNR ══
    evals, evecs = linalg.eig(cov_signal, cov_view)
    idx  = np.argsort(np.real(evals))[::-1]
    W    = np.real(evecs[:, idx]).T[:N_SSD_COMPONENTS]  # -> (N_SSD_COMPONENTS, n_ch)

    gt_on  = gt_on_all[pct].get_data().squeeze()
    scores = []
    for k in range(W.shape[0]):
        comp_epochs = (W[k] @ on_flat).reshape(on_data_full.shape[0], -1)
        snr = float(preprocessing.compute_snr_linear(comp_epochs, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ))
        scores.append((k, snr, comp_epochs))

    best_idx, best_snr, best_data = max(scores, key=lambda x: x[1])
    ssd_components_by_intensity[pct] = best_idx
    ssd_snr_by_intensity.append(best_snr)
    ssd_itpc_curves[pct] = preprocessing.compute_itpc_timecourse(best_data, gt_on, sfreq, SIGNAL_BAND_HZ)


# ============================================================
# 6) STIMULUS REFERENCE (negative control — GT vs stim)
# ============================================================

print("\nComputing stimulus reference ITPC (negative control)...")
stim_itpc_curves = {}
for level in INTENSITY_LEVELS:
    pct     = int(level * 100)
    gt_on   = gt_on_all[pct].get_data().squeeze()
    stim_on = stim_on_all[pct].get_data().squeeze()
    stim_itpc_curves[pct] = preprocessing.compute_itpc_timecourse(gt_on, stim_on, sfreq, SIGNAL_BAND_HZ)


# ============================================================
# 7) PLV ON ON-WINDOWS
# ============================================================

print("\nComputing PLV on ON windows...")
gt_on_10 = gt_on_all[10].get_data().squeeze()
gt_signal = preprocessing.filter_signal(gt_on_10, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
gt_psd    = np.mean(np.abs(np.fft.rfft(gt_signal, axis=-1)) ** 2, axis=0)
freqs     = np.fft.rfftfreq(gt_signal.shape[-1], 1 / sfreq)
target_peak_hz = freqs[np.argmax(gt_psd)]

raw_plv_by_intensity  = []
sass_plv_by_intensity = []
ssd_plv_by_intensity  = []
stim_plv_by_intensity = []

for level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    pct = int(level * 100)

    on_data = epochs_on_all[pct].get_data()     # -> (20, n_ch, n_t)
    gt_on   = gt_on_all[pct].get_data().squeeze()
    stim_on = stim_on_all[pct].get_data().squeeze()

    # ── Raw PLV ──
    raw_metrics = preprocessing.compute_epoch_plv_summary(
        on_data[:, best_channel_idx, :], gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz)
    raw_plv_by_intensity.append(float(raw_metrics["plv"]))

    # ── SASS PLV (recompute spatial filter) ──
    on_view      = preprocessing.filter_signal(on_data,                     sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    lateoff_view = preprocessing.filter_signal(epochs_lateoff_all[pct].get_data(), sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    n_ep, n_ch, n_t = on_view.shape
    on_vc   = on_view.transpose(1, 0, 2).reshape(n_ch, -1)
    off_vc  = lateoff_view.transpose(1, 0, 2).reshape(n_ch, -1)
    sass_out = sass.sass(on_vc, np.cov(on_vc), np.cov(off_vc))
    sass_data_plv = sass_out.reshape(n_ch, n_ep, n_t).transpose(1, 0, 2)
    best_sass_ch_idx = channel_names.index(sass_channels_by_intensity[pct])
    sass_metrics = preprocessing.compute_epoch_plv_summary(
        sass_data_plv[:, best_sass_ch_idx, :], gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz)
    sass_plv_by_intensity.append(float(sass_metrics["plv"]))

    # ── SSD PLV (recompute filter) ──
    on_flat_plv = on_data.transpose(1, 0, 2).reshape(n_ch, -1)
    cov_s = np.cov(preprocessing.filter_signal(on_flat_plv, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]))
    cov_v = np.cov(preprocessing.filter_signal(on_flat_plv, sfreq, VIEW_BAND_HZ[0],   VIEW_BAND_HZ[1]))
    ev, evec = linalg.eig(cov_s, cov_v)
    W_plv = np.real(evec[:, np.argsort(np.real(ev))[::-1]]).T[:N_SSD_COMPONENTS]
    best_k = ssd_components_by_intensity[pct]
    ssd_data_plv = (W_plv[best_k] @ on_flat_plv).reshape(on_data.shape[0], -1)
    ssd_metrics = preprocessing.compute_epoch_plv_summary(
        ssd_data_plv, gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz)
    ssd_plv_by_intensity.append(float(ssd_metrics["plv"]))

    # ── Stim PLV (negative control) ──
    stim_metrics = preprocessing.compute_epoch_plv_summary(
        stim_on, gt_on, sfreq, SIGNAL_BAND_HZ, target_peak_hz)
    stim_plv_by_intensity.append(float(stim_metrics["plv"]))

    # ── Per-intensity phase grid ──
    phase_grid = [[
        {"title": f"Raw {best_channel_name}\nPLV={float(raw_metrics['plv']):.2f}",
         "phases": raw_metrics.get("phase_samples", np.array([0.0])),
         "plv": float(raw_metrics["plv"]), "p_value": float(raw_metrics.get("p_value", 1.0)),
         "color": METHOD_COLORS["raw"]},
        {"title": f"SASS {sass_channels_by_intensity[pct]}\nPLV={float(sass_metrics['plv']):.2f}",
         "phases": sass_metrics.get("phase_samples", np.array([0.0])),
         "plv": float(sass_metrics["plv"]), "p_value": float(sass_metrics.get("p_value", 1.0)),
         "color": METHOD_COLORS["sass"]},
        {"title": f"SSD Comp{ssd_components_by_intensity[pct]+1}\nPLV={float(ssd_metrics['plv']):.2f}",
         "phases": ssd_metrics.get("phase_samples", np.array([0.0])),
         "plv": float(ssd_metrics["plv"]), "p_value": float(ssd_metrics.get("p_value", 1.0)),
         "color": METHOD_COLORS["ssd"]},
    ]]
    plot_helpers.save_phase_histogram_grid(
        phase_grid_rows=phase_grid,
        output_path=OUT_DIR / f"exp08t_art_filtering_phase_grid_{pct}pct.png",
        title=f"{label} ON window phase distributions against GT",
        n_columns=3,
    )


# ============================================================
# 8) VISUALIZE & SAVE
# ============================================================

print("\nGenerating figures...")
intensity_pcts = [int(l * 100) for l in INTENSITY_LEVELS]

# ── Correct time axis: ITPC curve spans the ON window, not ITPC_WINDOW_S ──
n_samples_itpc = len(next(iter(raw_itpc_curves.values())))
time_s = np.arange(n_samples_itpc) / sfreq + ON_WINDOW_S[0]

# ══ 8.1 ITPC timecourse: one subplot per intensity ══
fig, axes = plt.subplots(len(intensity_pcts), 1, figsize=(11, 22),
                         constrained_layout=True, sharex=True, sharey=True)
for i, (ax, pct, label) in enumerate(zip(np.atleast_1d(axes), intensity_pcts, INTENSITY_LABELS)):
    ax.plot(time_s, stim_itpc_curves[pct],  color=METHOD_COLORS["gt_ref"], lw=2.0, label="GT vs stim (neg. ctrl)", linestyle="--", alpha=0.6)
    ax.plot(time_s, raw_itpc_curves[pct],   color=METHOD_COLORS["raw"],    lw=1.8, label="Raw fixed channel")
    ax.plot(time_s, sass_itpc_curves[pct],  color=METHOD_COLORS["sass"],   lw=1.8, label="SASS")
    ax.plot(time_s, ssd_itpc_curves[pct],   color=METHOD_COLORS["ssd"],    lw=1.8, label="SSD")
    # Mark triplet pulse times (0, 20, 40 ms)
    for t_pulse in [0.000, 0.020, 0.040]:
        ax.axvline(t_pulse, color="gray", linewidth=0.7, linestyle=":", alpha=0.6)
    ax.set(ylim=(0, 1.05), xlim=ON_WINDOW_S)
    ax.set_ylabel("ITPC", fontsize=10)
    ax.set_title(f"{label} intensity (n=20 triplets)", fontsize=11, color="#333")
    ax.grid(True, alpha=0.15, linestyle=":", linewidth=0.5)
    ax.axhline(y=1.0, color="red", linestyle=":", alpha=0.3, linewidth=0.8)
    if i == 0:
        ax.legend(frameon=False, loc="lower right", fontsize=9)
np.atleast_1d(axes)[-1].set_xlabel("Time relative to triplet onset (s)", fontsize=11, fontweight="bold")
fig.suptitle("EXP08 Triplet: GT Signal Recovery — ITPC vs. Artifact Control",
             fontsize=13, fontweight="bold", y=0.995)
fig.savefig(ITPC_TIMECOURSE_FIG, dpi=220)
plt.close(fig)
print(f"  Saved: {ITPC_TIMECOURSE_FIG.name}")

# ══ 8.2 ITPC summary: mean ITPC vs. intensity ══
intensity_values = np.asarray(intensity_pcts, dtype=float)
raw_mean_itpc  = np.asarray([np.mean(raw_itpc_curves[p])  for p in intensity_pcts])
sass_mean_itpc = np.asarray([np.mean(sass_itpc_curves[p]) for p in intensity_pcts])
ssd_mean_itpc  = np.asarray([np.mean(ssd_itpc_curves[p])  for p in intensity_pcts])

fig2, ax2 = plt.subplots(figsize=(10.2, 5.2))
ax2.plot(intensity_values, raw_mean_itpc,  color=METHOD_COLORS["raw"],  lw=1.8, marker="o", ms=6, label="Raw")
ax2.plot(intensity_values, sass_mean_itpc, color=METHOD_COLORS["sass"], lw=1.8, marker="o", ms=6, label="SASS")
ax2.plot(intensity_values, ssd_mean_itpc,  color=METHOD_COLORS["ssd"],  lw=1.8, marker="o", ms=6, label="SSD")
ax2.set(xticks=intensity_values, xlabel="Stimulus intensity (%)", ylabel="Mean ON-window ITPC",
        title="EXP08 Triplet: GT Recovery ITPC vs. Stimulus Intensity", ylim=(0, 1.05))
ax2.legend(frameon=False, loc="upper right")
ax2.grid(True, alpha=0.15, linestyle=":", linewidth=0.5)
fig2.tight_layout()
fig2.savefig(ITPC_SUMMARY_FIG, dpi=220)
plt.close(fig2)
print(f"  Saved: {ITPC_SUMMARY_FIG.name}")

# ══ 8.3 PLV summary ══
plot_helpers.save_plv_method_summary_figure(
    x_values=np.asarray(intensity_pcts, dtype=int),
    event_counts=np.asarray([20] * len(INTENSITY_LEVELS), dtype=int),
    method_series=[
        {"label": "Raw",      "values": np.asarray(raw_plv_by_intensity),  "color": METHOD_COLORS["raw"],    "linewidth": 1.8},
        {"label": "SASS",     "values": np.asarray(sass_plv_by_intensity), "color": METHOD_COLORS["sass"],   "linewidth": 1.8},
        {"label": "SSD",      "values": np.asarray(ssd_plv_by_intensity),  "color": METHOD_COLORS["ssd"],    "linewidth": 1.8},
        {"label": "GT vs STIM","values": np.asarray(stim_plv_by_intensity),"color": METHOD_COLORS["gt_ref"], "linewidth": 1.8},
    ],
    output_path=PLV_SUMMARY_FIG,
    title="EXP08 Triplet: GT Recovery PLV on ON windows vs. Stimulus Intensity",
)
print(f"  Saved: {PLV_SUMMARY_FIG.name}")

# ══ 8.4 Text summary ══
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    f.write("=" * 80 + "\n")
    f.write("EXP08 TRIPLET ARTIFACT FILTERING: Raw vs. SASS vs. SSD\n")
    f.write("=" * 80 + "\n\n")
    f.write("EPOCH SOURCE: exp08-STIM-triplet_run02_10-100.vhdr\n")
    f.write("  Triplet structure: 3 half-sine pulses at 0 / 20 / 40 ms (50 Hz)\n")
    f.write("  Protocol: 20 triplets × 10 intensity levels (10–100%); 5 s inter-triplet\n\n")
    f.write(f"TIME WINDOWS:\n")
    f.write(f"  ON:       {ON_WINDOW_S[0]:.1f} to {ON_WINDOW_S[1]:.1f} s\n")
    f.write(f"  late-OFF: {LATE_OFF_WINDOW_S[0]:.1f} to {LATE_OFF_WINDOW_S[1]:.1f} s (noise reference)\n\n")
    f.write(f"FREQUENCY BANDS:\n")
    f.write(f"  Signal: {SIGNAL_BAND_HZ[0]:.1f}–{SIGNAL_BAND_HZ[1]:.1f} Hz\n")
    f.write(f"  View:   {VIEW_BAND_HZ[0]:.1f}–{VIEW_BAND_HZ[1]:.1f} Hz\n\n")
    f.write("=" * 80 + "\n")
    f.write(f"{'Intensity':<10} {'Raw SNR':<12} {'SASS SNR':<12} {'SSD SNR':<12} "
            f"{'Raw ITPC':<12} {'SASS ITPC':<12} {'SSD ITPC':<12}\n")
    f.write("-" * 80 + "\n")
    for i, lbl in enumerate(INTENSITY_LABELS):
        pct = intensity_pcts[i]
        f.write(f"{lbl:<10} {raw_snr_by_intensity[i]:<12.3f} {sass_snr_by_intensity[i]:<12.3f} "
                f"{ssd_snr_by_intensity[i]:<12.3f} {np.mean(raw_itpc_curves[pct]):<12.3f} "
                f"{np.mean(sass_itpc_curves[pct]):<12.3f} {np.mean(ssd_itpc_curves[pct]):<12.3f}\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"Raw locked channel: {best_channel_name}\n")
    f.write("SASS best channel per intensity:\n")
    for pct in intensity_pcts:
        f.write(f"  {pct}%: {sass_channels_by_intensity[pct]}\n")
    f.write("SSD best component per intensity:\n")
    for pct in intensity_pcts:
        f.write(f"  {pct}%: Component {ssd_components_by_intensity[pct]}\n")
print(f"  Saved: {MANIFEST_PATH.name}")

print("\n" + "=" * 80)
print("EXP08 TRIPLET ARTIFACT FILTERING COMPLETE")
print("=" * 80)
print(f"Raw  SNR:  {raw_snr_by_intensity[0]:.3f} (10%) -> {raw_snr_by_intensity[-1]:.3f} (100%)")
print(f"SASS SNR:  {sass_snr_by_intensity[0]:.3f} (10%) -> {sass_snr_by_intensity[-1]:.3f} (100%)")
print(f"SSD  SNR:  {ssd_snr_by_intensity[0]:.3f} (10%) -> {ssd_snr_by_intensity[-1]:.3f} (100%)")
print(f"\nOutput: {OUT_DIR}")
