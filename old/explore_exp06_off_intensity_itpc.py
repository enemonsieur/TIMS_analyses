"""Does the transferred exp06 baseline SSD stay more GT-locked than raw O2 from 10% to 50% late-OFF?"""

from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import preprocessing
import plot_helpers


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
# Measured STIM amplitudes show that run01 starts with the true 10% block.
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
WEIGHTS_PATH = OUTPUT_DIRECTORY / "exp06_baseline_ssd_component1_weights.npz"

INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES_PER_INTENSITY = 20
LATE_OFF_START_S = 1.5
LATE_OFF_STOP_S = 3.2
FOCUS_CHANNEL = "O2"
TIMING_PADDING_BEFORE_S = 2.0
TIMING_PADDING_AFTER_S = 0.5
RAW_CHANNEL_COLOR = "black"
RECOVERED_COLOR = "steelblue"
INTENSITY_COLORS = ["#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#084594"]


# ===== Load ===================================================================
weights_artifact = preprocessing.load_exp06_saved_ssd_artifact(WEIGHTS_PATH)
saved_channel_names = weights_artifact["channel_names"]
saved_sampling_rate_hz = weights_artifact["sampling_rate_hz"]
signal_band_hz = weights_artifact["signal_band_hz"]
view_band_hz = weights_artifact["view_band_hz"]
selected_filter = weights_artifact["selected_filter"]

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_stim_full.ch_names or "ground_truth" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channels: stim and ground_truth.")

sampling_rate_hz = float(raw_stim_full.info["sfreq"])
stim_marker_v = raw_stim_full.copy().pick(["stim"]).get_data()[0]
ground_truth_stim_v = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]
raw_stim_eeg = raw_stim_full.copy().pick(saved_channel_names)
preprocessing.validate_exp06_saved_ssd_against_raw(
    raw_stim_eeg,
    saved_channel_names,
    saved_sampling_rate_hz,
    selected_filter,
    focus_channel=FOCUS_CHANNEL,
)

print(f"exp06 off-intensity itpc | {len(saved_channel_names)} ch | {sampling_rate_hz:.0f} Hz")


