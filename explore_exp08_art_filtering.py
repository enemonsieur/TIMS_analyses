"""Compare EXP08 raw Oz, SASS component, SSD component, and STIM phase recovery."""

from pathlib import Path
import os

os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(Path(__file__).resolve().parent / ".mne"))
os.environ["QT_API"] = "pyqt6"
os.environ["MPLBACKEND"] = "qtagg"

import matplotlib
matplotlib.use("QtAgg", force=True)
import matplotlib.pyplot as plt
matplotlib.rcParams["backend"] = "QtAgg"
plt.ion()


import matplotlib.pyplot as plt
import mne
import numpy as np

from plot_helpers import save_phase_histogram_grid, save_plv_method_summary_figure
from preprocessing import (
    baseline_centered_window_rms_uv,
    make_sass_component_candidates,
    make_ssd_component_candidates,
    score_signal_against_reference,
    select_best_component_by_plv,
)


# ============================================================
# CONFIG
# ============================================================

EPOCH_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY = EPOCH_DIRECTORY
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# One intensity means one already-exported ON/rest/GT/STIM epoch set.
INTENSITY_PCTS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
RAW_CHANNEL_NAME = "Oz"  # fixed posterior sensor; no data-driven channel reselection

# ON is the pulse-adjacent test epoch; late-OFF is the rest covariance for SASS.
ON_WINDOW_S = (-0.5, 1.0)  # pulse-adjacent epochs already exported by EXP08 artifact-removal
LATE_OFF_WINDOW_S = (1.5, 3.2)  # rest covariance for SASS; keep away from ON pulse response

# Keep the disputed pulse-adjacent phase window to test whether artremoved data is usable there.
PHASE_WINDOW_S = (-0.5, 0.5)  # intentionally retained to test whether artremoved epochs still work here
TARGET_CENTER_HZ = 13.0  # EXP08 target; do not re-estimate from noisy short GT FFTs
SIGNAL_BAND_HZ = (12.5, 13.5)  # phase metric band around the 13 Hz target
VIEW_BAND_HZ = (4.0, 20.0)  # decomposition covariance view; broad enough to include artifacts

# SASS/SSD output component signals; ranking is component-space, not sensor-space.
N_SASS_COMPONENTS = 6
SASS_SKIP_COMPONENTS = 1  # skip the strongest ON-vs-lateOFF component before PLV ranking
N_SSD_COMPONENTS = 6
PHASE_FILTER_KWARGS = {"notch_hz": None}

# Minimal numeric sanity check: pulse-window RMS after baseline-centering.
SANITY_CHECK_PCTS = [10, 100]  # fast raw-vs-artremoved pulse-energy print
SANITY_BASELINE_WINDOW_S = (-0.2, -0.05)
SANITY_ACUTE_WINDOW_S = (0.0, 0.1)

# Fixed output names make reruns deterministic and easy to compare.
ITPC_TIMESERIES_PATH = OUTPUT_DIRECTORY / "exp08_itpc_artremoved_raw_sass_ssd_vs_gt.png"
ITPC_SUMMARY_PATH = OUTPUT_DIRECTORY / "exp08_itpc_artremoved_summary.png"
PLV_SUMMARY_PATH = OUTPUT_DIRECTORY / "exp08_plv_artremoved_raw_sass_ssd_vs_gt.png"
PHASE_GRID_STEM = "exp08_phase_hist_artremoved_raw_sass_ssd_vs_gt"
MANIFEST_PATH = OUTPUT_DIRECTORY / "exp08_art_filtering_manifest.txt"

# Stable method keys used in results[pct][method], figures, and the manifest.
METHODS = ("raw_oz", "sass_component", "ssd_component", "gt_vs_stim")
METHOD_LABELS = {
    "raw_oz": "Raw Oz",
    "sass_component": "SASS component",
    "ssd_component": "SSD component",
    "gt_vs_stim": "GT vs STIM",
}
METHOD_COLORS = {
    "raw_oz": "#2C7BB6",
    "sass_component": "#009E73",
    "ssd_component": "#D95F02",
    "gt_vs_stim": "#6A51A3",
}


