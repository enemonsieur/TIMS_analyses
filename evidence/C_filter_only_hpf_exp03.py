"""Exp03 approach C: filter-only HPF baseline."""

from pathlib import Path
import csv
import warnings

import mne
import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

import plot_helpers
import preprocessing


# ============================================================
# CONSTANTS (EDIT ONLY THIS BLOCK)
# ============================================================
STIM_VHDR_PATH = Path(
    r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
)
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_artifact_compare_C_filter_only")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

FIXED_RETAINED_CHANNELS = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Cz"]
CHANNEL_FOR_METRICS = "FC1"

EPOCH_TMIN_S = -2.0
EPOCH_TMAX_S = 1.0
POSTPULSE_CROP_WINDOW_S = (0.08, 1.00)
HPF_HZ = 1.0
HPF_IIR_ORDER = 4

ZOOM_WINDOW_S = (0.00, 0.35)
BAND_HZ = (8.0, 12.0)
EVAL_WINDOW_MAX_S = 0.30
MIN_EVAL_SAMPLES = 16

METRICS_FIELDNAMES = [
    "stage",
    "plv",
    "coherence_8_12",
    "recovery_latency_ms",
    "eval_window_start_s",
    "eval_window_end_s",
]


# ============================================================
# LOAD RAW + EVENTS
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

sampling_rate_hz = float(raw.info["sfreq"])
stim_marker = raw.copy().pick(["stim"]).get_data()[0]
stim_onsets_samples, _, _, _ = preprocessing.detect_stim_onsets(
    stim_marker=stim_marker, sampling_rate_hz=sampling_rate_hz
)
events = np.c_[stim_onsets_samples, np.zeros_like(stim_onsets_samples), np.ones_like(stim_onsets_samples)].astype(int)

raw_eeg = raw.copy().pick(FIXED_RETAINED_CHANNELS)
raw_ground_truth = raw.copy().pick(["ground_truth"])


# ============================================================
# BUILD STAGES
# ============================================================
# Stage 1 keeps the unfiltered reference.
stage1_eeg = mne.Epochs(
    raw_eeg, events, event_id=1, tmin=EPOCH_TMIN_S, tmax=EPOCH_TMAX_S, baseline=None, preload=True, verbose=False
)
stage1_ground_truth = mne.Epochs(
    raw_ground_truth, events, event_id=1, tmin=EPOCH_TMIN_S, tmax=EPOCH_TMAX_S, baseline=None, preload=True, verbose=False
)

# Stage 2 discards the pulse block before filtering.
stage2_eeg = stage1_eeg.copy().crop(tmin=POSTPULSE_CROP_WINDOW_S[0], tmax=POSTPULSE_CROP_WINDOW_S[1])
stage2_ground_truth = stage1_ground_truth.copy().crop(
    tmin=POSTPULSE_CROP_WINDOW_S[0], tmax=POSTPULSE_CROP_WINDOW_S[1]
)

# Stage 3 applies the 1.0 Hz HPF only on the cropped post-pulse signal.
stage3_eeg = stage2_eeg.copy().filter(
    l_freq=HPF_HZ,
    h_freq=None,
    method="iir",
    iir_params={"order": HPF_IIR_ORDER, "ftype": "butter"},
    verbose=False,
)
stage3_ground_truth = stage2_ground_truth.copy().filter(
    l_freq=HPF_HZ,
    h_freq=None,
    picks="all",
    method="iir",
    iir_params={"order": HPF_IIR_ORDER, "ftype": "butter"},
    verbose=False,
)

stage_epochs = {
    "01  Raw (no filter)": stage1_eeg,
    "02  Crop post-pulse (0.08-1.0 s)": stage2_eeg,
    "03  HPF 1.0 Hz on cropped": stage3_eeg,
}
stage_ground_truth_epochs = {
    "01  Raw (no filter)": stage1_ground_truth,
    "02  Crop post-pulse (0.08-1.0 s)": stage2_ground_truth,
    "03  HPF 1.0 Hz on cropped": stage3_ground_truth,
}


# ============================================================
# FIGURE 1: PIPELINE SUBPLOTS
# ============================================================
plot_helpers.plot_cz_pipeline_steps(
    stage_epochs=stage_epochs,
    channel=CHANNEL_FOR_METRICS,
    output_path=OUTPUT_DIRECTORY / "pipeline_steps_FC1.png",
)


# ============================================================
# FIGURE 2: ZOOMED EEG VS GROUND_TRUTH OVERLAYS
# ============================================================
stage_eeg_traces_uv = {}
stage_ground_truth_traces_uv = {}
stage_time_axes_seconds = {}
for stage_name in stage_epochs:
    stage_eeg_traces_uv[stage_name] = stage_epochs[stage_name].get_data(picks=[CHANNEL_FOR_METRICS]).mean(axis=0).squeeze() * 1e6
    stage_ground_truth_traces_uv[stage_name] = stage_ground_truth_epochs[stage_name].get_data().mean(axis=0).squeeze() * 1e6
    stage_time_axes_seconds[stage_name] = stage_epochs[stage_name].times