# ===== Block 1: Build per-intensity late-OFF windows ==========================
# Keep the dose slicing explicit because this script answers one fixed exp06
# question: transfer from baseline into the known 10-20-30-40-50% sweep order.
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(stim_marker_v, sampling_rate_hz)
required_block_count = len(INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY + 1
if len(block_onsets_samples) < required_block_count:
    raise RuntimeError(
        f"Need at least {required_block_count} measured ON blocks to build 10-50% late-OFF windows, "
        f"but found {len(block_onsets_samples)}."
    )

summary_rows = []
itpc_curves_raw = []
itpc_curves_ssd = []
timing_windows = []
trace_axis_s = None
late_off_duration_samples = None

for intensity_index, intensity_label in enumerate(INTENSITY_LABELS):
    block_start_index = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    block_stop_index = block_start_index + BLOCK_CYCLES_PER_INTENSITY + 1
    dose_block_onsets = block_onsets_samples[block_start_index:block_stop_index]
    dose_block_offsets = block_offsets_samples[block_start_index:block_stop_index]
    events_late_off, late_off_duration_s, late_off_duration_samples = preprocessing.build_late_off_events(
        dose_block_onsets,
        dose_block_offsets,
        sampling_rate_hz,
        LATE_OFF_START_S,
        LATE_OFF_STOP_S,
    )
    if len(events_late_off) != BLOCK_CYCLES_PER_INTENSITY:
        raise RuntimeError(
            f"Expected {BLOCK_CYCLES_PER_INTENSITY} valid late-OFF windows for {intensity_label}, "
            f"but built {len(events_late_off)}."
        )

    epochs_view, selected_component_epochs = preprocessing.apply_exp06_saved_ssd_to_events(
        raw_stim_eeg,
        events_late_off,
        selected_filter,
        view_band_hz,
        late_off_duration_s,
    )
    focus_channel_epochs = epochs_view.copy().pick([FOCUS_CHANNEL]).get_data()[:, 0, :]
    ground_truth_epochs = preprocessing.extract_event_windows(
        ground_truth_stim_v,
        events_late_off[:, 0],
        late_off_duration_samples,
    )

    raw_metrics = preprocessing.compute_band_limited_epoch_triplet_metrics(
        focus_channel_epochs,
        ground_truth_epochs,
        sampling_rate_hz,
        signal_band_hz,
    )
    recovered_metrics = preprocessing.compute_band_limited_epoch_triplet_metrics(
        selected_component_epochs,
        ground_truth_epochs,
        sampling_rate_hz,
        signal_band_hz,
    )
    recovered_peak_hz = preprocessing.find_psd_peak_frequency(
        selected_component_epochs.reshape(-1),
        sampling_rate_hz,
        view_band_hz,
    )

    intensity_pct = int(intensity_label.replace("%", ""))
    summary_rows.append(
        {
            "label": intensity_label,
            "intensity_pct": intensity_pct,
            "event_count": int(len(events_late_off)),
            "raw_mean_itpc": float(np.mean(raw_metrics["itpc_curve"])),
            "ssd_mean_itpc": float(np.mean(recovered_metrics["itpc_curve"])),
            "recovered_peak_hz": float(recovered_peak_hz),
            "block_onsets_samples": dose_block_onsets[:BLOCK_CYCLES_PER_INTENSITY].copy(),
            "block_offsets_samples": dose_block_offsets[:BLOCK_CYCLES_PER_INTENSITY].copy(),
            "late_off_event_starts": events_late_off[:, 0].copy(),
        }
    )
    itpc_curves_raw.append(np.asarray(raw_metrics["itpc_curve"], dtype=float))
    itpc_curves_ssd.append(np.asarray(recovered_metrics["itpc_curve"], dtype=float))
    timing_windows.append(events_late_off[:, 0].copy())

    if trace_axis_s is None:
        trace_axis_s = epochs_view.times + LATE_OFF_START_S

    print(
        f"{intensity_label} | late_off={len(events_late_off)} "
        f"| raw_itpc={summary_rows[-1]['raw_mean_itpc']:.4f} "
        f"| ssd_itpc={summary_rows[-1]['ssd_mean_itpc']:.4f} "
        f"| peak={recovered_peak_hz:.2f} Hz"
    )


# ===== Block 2: Save figures ==================================================
# Figure 1 orients the reader to the measured dose ordering before comparing ITPC.
timing_start_sample = max(0, block_onsets_samples[0] - int(round(TIMING_PADDING_BEFORE_S * sampling_rate_hz)))
timing_stop_sample = min(
    raw_stim_full.n_times,
    timing_windows[-1][-1] + late_off_duration_samples + int(round(TIMING_PADDING_AFTER_S * sampling_rate_hz)),
)
timing_axis_s = (
    np.arange(timing_stop_sample - timing_start_sample, dtype=float) / sampling_rate_hz
    + timing_start_sample / sampling_rate_hz
    - block_onsets_samples[0] / sampling_rate_hz
)
stim_segment = stim_marker_v[timing_start_sample:timing_stop_sample]

timing_figure, timing_axis = plt.subplots(figsize=(12.4, 3.8), constrained_layout=True)
timing_axis.plot(timing_axis_s, stim_segment, color="black", lw=0.8)
for block_onset_sample, block_offset_sample in zip(block_onsets_samples[: required_block_count - 1], block_offsets_samples[: required_block_count - 1]):
    timing_axis.axvspan(
        block_onset_sample / sampling_rate_hz - block_onsets_samples[0] / sampling_rate_hz,
        block_offset_sample / sampling_rate_hz - block_onsets_samples[0] / sampling_rate_hz,
        color="0.82",
        alpha=0.35,
    )
for row, intensity_color in zip(summary_rows, INTENSITY_COLORS, strict=True):
    for late_off_start_sample in row["late_off_event_starts"]:
        late_off_start_s = late_off_start_sample / sampling_rate_hz - block_onsets_samples[0] / sampling_rate_hz
        timing_axis.axvspan(
            late_off_start_s,
            late_off_start_s + late_off_duration_samples / sampling_rate_hz,
            color=intensity_color,
            alpha=0.32,
        )
timing_axis.text(
    0.015,
    0.96,
    "Gray = measured ON blocks\nBlue shades = accepted late-OFF windows from 10% to 50%",
    transform=timing_axis.transAxes,
    va="top",
    fontsize=8.3,
    bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 2.5},
)
timing_axis.set(
    xlabel="Time from first 10% ON block (s)",
    ylabel="STIM (V)",
    title="The exp06 run contains five measured late-OFF dose blocks from 10% to 50%",
)
plot_helpers.style_clean_axis(timing_axis, grid_alpha=0.15)
timing_path = OUTPUT_DIRECTORY / "exp06_off_intensity_itpc_timing_windows.png"
timing_figure.savefig(timing_path, dpi=220)
plt.close(timing_figure)