def read_epochs(file_name: str) -> mne.Epochs:
    return mne.read_epochs(EPOCH_DIRECTORY / file_name, preload=True, verbose=False)


# ============================================================
# PIPELINE OVERVIEW
# ============================================================
#
# exported FIF epochs
#   -> artremoved ON sensor epochs: (epochs, channels, samples)
#   -> raw late-OFF rest epochs:    (epochs, channels, samples)
#   -> GT/STIM reference epochs:    (epochs, 1 channel, samples)
#
# method paths
#   -> raw Oz sensor trace
#   -> SASS components from ON-vs-late-OFF covariance
#   -> SSD components from 13 Hz signal covariance
#   -> STIM timing trace scored against recorded GT
#
# shared scoring
#   -> fixed 13 Hz band phase, PLV, ITPC curve, phase histogram inputs
#


# ============================================================
# 1) LOAD EXPORTED EPOCHS
# ============================================================

print("Loading EXP08 artremoved ON epochs and raw late-OFF rest epochs...")
# Dictionary shape: pct -> MNE Epochs. All files share the same epoch time axis.
epochs_on_by_pct: dict[int, mne.Epochs] = {}
epochs_lateoff_by_pct: dict[int, mne.Epochs] = {}
gt_on_by_pct: dict[int, mne.Epochs] = {}
stim_on_by_pct: dict[int, mne.Epochs] = {}

for pct in INTENSITY_PCTS:
    # ON is already artifact-removed; late-OFF stays raw for the rest covariance estimate.
    epochs_on_by_pct[pct] = read_epochs(f"exp08_epochs_{pct}pct_on_artremoved-epo.fif")
    epochs_lateoff_by_pct[pct] = read_epochs(f"exp08_epochs_{pct}pct_lateoff-epo.fif").pick(epochs_on_by_pct[pct].ch_names)

    # Add simple low pass filter to remove the small residual pulse artifact
    epochs_on_by_pct[pct].filter(None, 80, verbose=False)

    # GT is the biological/reference phase target; STIM is the pulse timing control.
    gt_on_by_pct[pct] = read_epochs(f"exp08_gt_epochs_{pct}pct_on-epo.fif")
    stim_on_by_pct[pct] = read_epochs(f"exp08_stim_epochs_{pct}pct_on-epo.fif")
    print(f"{pct}%: ON={len(epochs_on_by_pct[pct])}, late-OFF={len(epochs_lateoff_by_pct[pct])}")

# Santy check: print raw vs artremoved pulse energy in 0-0.1 s window, baseline-centered RMS in µV.
# Manual sanity plot: one 10% artremoved epoch, all sensors, to inspect pulse-locked structure.
# Data shape after indexing: (channels, samples), converted to uV only for display.
# data = epochs_on_by_pct[100][10].pick(["Oz"]).get_data()[0]  # epoch 0, all channels
# data = data - data.mean()
# data_f = mne.filter.filter_data(data, sfreq=1000, l_freq=0.5, h_freq=80, verbose=False)

# plt.plot(epochs_on_by_pct[100].times, data.T * 1e6)
# plt.plot(epochs_on_by_pct[100].times, data_f.T * 1e6)
# plt.show()
# plt.pause(interval=30.1)  # pause to ensure the plot renders before the script continues
# scheneurkel
sampling_rate_hz = float(epochs_on_by_pct[INTENSITY_PCTS[0]].info["sfreq"])
epoch_times_s = epochs_on_by_pct[INTENSITY_PCTS[0]].times

# Seconds -> sample mask; this same mask gates every ITPC and PLV summary.
phase_mask = (epoch_times_s >= PHASE_WINDOW_S[0]) & (epoch_times_s <= PHASE_WINDOW_S[1])
phase_time_s = epoch_times_s[phase_mask]

# The scorer expects the phase window relative to epoch start, not pulse-relative time.
phase_window_from_start_s = (
    PHASE_WINDOW_S[0] - float(epoch_times_s[0]),
    PHASE_WINDOW_S[1] - float(epoch_times_s[0]),
)
raw_channel_idx = epochs_on_by_pct[INTENSITY_PCTS[0]].ch_names.index(RAW_CHANNEL_NAME)