plot_helpers.plot_stage_overlay_with_ground_truth(
    stage_eeg_traces_uv=stage_eeg_traces_uv,
    stage_ground_truth_traces_uv=stage_ground_truth_traces_uv,
    stage_time_axes_seconds=stage_time_axes_seconds,
    zoom_window_s=ZOOM_WINDOW_S,
    output_path=OUTPUT_DIRECTORY / "zoom_overlay_FC1_vs_groundtruth.png",
    eeg_label=CHANNEL_FOR_METRICS,
    ground_truth_label="ground_truth",
)


# ============================================================
# RECOVERY LATENCY (HOW CLOSE TO ARTIFACT)
# ============================================================
# Crop boundary defines the first valid post-pulse sample for the filtered stage.
recovery_time_s = float(POSTPULSE_CROP_WINDOW_S[0])
recovery_latency_ms = 1000.0 * recovery_time_s
if recovery_latency_ms <= 50.0:
    latency_rating = "ideal"
elif recovery_latency_ms <= 150.0:
    latency_rating = "acceptable"
else:
    latency_rating = "too_late"


# ============================================================
# PHASE RECOVERY METRICS (PLV + COHERENCE)
# ============================================================
band_sos = butter(4, [BAND_HZ[0], BAND_HZ[1]], btype="bandpass", fs=sampling_rate_hz, output="sos")
metrics_rows = []
for stage_name in stage_epochs:
    eeg_epoch_data = stage_epochs[stage_name].get_data(picks=[CHANNEL_FOR_METRICS]).squeeze(1)
    gt_epoch_data = stage_ground_truth_epochs[stage_name].get_data().squeeze(1)
    stage_time = stage_epochs[stage_name].times

    eval_window_start_s = max(float(stage_time[0]), float(recovery_time_s))
    eval_window_end_s = min(float(stage_time[-1]), float(EVAL_WINDOW_MAX_S))
    eval_mask = (stage_time >= eval_window_start_s) & (stage_time <= eval_window_end_s)

    coherence_values = []
    plv_values = []
    if int(np.sum(eval_mask)) >= MIN_EVAL_SAMPLES:
        for eeg_epoch, gt_epoch in zip(eeg_epoch_data, gt_epoch_data):
            eeg_band = sosfiltfilt(band_sos, eeg_epoch[eval_mask])
            gt_band = sosfiltfilt(band_sos, gt_epoch[eval_mask])
            coherence_values.append(
                preprocessing.compute_coherence_band(
                    signal_a=eeg_band,
                    signal_b=gt_band,
                    sampling_rate_hz=sampling_rate_hz,
                    low_hz=float(BAND_HZ[0]),
                    high_hz=float(BAND_HZ[1]),
                )
            )
            plv_values.append(
                preprocessing.compute_plv_phase(
                    analytic_a=hilbert(eeg_band),
                    analytic_b=hilbert(gt_band),
                )
            )
        coherence_mean = float(np.mean(coherence_values))
        plv_mean = float(np.mean(plv_values))
    else:
        coherence_mean = float("nan")
        plv_mean = float("nan")

    metrics_rows.append(
        {
            "stage": stage_name,
            "plv": plv_mean,
            "coherence_8_12": coherence_mean,
            "eval_window_start_s": eval_window_start_s,
            "eval_window_end_s": eval_window_end_s,
        }
    )
for row in metrics_rows:
    row["recovery_latency_ms"] = recovery_latency_ms
with open(OUTPUT_DIRECTORY / "metrics_summary.csv", "w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=METRICS_FIELDNAMES)
    writer.writeheader()
    writer.writerows(metrics_rows)


# ============================================================
# SUMMARY
# ============================================================
ground_truth_recovered = preprocessing.did_ground_truth_recover(metrics_rows)
summary_items = {
    "approach": "C_filter_only_hpf",
    "n_pulses": int(len(stim_onsets_samples)),
    "channel": CHANNEL_FOR_METRICS,
    "recovery_latency_ms": float(recovery_latency_ms),
    "latency_rating": latency_rating,
    "raw_plv": float(metrics_rows[0]["plv"]),
    "final_plv": float(metrics_rows[-1]["plv"]),
    "raw_coherence_8_12": float(metrics_rows[0]["coherence_8_12"]),
    "final_coherence_8_12": float(metrics_rows[-1]["coherence_8_12"]),
    "ground_truth_recovered": bool(ground_truth_recovered),
}
preprocessing.save_summary_items(summary_items=summary_items, output_path=OUTPUT_DIRECTORY / "summary.txt")

print(f"Saved -> {OUTPUT_DIRECTORY / 'pipeline_steps_FC1.png'}")
print(f"Saved -> {OUTPUT_DIRECTORY / 'zoom_overlay_FC1_vs_groundtruth.png'}")
print(f"Saved -> {OUTPUT_DIRECTORY / 'metrics_summary.csv'}")
print(f"Saved -> {OUTPUT_DIRECTORY / 'summary.txt'}")