# Figure 2 is the main claim figure: one summary metric across dose.
intensity_values = np.asarray([row["intensity_pct"] for row in summary_rows], dtype=float)
raw_mean_itpc_values = np.asarray([row["raw_mean_itpc"] for row in summary_rows], dtype=float)
ssd_mean_itpc_values = np.asarray([row["ssd_mean_itpc"] for row in summary_rows], dtype=float)

summary_figure, summary_axis = plt.subplots(figsize=(8.8, 4.6), constrained_layout=True)
summary_axis.plot(intensity_values, raw_mean_itpc_values, color=RAW_CHANNEL_COLOR, lw=1.8, marker="o", ms=6, label=FOCUS_CHANNEL)
summary_axis.plot(intensity_values, ssd_mean_itpc_values, color=RECOVERED_COLOR, lw=2.3, marker="o", ms=6, label="SSD")
summary_axis.set(
    xticks=intensity_values,
    xlabel="Stimulation intensity (%)",
    ylabel="Mean late-OFF ITPC",
    title=f"Transferred SSD stays more GT-locked than raw {FOCUS_CHANNEL} from 10% to 50%",
)
summary_axis.legend(frameon=False, loc="upper right")
plot_helpers.style_clean_axis(summary_axis, grid_alpha=0.15)
summary_path = OUTPUT_DIRECTORY / "exp06_off_intensity_itpc_summary.png"
summary_figure.savefig(summary_path, dpi=220)
plt.close(summary_figure)

# Figure 3 qualifies the summary with aligned ITPC time courses for each dose.
itpc_floor = min(float(np.min(curve)) for curve in itpc_curves_raw + itpc_curves_ssd)
itpc_ceiling = max(float(np.max(curve)) for curve in itpc_curves_raw + itpc_curves_ssd)
itpc_figure, itpc_axes = plt.subplots(1, len(INTENSITY_LABELS), figsize=(15.5, 3.9), constrained_layout=True, sharey=True)
for axis, row, raw_curve, ssd_curve, intensity_color in zip(
    np.atleast_1d(itpc_axes),
    summary_rows,
    itpc_curves_raw,
    itpc_curves_ssd,
    INTENSITY_COLORS,
    strict=True,
):
    axis.plot(trace_axis_s, raw_curve, color=RAW_CHANNEL_COLOR, lw=1.6)
    axis.plot(trace_axis_s, ssd_curve, color=RECOVERED_COLOR, lw=2.0)
    axis.set_title(row["label"], color=intensity_color, pad=8)
    axis.set_xlabel("Time after offset (s)")
    axis.set_ylim(max(0.0, itpc_floor - 0.01), min(1.0, itpc_ceiling + 0.01))
    plot_helpers.style_clean_axis(axis, grid_alpha=0.12)
itpc_axes = np.atleast_1d(itpc_axes)
itpc_axes[0].set_ylabel("ITPC")
itpc_axes[-1].legend([FOCUS_CHANNEL, "SSD"], frameon=False, loc="lower right")
itpc_figure.suptitle("GT-locked late-OFF ITPC by dose block", fontsize=12.5)
itpc_path = OUTPUT_DIRECTORY / "exp06_off_intensity_itpc_panels.png"
itpc_figure.savefig(itpc_path, dpi=220)
plt.close(itpc_figure)

summary_lines = [
    "exp06 off-intensity itpc summary",
    f"stim_vhdr_path={STIM_VHDR_PATH}",
    f"weights_npz={WEIGHTS_PATH.name}",
    f"signal_band_hz=({signal_band_hz[0]:.6f}, {signal_band_hz[1]:.6f})",
    f"late_off_window_s=({LATE_OFF_START_S:.6f}, {LATE_OFF_STOP_S:.6f})",
    f"focus_channel={FOCUS_CHANNEL}",
]
for row in summary_rows:
    label_key = row["label"].replace("%", "pct")
    summary_lines.extend(
        [
            f"{label_key}_late_off_count={row['event_count']}",
            f"{label_key}_raw_mean_itpc={row['raw_mean_itpc']:.6f}",
            f"{label_key}_ssd_mean_itpc={row['ssd_mean_itpc']:.6f}",
            f"{label_key}_ssd_peak_hz={row['recovered_peak_hz']:.6f}",
        ]
    )
summary_text_path = OUTPUT_DIRECTORY / "exp06_off_intensity_itpc_summary.txt"
summary_text_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

print(f"saved={timing_path.name}")
print(f"saved={summary_path.name}")
print(f"saved={itpc_path.name}")
print(f"saved={summary_text_path.name}")