# ============================================================
# 2) QUICK ARTIFACT SANITY PRINT
# ============================================================

print("Artifact sanity: baseline-centered RMS in 0-0.1 s.")
for pct in SANITY_CHECK_PCTS:
    # Baseline-centering makes this a pulse-energy check, not a slow-offset check.
    raw_rms = baseline_centered_window_rms_uv(
        read_epochs(f"exp08_epochs_{pct}pct_on-epo.fif"),
        SANITY_BASELINE_WINDOW_S,
        SANITY_ACUTE_WINDOW_S,
    )
    clean_rms = baseline_centered_window_rms_uv(
        epochs_on_by_pct[pct],
        SANITY_BASELINE_WINDOW_S,
        SANITY_ACUTE_WINDOW_S,
    )
    print(f"sanity {pct}%: raw={raw_rms:.1f} uV, artremoved={clean_rms:.1f} uV")

# Shared kwargs keep PLV and ITPC on the same phase/scoring path.
phase_score_kwargs = {
    "sampling_rate_hz": sampling_rate_hz,
    "signal_band_hz": SIGNAL_BAND_HZ,
    "view_band_hz": VIEW_BAND_HZ,
    "reference_frequency_hz": TARGET_CENTER_HZ,
    "phase_window_from_epoch_start_s": phase_window_from_start_s,
    "time_mask_samples": phase_mask,
    "filter_kwargs": PHASE_FILTER_KWARGS,
}


# ============================================================
# 3) BUILD METHOD SIGNALS AND SCORE AGAINST GT
# ============================================================

# Results shape: results[pct][method] -> score dict used directly by all figures.
results: dict[int, dict[str, dict[str, object]]] = {pct: {} for pct in INTENSITY_PCTS}
selection_rows: list[dict[str, object]] = []

for pct in INTENSITY_PCTS:
    # MNE Epochs -> Volts arrays: sensor epochs are (epochs, channels, samples).
    on_data = epochs_on_by_pct[pct].get_data()
    lateoff_data = epochs_lateoff_by_pct[pct].get_data()

    # Reference epochs are single-channel matrices: (epochs, samples).
    gt_data = gt_on_by_pct[pct].get_data()[:, 0, :]
    stim_data = stim_on_by_pct[pct].get_data()[:, 0, :]

    # ON artremoved sensor epochs + late-OFF rest epochs -> SASS component activations.
    # Candidate components are ranked by PLV to the recorded GT, not by cleaned sensor PLV.
    sass_candidates, sass_auto_nulls = make_sass_component_candidates(
        on_data,
        lateoff_data,
        sampling_rate_hz,
        VIEW_BAND_HZ,
        N_SASS_COMPONENTS,
        skip_components=SASS_SKIP_COMPONENTS,
    )
    sass_best = select_best_component_by_plv(sass_candidates, gt_data, **phase_score_kwargs)

    # ON artremoved sensor epochs -> SSD component activations, ranked with the same GT PLV rule.
    ssd_candidates = make_ssd_component_candidates(
        on_data,
        sampling_rate_hz,
        SIGNAL_BAND_HZ,
        VIEW_BAND_HZ,
        N_SSD_COMPONENTS,
    )
    ssd_best = select_best_component_by_plv(ssd_candidates, gt_data, **phase_score_kwargs)

    # Shared scorer applies the fixed 13 Hz, 12.5-13.5 Hz phase metric to every method path.
    # Raw Oz remains the sensor baseline; STIM-vs-GT is the timing-control comparison.
    raw_score = score_signal_against_reference(
        on_data[:, raw_channel_idx, :],
        gt_data,
        **phase_score_kwargs,
    )

    if pct == 100:
        from scipy.signal import butter, sosfilt, sosfiltfilt

        raw_oz = on_data[:, raw_channel_idx, :]
        raw_oz = raw_oz.mean(axis=0)


        #quickly deman the raw_oz
        raw_oz = raw_oz - raw_oz.mean(axis=0, keepdims=True)
        sos_wide = butter(2, [4, 20], btype="bandpass", fs=sampling_rate_hz, output="sos")

        #raw_oz_phase = filter_signal(raw_oz, sampling_rate_hz, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1], **PHASE_FILTER_KWARGS)
        plt.plot(epoch_times_s, raw_oz * 1e6, label="raw Oz before ITPC filter")
        plt.plot(epoch_times_s, sosfilt(sos_wide, raw_oz) * 1e6, label="causal 10-16 Hz order2")
        plt.ylim(-10, 10)
        plt.legend(); plt.show()
        plt.pause(interval=40.1)  # pause to ensure the plot renders before the script continues
    stim_score = score_signal_against_reference(stim_data, gt_data, **phase_score_kwargs)


    results[pct] = {
        "raw_oz": {**raw_score, "label": RAW_CHANNEL_NAME},
        "sass_component": {**sass_best, "auto_null_count": sass_auto_nulls},
        "ssd_component": ssd_best,
        "gt_vs_stim": {**stim_score, "label": "STIM"},
    }

    selection_rows.append(
        {
            "pct": pct,
            "raw_plv": results[pct]["raw_oz"]["plv"],
            "sass_component": int(results[pct]["sass_component"]["index"]) + 1,
            "sass_lambda": results[pct]["sass_component"]["lambda"],
            "sass_plv": results[pct]["sass_component"]["plv"],
            "sass_auto_nulls": sass_auto_nulls,
            "ssd_component": int(results[pct]["ssd_component"]["index"]) + 1,
            "ssd_lambda": results[pct]["ssd_component"]["lambda"],
            "ssd_plv": results[pct]["ssd_component"]["plv"],
            "stim_plv": results[pct]["gt_vs_stim"]["plv"],
        }
    )

    # Compact progress print: chosen component and PLV per path, without pausing the run.
    print(
        f"{pct}% PLV: raw={results[pct]['raw_oz']['plv']:.3f}, "
        f"SASS C{selection_rows[-1]['sass_component']}={results[pct]['sass_component']['plv']:.3f}, "
        f"SSD C{selection_rows[-1]['ssd_component']}={results[pct]['ssd_component']['plv']:.3f}, "
        f"stim={results[pct]['gt_vs_stim']['plv']:.3f}"
    )


# ============================================================
# 4) SAVE METHOD FIGURES
# ============================================================

for pct in INTENSITY_PCTS:
    # Phase samples are per-epoch phase differences to GT inside PHASE_WINDOW_S.
    phase_panels = [
        {
            "phases": np.asarray(results[pct][method]["phase_samples"]),
            "plv": float(results[pct][method]["plv"]),
            "p_value": float(results[pct][method]["p_value"]),
            "title": f"{METHOD_LABELS[method]}\nPLV={results[pct][method]['plv']:.2f}",
            "color": METHOD_COLORS[method],
        }
        for method in METHODS
    ]
    save_phase_histogram_grid(
        [phase_panels],
        OUTPUT_DIRECTORY / f"{PHASE_GRID_STEM}_{pct}pct.png",
        f"EXP08 {pct}% phase differences to GT",
        n_columns=4,
    )

# ITPC curves preserve time structure so the pulse-adjacent behavior stays visible.
fig, axes = plt.subplots(5, 2, figsize=(11, 12), sharex=True, sharey=True)
for ax, pct in zip(axes.ravel(), INTENSITY_PCTS):
    for method in METHODS:
        ax.plot(
            phase_time_s,
            np.asarray(results[pct][method]["itpc_curve"]),
            label=METHOD_LABELS[method],
            color=METHOD_COLORS[method],
            linewidth=1.7,
        )
    ax.axvline(0.0, color="0.65", linewidth=0.8)
    ax.set_title(f"{pct}%")
    ax.set_ylim(0.0, 1.05)
    ax.grid(alpha=0.2)
axes[0, 0].legend(frameon=False, fontsize=8)
fig.supxlabel("Time relative to pulse (s)")
fig.supylabel("ITPC")
fig.suptitle(f"EXP08 {TARGET_CENTER_HZ:.0f} Hz ITPC after artifact-removal")
fig.tight_layout(rect=(0, 0, 1, 0.97))
fig.savefig(ITPC_TIMESERIES_PATH, dpi=180)
plt.close(fig)

# Summary figure reduces each method curve to mean ITPC over the same phase window.
fig, ax = plt.subplots(figsize=(7.5, 4.5))
for method in METHODS:
    ax.plot(
        INTENSITY_PCTS,
        [float(results[pct][method]["mean_itpc"]) for pct in INTENSITY_PCTS],
        marker="o",
        label=METHOD_LABELS[method],
        color=METHOD_COLORS[method],
    )
ax.set(
    xlabel="Stimulation intensity (% MSO)",
    ylabel=f"Mean ITPC, {PHASE_WINDOW_S[0]} to {PHASE_WINDOW_S[1]} s",
    title=f"EXP08 {TARGET_CENTER_HZ:.0f} Hz ITPC summary",
    ylim=(0.0, 1.05),
)
ax.grid(alpha=0.2)
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(ITPC_SUMMARY_PATH, dpi=180)
plt.close(fig)

# PLV uses the same stored method scores as ITPC, avoiding duplicated pipelines.
plv_method_series = [
    {
        "label": METHOD_LABELS[method],
        "values": [float(results[pct][method]["plv"]) for pct in INTENSITY_PCTS],
        "color": METHOD_COLORS[method],
    }
    for method in METHODS
]
save_plv_method_summary_figure(
    INTENSITY_PCTS,
    [len(epochs_on_by_pct[pct]) for pct in INTENSITY_PCTS],
    plv_method_series,
    PLV_SUMMARY_PATH,
    title=f"EXP08 {TARGET_CENTER_HZ:.0f} Hz PLV to GT",
    ylabel=f"PLV, {SIGNAL_BAND_HZ[0]:.1f}-{SIGNAL_BAND_HZ[1]:.1f} Hz",
    xlabel="Stimulation intensity (% MSO)",
)


# ============================================================
# 5) SAVE MANIFEST
# ============================================================

# Manifest records component choices and scalar metrics for figure interpretation.
manifest_lines = [
    "EXP08 art-filtering comparison",
    f"Epoch directory: {EPOCH_DIRECTORY}",
    f"Target frequency: fixed {TARGET_CENTER_HZ:.1f} Hz",
    f"Windows: ON={ON_WINDOW_S}, late-OFF={LATE_OFF_WINDOW_S}, phase={PHASE_WINDOW_S}",
    f"Raw: fixed {RAW_CHANNEL_NAME}; SASS: skip=max({SASS_SKIP_COMPONENTS}, auto_null_count) "
    f"then rank {N_SASS_COMPONENTS} components by PLV; SSD: rank top {N_SSD_COMPONENTS} by PLV.",
    "",
    "pct | raw_PLV | SASS_comp | SASS_lambda | SASS_PLV | SASS_auto_nulls | "
    "SSD_comp | SSD_lambda | SSD_PLV | STIM_PLV",
]
manifest_lines += [
    f"{row['pct']:>3} | {row['raw_plv']:.3f} | C{row['sass_component']} | "
    f"{row['sass_lambda']:.3g} | {row['sass_plv']:.3f} | {row['sass_auto_nulls']} | "
    f"C{row['ssd_component']} | {row['ssd_lambda']:.3g} | {row['ssd_plv']:.3f} | "
    f"{row['stim_plv']:.3f}"
    for row in selection_rows
]
manifest_lines += [
    "",
    "Saved outputs:",
    str(ITPC_TIMESERIES_PATH),
    str(ITPC_SUMMARY_PATH),
    str(PLV_SUMMARY_PATH),
]
manifest_lines += [str(OUTPUT_DIRECTORY / f"{PHASE_GRID_STEM}_{pct}pct.png") for pct in INTENSITY_PCTS]
MANIFEST_PATH.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

print(f"Saved figures and manifest in {OUTPUT_DIRECTORY}")
