"""Validate whether exp05 late-OFF baseline SSD can recover the measured GT band."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import welch

import plot_helpers
import preprocessing


# ============================================================
# FIXED INPUTS
# ============================================================
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
BASELINE_VHDR = DATA_DIR / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
STIM_100_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-GT-cTBS-run01.vhdr"
STIM_30_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP05_ssd_recovery")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

GT_SEARCH_RANGE_HZ = (4.0, 12.0)
PSD_FREQUENCY_RANGE_HZ = (5.0, 15.0)
SIGNAL_HALF_WIDTH_HZ = 1.0
N_COMP = 10
OFF_WINDOW_START_AFTER_OFFSET_S = 1.5
OFF_WINDOW_STOP_AFTER_OFFSET_S = 2.5
BASELINE_FIRST_EVENT_START_S = 2.0
BASELINE_STRIDE_S = 1.0
PEAK_FLANK_GAP_HZ = 0.5
TARGET_PEAK_TOLERANCE_HZ = 0.0
CONDITION_COLORS = plot_helpers.TIMS_CONDITION_COLORS


# ============================================================
# 1) LOAD DATA
# ============================================================
raw_base = mne.io.read_raw_brainvision(str(BASELINE_VHDR), preload=True, verbose=False)
raw_100 = mne.io.read_raw_brainvision(str(STIM_100_VHDR), preload=True, verbose=False)
raw_30 = mne.io.read_raw_brainvision(str(STIM_30_VHDR), preload=True, verbose=False)
sfreq = float(raw_base.info["sfreq"])

ground_truth_base = raw_base.copy().pick(["ground_truth"]).get_data()[0]
ground_truth_100 = raw_100.copy().pick(["ground_truth"]).get_data()[0]
ground_truth_30 = raw_30.copy().pick(["ground_truth"]).get_data()[0]
stim_marker_100 = raw_100.copy().pick(["stim"]).get_data()[0]
stim_marker_30 = raw_30.copy().pick(["stim"]).get_data()[0]

for raw in (raw_base, raw_100, raw_30):
    non_eeg_channels = [channel_name for channel_name in raw.ch_names if channel_name.lower() in ("stim", "ground_truth") or channel_name.startswith("STI")]
    raw.drop_channels(non_eeg_channels)

common_channels = sorted(set(raw_base.ch_names) & set(raw_100.ch_names) & set(raw_30.ch_names))
for raw in (raw_base, raw_100, raw_30):
    raw.pick(common_channels)

print(f"EEG channels: {len(common_channels)}  |  sfreq: {sfreq}")


# ============================================================
# 2) BUILD LATE-OFF WINDOWS FROM MEASURED STIM OFFSETS
# ============================================================
block_onsets_100, block_offsets_100 = preprocessing.detect_stim_blocks(stim_marker_100, sfreq)
block_onsets_30, block_offsets_30 = preprocessing.detect_stim_blocks(stim_marker_30, sfreq)

on_durations_100_s = (block_offsets_100 - block_onsets_100) / sfreq
on_durations_30_s = (block_offsets_30 - block_onsets_30) / sfreq
off_durations_100_s = (block_onsets_100[1:] - block_offsets_100[:-1]) / sfreq
off_durations_30_s = (block_onsets_30[1:] - block_offsets_30[:-1]) / sfreq
median_on_100_s = float(np.median(on_durations_100_s))
median_on_30_s = float(np.median(on_durations_30_s))
median_off_100_s = float(np.median(off_durations_100_s))
median_off_30_s = float(np.median(off_durations_30_s))
max_cycle_s = max(median_on_100_s + median_off_100_s, median_on_30_s + median_off_30_s)
late_off_duration_s = OFF_WINDOW_STOP_AFTER_OFFSET_S - OFF_WINDOW_START_AFTER_OFFSET_S
late_off_duration_samples = int(round(late_off_duration_s * sfreq))
min_off_duration_s = float(min(np.min(off_durations_100_s), np.min(off_durations_30_s)))

if min_off_duration_s <= OFF_WINDOW_STOP_AFTER_OFFSET_S:
    raise RuntimeError(
        f"Late-OFF stop {OFF_WINDOW_STOP_AFTER_OFFSET_S:.3f} s does not fit into the shortest measured OFF gap {min_off_duration_s:.3f} s."
    )

late_off_starts_100 = block_offsets_100[:-1] + int(round(OFF_WINDOW_START_AFTER_OFFSET_S * sfreq))
late_off_starts_30 = block_offsets_30[:-1] + int(round(OFF_WINDOW_START_AFTER_OFFSET_S * sfreq))
valid_late_off_100 = late_off_starts_100 + late_off_duration_samples <= block_onsets_100[1:]
valid_late_off_30 = late_off_starts_30 + late_off_duration_samples <= block_onsets_30[1:]

events_100 = np.column_stack(
    [
        late_off_starts_100[valid_late_off_100],
        np.zeros(np.sum(valid_late_off_100), dtype=int),
        np.ones(np.sum(valid_late_off_100), dtype=int),
    ]
)
events_30 = np.column_stack(
    [
        late_off_starts_30[valid_late_off_30],
        np.zeros(np.sum(valid_late_off_30), dtype=int),
        np.ones(np.sum(valid_late_off_30), dtype=int),
    ]
)

baseline_stride_samples = int(round(BASELINE_STRIDE_S * sfreq))
baseline_event_starts = np.arange(
    int(round(BASELINE_FIRST_EVENT_START_S * sfreq)),
    raw_base.n_times - late_off_duration_samples,
    baseline_stride_samples,
    dtype=int,
)
events_base = np.column_stack(
    [
        baseline_event_starts,
        np.zeros(len(baseline_event_starts), dtype=int),
        np.ones(len(baseline_event_starts), dtype=int),
    ]
)

late_off_mask_base = np.zeros(raw_base.n_times, dtype=bool)
late_off_mask_30 = np.zeros(raw_30.n_times, dtype=bool)
late_off_mask_100 = np.zeros(raw_100.n_times, dtype=bool)
for start_sample in events_base[:, 0]:
    late_off_mask_base[int(start_sample):int(start_sample) + late_off_duration_samples] = True
for start_sample in events_30[:, 0]:
    late_off_mask_30[int(start_sample):int(start_sample) + late_off_duration_samples] = True
for start_sample in events_100[:, 0]:
    late_off_mask_100[int(start_sample):int(start_sample) + late_off_duration_samples] = True

print("=== LATE-OFF SSD WINDOWS ===")
print("Nominal paradigm: 2 s ON / 3 s OFF")
print(f"100%: ON={median_on_100_s:.3f} s  OFF={median_off_100_s:.3f} s")
print(f" 30%: ON={median_on_30_s:.3f} s  OFF={median_off_30_s:.3f} s")
print(f"Late-OFF analysis window: {OFF_WINDOW_START_AFTER_OFFSET_S:.3f}-{OFF_WINDOW_STOP_AFTER_OFFSET_S:.3f} s after measured offset")
print(f"Late-OFF epoch duration: {late_off_duration_s:.3f} s")
print(f"SSD events -- baseline: {len(events_base)}  |  30%: {len(events_30)}  |  100%: {len(events_100)}")


# ============================================================
# 2b) FIGURE: TIMING INSPECTION (OFF window placement)
# ============================================================
time_window_duration_s = 40.0
time_window_start_sample = int(round(5.0 * sfreq))
time_window_end_sample = time_window_start_sample + int(round(time_window_duration_s * sfreq))
time_window_end_sample = min(time_window_end_sample, raw_100.n_times)

cz_idx = raw_100.ch_names.index("Cz")
cz_data_100 = raw_100.get_data(start=time_window_start_sample, stop=time_window_end_sample)[cz_idx]
stim_data_100 = stim_marker_100[time_window_start_sample:time_window_end_sample]
time_axis_s = np.arange(len(cz_data_100)) / sfreq

time_offset_s = time_window_start_sample / sfreq

fig_timing, (ax_stim, ax_cz) = plt.subplots(2, 1, figsize=(12.0, 5.5), sharex=True)

ax_stim.plot(time_axis_s, stim_data_100, lw=1.0, color="black")
ax_stim.set_ylabel("STIM (V)")
ax_stim.set_title("100% stimulation: ON blocks (gray) and late-OFF windows (blue)")
ax_stim.grid(alpha=0.2)

ax_cz.plot(time_axis_s, cz_data_100, lw=0.8, color="steelblue")
ax_cz.set_ylabel("Cz (µV)")
ax_cz.set_xlabel("Time (s) from record start")
ax_cz.grid(alpha=0.2)

for onset, offset in zip(block_onsets_100, block_offsets_100):
    if time_window_start_sample <= onset < time_window_end_sample:
        ax_stim.axvspan((onset - time_window_start_sample) / sfreq,
                        (offset - time_window_start_sample) / sfreq,
                        color="gray", alpha=0.3, label="ON block" if onset == block_onsets_100[0] else "")
        ax_cz.axvspan((onset - time_window_start_sample) / sfreq,
                      (offset - time_window_start_sample) / sfreq,
                      color="gray", alpha=0.3)

for offset in block_offsets_100:
    late_off_start = offset + int(round(OFF_WINDOW_START_AFTER_OFFSET_S * sfreq))
    late_off_stop = offset + int(round(OFF_WINDOW_STOP_AFTER_OFFSET_S * sfreq))
    if time_window_start_sample <= late_off_start < time_window_end_sample:
        ax_stim.axvspan((late_off_start - time_window_start_sample) / sfreq,
                        (late_off_stop - time_window_start_sample) / sfreq,
                        color="cyan", alpha=0.4, label="late-OFF window (1.5-2.5s)" if offset == block_offsets_100[0] else "")
        ax_cz.axvspan((late_off_start - time_window_start_sample) / sfreq,
                      (late_off_stop - time_window_start_sample) / sfreq,
                      color="cyan", alpha=0.4)

ax_stim.legend(fontsize=9, loc="upper right")
fig_timing.tight_layout()
fig_timing.savefig(OUTPUT_DIRECTORY / "fig_timing_inspection.png", dpi=220)
plt.close(fig_timing)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig_timing_inspection.png'}")


# ============================================================
# 3) MEASURE THE GT PEAK FROM THE BASELINE GT RECORDING
# ============================================================
gt_freqs_base_hz, gt_psd_base = welch(ground_truth_base, fs=sfreq, nperseg=min(4096, ground_truth_base.size))
gt_freqs_30_hz, gt_psd_30 = welch(ground_truth_30, fs=sfreq, nperseg=min(4096, ground_truth_30.size))
gt_freqs_100_hz, gt_psd_100 = welch(ground_truth_100, fs=sfreq, nperseg=min(4096, ground_truth_100.size))
gt_search_mask = (gt_freqs_base_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_base_hz <= GT_SEARCH_RANGE_HZ[1])
if not np.any(gt_search_mask):
    raise ValueError("GT_SEARCH_RANGE_HZ does not overlap the Welch frequencies.")

gt_peak_frequency_hz = float(gt_freqs_base_hz[gt_search_mask][np.argmax(gt_psd_base[gt_search_mask])])
signal_band_hz = (
    max(PSD_FREQUENCY_RANGE_HZ[0], gt_peak_frequency_hz - SIGNAL_HALF_WIDTH_HZ),
    min(PSD_FREQUENCY_RANGE_HZ[1], gt_peak_frequency_hz + SIGNAL_HALF_WIDTH_HZ),
)
peak_30_hz = float(
    gt_freqs_30_hz[(gt_freqs_30_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_30_hz <= GT_SEARCH_RANGE_HZ[1])][
        np.argmax(gt_psd_30[(gt_freqs_30_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_30_hz <= GT_SEARCH_RANGE_HZ[1])])
    ]
)
peak_100_hz = float(
    gt_freqs_100_hz[(gt_freqs_100_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_100_hz <= GT_SEARCH_RANGE_HZ[1])][
        np.argmax(gt_psd_100[(gt_freqs_100_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_100_hz <= GT_SEARCH_RANGE_HZ[1])])
    ]
)

print("\n=== RECORDED GT PEAK ===")
print(f"baseline GT peak: {gt_peak_frequency_hz:.3f} Hz")
print(f"    30% GT peak: {peak_30_hz:.3f} Hz")
print(f"   100% GT peak: {peak_100_hz:.3f} Hz")
print(f"SSD signal band: {signal_band_hz[0]:.3f}-{signal_band_hz[1]:.3f} Hz")


# ============================================================
# 4) FIGURE 0: GT PSD CHECK
# ============================================================
fig0, ax0 = plt.subplots(figsize=(8.0, 4.4))
for label, freqs_hz, psd_values, color in [
    ("baseline GT", gt_freqs_base_hz, gt_psd_base, CONDITION_COLORS["baseline"]),
    ("30% GT", gt_freqs_30_hz, gt_psd_30, CONDITION_COLORS["30%"]),
    ("100% GT", gt_freqs_100_hz, gt_psd_100, CONDITION_COLORS["100%"]),
]:
    visible_mask = (freqs_hz >= PSD_FREQUENCY_RANGE_HZ[0]) & (freqs_hz <= PSD_FREQUENCY_RANGE_HZ[1])
    ax0.plot(freqs_hz[visible_mask], 10.0 * np.log10(psd_values[visible_mask] + 1e-30), lw=1.8, color=color, label=label)
ax0.axvline(gt_peak_frequency_hz, color="darkorange", lw=1.2, ls="--", label=f"measured GT peak ({gt_peak_frequency_hz:.2f} Hz)")
ax0.axvspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.8)
ax0.set_xlim(PSD_FREQUENCY_RANGE_HZ)
ax0.set_xlabel("Frequency (Hz)")
ax0.set_ylabel("Power (dB)")
ax0.set_title("exp05: Ground-truth PSD across runs")
ax0.grid(alpha=0.2)
ax0.legend(fontsize=8, loc="upper right")
fig0.tight_layout()
fig0.savefig(OUTPUT_DIRECTORY / "fig0_ground_truth_reference_psd.png", dpi=220)
plt.close(fig0)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig0_ground_truth_reference_psd.png'}")


# ============================================================
# 5) TRAIN SSD ON BASELINE LATE-OFF EPOCHS
# ============================================================
n_comp = min(N_COMP, len(common_channels))
W_train, patterns_train, evals_train = plot_helpers.run_ssd(
    raw_base,
    events_base,
    signal_band_hz,
    PSD_FREQUENCY_RANGE_HZ,
    n_comp=n_comp,
    epoch_duration_s=late_off_duration_s,
)

raw_base_band = raw_base.copy().filter(*signal_band_hz, verbose=False)
raw_30_band = raw_30.copy().filter(*signal_band_hz, verbose=False)
raw_100_band = raw_100.copy().filter(*signal_band_hz, verbose=False)
raw_base_view = raw_base.copy().filter(*PSD_FREQUENCY_RANGE_HZ, verbose=False)
raw_30_view = raw_30.copy().filter(*PSD_FREQUENCY_RANGE_HZ, verbose=False)
raw_100_view = raw_100.copy().filter(*PSD_FREQUENCY_RANGE_HZ, verbose=False)
ground_truth_base_band = preprocessing.filter_signal(ground_truth_base, sfreq, signal_band_hz[0], signal_band_hz[1])
ground_truth_30_band = preprocessing.filter_signal(ground_truth_30, sfreq, signal_band_hz[0], signal_band_hz[1])
ground_truth_100_band = preprocessing.filter_signal(ground_truth_100, sfreq, signal_band_hz[0], signal_band_hz[1])
ground_truth_base_view = preprocessing.filter_signal(ground_truth_base, sfreq, PSD_FREQUENCY_RANGE_HZ[0], PSD_FREQUENCY_RANGE_HZ[1])
signal_band_width_hz = signal_band_hz[1] - signal_band_hz[0]

component_metrics = []
for component_index in range(n_comp):
    baseline_component_band = W_train[component_index] @ raw_base_band.get_data()
    baseline_component_view = W_train[component_index] @ raw_base_view.get_data()
    baseline_component_band_late = baseline_component_band[late_off_mask_base]
    baseline_component_view_late = baseline_component_view[late_off_mask_base]
    ground_truth_base_band_late = ground_truth_base_band[late_off_mask_base]
    peak_frequency_hz = preprocessing.find_psd_peak_frequency(
        baseline_component_view_late,
        sfreq,
        PSD_FREQUENCY_RANGE_HZ,
    )
    phase_samples = preprocessing.sample_phase_differences(
        ground_truth_base_band_late,
        baseline_component_band_late,
        sfreq,
        gt_peak_frequency_hz,
    )
    component_metrics.append(
        {
            "component_index": int(component_index),
            "lambda": float(evals_train[component_index]),
            "coherence": preprocessing.compute_coherence_band(
                baseline_component_band_late,
                ground_truth_base_band_late,
                sfreq,
                signal_band_hz[0],
                signal_band_hz[1],
            ),
            "plv": float(np.abs(np.mean(np.exp(1j * phase_samples)))),
            "plv_p": preprocessing.approximate_rayleigh_p(phase_samples),
            "peak_ratio": preprocessing.compute_band_peak_ratio(
                baseline_component_view_late,
                sfreq,
                signal_band_hz,
                flank_width_hz=signal_band_width_hz,
                flank_gap_hz=PEAK_FLANK_GAP_HZ,
            ),
            "peak_frequency_hz": peak_frequency_hz,
            "peak_in_target_band": bool(
                np.isfinite(peak_frequency_hz)
                and peak_frequency_hz >= signal_band_hz[0] - TARGET_PEAK_TOLERANCE_HZ
                and peak_frequency_hz <= signal_band_hz[1] + TARGET_PEAK_TOLERANCE_HZ
            ),
        }
    )

candidate_indices = [metrics_row["component_index"] for metrics_row in component_metrics if metrics_row["peak_in_target_band"]]
selection_pool = candidate_indices if candidate_indices else list(range(n_comp))
selected_component_index = max(
    selection_pool,
    key=lambda component_index: (
        component_metrics[component_index]["coherence"],
        component_metrics[component_index]["plv"],
        component_metrics[component_index]["peak_ratio"],
        component_metrics[component_index]["lambda"],
    ),
)
selected_component_number = selected_component_index + 1
selected_filter = W_train[selected_component_index].copy()
selected_pattern = patterns_train[:, selected_component_index].copy()
selection_mode = "target_band_candidates" if candidate_indices else "fallback_all_components"

selected_component_band = selected_filter @ raw_base_band.get_data()
selected_correlation = float(
    np.corrcoef(
        selected_component_band[late_off_mask_base],
        ground_truth_base_band[late_off_mask_base],
    )[0, 1]
)
sign_flipped = bool(np.isfinite(selected_correlation) and selected_correlation < 0)
if sign_flipped:
    W_train[selected_component_index] *= -1.0
    patterns_train[:, selected_component_index] *= -1.0
    selected_filter *= -1.0
    selected_pattern *= -1.0

print("\n=== BASELINE COMPONENT SELECTION ===")
for metrics_row in component_metrics:
        band_flag = "in-band" if metrics_row["peak_in_target_band"] else "out-of-band"
        print(
            f"Comp {metrics_row['component_index'] + 1}: "
            f"lambda={metrics_row['lambda']:.3f}  "
            f"coh={metrics_row['coherence']:.3f}  "
            f"PLV={metrics_row['plv']:.3f}  "
            f"peak_ratio={metrics_row['peak_ratio']:.2f}x  "
            f"peak={metrics_row['peak_frequency_hz']:.2f} Hz  "
            f"{band_flag}"
    )
print(f"Selection mode: {selection_mode}")
print(f"Selected baseline component: {selected_component_number}")
print(f"Selected component sign-flipped for positive GT alignment: {sign_flipped}")


# ============================================================
# 6) PROJECT THE BASELINE-TRAINED FILTERS ONTO LATE-OFF EPOCHS
# ============================================================
epochs_view_base, component_epochs_base = plot_helpers.build_ssd_component_epochs(
    raw_base,
    events_base,
    W_train,
    PSD_FREQUENCY_RANGE_HZ,
    late_off_duration_s,
)
epochs_view_30, component_epochs_30 = plot_helpers.build_ssd_component_epochs(
    raw_30,
    events_30,
    W_train,
    PSD_FREQUENCY_RANGE_HZ,
    late_off_duration_s,
)
epochs_view_100, component_epochs_100 = plot_helpers.build_ssd_component_epochs(
    raw_100,
    events_100,
    W_train,
    PSD_FREQUENCY_RANGE_HZ,
    late_off_duration_s,
)

selected_component_epochs_base = component_epochs_base[selected_component_index:selected_component_index + 1]
selected_component_epochs_30 = component_epochs_30[selected_component_index:selected_component_index + 1]
selected_component_epochs_100 = component_epochs_100[selected_component_index:selected_component_index + 1]
selected_component_lambda = [float(evals_train[selected_component_index])]
selected_component_number_list = [selected_component_number]


# ============================================================
# 7) SCORE THE SELECTED COMPONENT IN BASELINE, 30%, AND 100%
# ============================================================
selected_source_base_band = selected_filter @ raw_base_band.get_data()
selected_source_30_band = selected_filter @ raw_30_band.get_data()
selected_source_100_band = selected_filter @ raw_100_band.get_data()
selected_source_base_view = selected_filter @ raw_base_view.get_data()
selected_source_30_view = selected_filter @ raw_30_view.get_data()
selected_source_100_view = selected_filter @ raw_100_view.get_data()

results = {}
for label, selected_source_band, selected_source_view, ground_truth_band, eval_mask in [
    ("baseline", selected_source_base_band, selected_source_base_view, ground_truth_base_band, late_off_mask_base),
    ("30%", selected_source_30_band, selected_source_30_view, ground_truth_30_band, late_off_mask_30),
    ("100%", selected_source_100_band, selected_source_100_view, ground_truth_100_band, late_off_mask_100),
]:
    phase_samples = preprocessing.sample_phase_differences(
        ground_truth_band[eval_mask],
        selected_source_band[eval_mask],
        sfreq,
        gt_peak_frequency_hz,
    )
    results[label] = {
        "coherence": preprocessing.compute_coherence_band(
            selected_source_band[eval_mask],
            ground_truth_band[eval_mask],
            sfreq,
            signal_band_hz[0],
            signal_band_hz[1],
        ),
        "plv": float(np.abs(np.mean(np.exp(1j * phase_samples)))),
        "plv_p": preprocessing.approximate_rayleigh_p(phase_samples),
        "peak_ratio": preprocessing.compute_band_peak_ratio(
            selected_source_view[eval_mask],
            sfreq,
            signal_band_hz,
            flank_width_hz=signal_band_width_hz,
            flank_gap_hz=PEAK_FLANK_GAP_HZ,
        ),
        "peak_frequency_hz": preprocessing.find_psd_peak_frequency(
            selected_source_view[eval_mask],
            sfreq,
            PSD_FREQUENCY_RANGE_HZ,
        ),
        "eval_seconds": float(np.sum(eval_mask) / sfreq),
    }
    print(
        f"{label:>10s}  lambda={selected_component_lambda[0]:.3f}  "
        f"coh={results[label]['coherence']:.3f}  "
        f"PLV={results[label]['plv']:.3f}  "
        f"peak_ratio={results[label]['peak_ratio']:.2f}x  "
        f"peak={results[label]['peak_frequency_hz']:.2f} Hz  "
        f"eval={results[label]['eval_seconds']:.1f} s"
    )


# ============================================================
# 8) FIGURE 1: BASELINE COMPONENT SELECTION SUMMARY
# ============================================================
component_numbers = np.arange(1, n_comp + 1, dtype=int)
selected_mask = component_numbers == selected_component_number
coherence_values = [metrics_row["coherence"] for metrics_row in component_metrics]
plv_values = [metrics_row["plv"] for metrics_row in component_metrics]
peak_ratio_values = [metrics_row["peak_ratio"] for metrics_row in component_metrics]
peak_frequency_values = [metrics_row["peak_frequency_hz"] for metrics_row in component_metrics]

fig1, (ax_lambda, ax_metric, ax_peak) = plt.subplots(1, 3, figsize=(13.8, 4.2), constrained_layout=True)
ax_lambda.bar(component_numbers, evals_train[:n_comp], color=CONDITION_COLORS["baseline"], alpha=0.85)
ax_lambda.bar(component_numbers[selected_mask], evals_train[selected_component_index:selected_component_index + 1], color="darkorange", alpha=0.95)
ax_lambda.axhline(1.0, color="gray", ls="--", lw=0.8, label="signal = noise")
ax_lambda.set_xlabel("Baseline SSD component")
ax_lambda.set_ylabel("Generalized eigenvalue lambda")
ax_lambda.set_title("Baseline SSD separation")
ax_lambda.legend(fontsize=8, loc="upper right")

bar_width = 0.35
ax_metric.bar(component_numbers - bar_width / 2, coherence_values, bar_width, color="steelblue", alpha=0.9, label="Coherence")
ax_metric.bar(component_numbers + bar_width / 2, plv_values, bar_width, color="seagreen", alpha=0.9, label="PLV")
ax_metric.axvline(selected_component_number, color="darkorange", ls="--", lw=1.0)
ax_metric.set_xlabel("Baseline SSD component")
ax_metric.set_ylabel("GT-match metric")
ax_metric.set_title(f"GT matching around {gt_peak_frequency_hz:.2f} Hz")
ax_metric.legend(fontsize=8, loc="upper right")

ax_peak.bar(component_numbers, peak_ratio_values, color="slateblue", alpha=0.9)
ax_peak.bar(component_numbers[selected_mask], [peak_ratio_values[selected_component_index]], color="darkorange", alpha=0.95)
ax_peak.axhline(1.0, color="gray", ls="--", lw=0.8)
ax_peak.set_xlabel("Baseline SSD component")
ax_peak.set_ylabel("Local peak / flank ratio")
ax_peak.set_title("Target-band peak sanity")
ax_peak_freq = ax_peak.twinx()
ax_peak_freq.scatter(component_numbers, peak_frequency_values, color="black", s=30, zorder=3, label="PSD peak")
ax_peak_freq.axhspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.45)
ax_peak_freq.axhline(gt_peak_frequency_hz, color="darkorange", ls="--", lw=1.0)
ax_peak_freq.set_ylabel("Peak frequency (Hz)")
ax_peak_freq.set_ylim(PSD_FREQUENCY_RANGE_HZ)

fig1.suptitle(
    f"exp05: baseline late-OFF SSD component selection ({OFF_WINDOW_START_AFTER_OFFSET_S:.1f}-{OFF_WINDOW_STOP_AFTER_OFFSET_S:.1f} s after offset)",
    fontsize=13,
)
fig1.savefig(OUTPUT_DIRECTORY / "fig1_baseline_component_selection.png", dpi=220)
plt.close(fig1)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig1_baseline_component_selection.png'}")


# ============================================================
# 9) FIGURE 2: BASELINE SELECTED-COMPONENT SUMMARY
# ============================================================
ground_truth_base_band_epochs = np.asarray(
    [
        ground_truth_base_band[int(start_sample):int(start_sample) + late_off_duration_samples]
        for start_sample in events_base[:, 0]
    ],
    dtype=float,
)
ground_truth_base_view_epochs = np.asarray(
    [
        ground_truth_base_view[int(start_sample):int(start_sample) + late_off_duration_samples]
        for start_sample in events_base[:, 0]
    ],
    dtype=float,
)
selected_component_band_epochs = np.asarray(
    [
        selected_source_base_band[int(start_sample):int(start_sample) + late_off_duration_samples]
        for start_sample in events_base[:, 0]
    ],
    dtype=float,
)

epoch_correlations = []
for selected_epoch, gt_epoch in zip(selected_component_band_epochs, ground_truth_base_band_epochs):
    if np.std(selected_epoch) <= 1e-12 or np.std(gt_epoch) <= 1e-12:
        epoch_correlations.append(float("nan"))
    else:
        epoch_correlations.append(float(np.corrcoef(selected_epoch, gt_epoch)[0, 1]))
best_epoch_index = int(np.nanargmax(np.asarray(epoch_correlations, dtype=float)))
time_after_offset_s = OFF_WINDOW_START_AFTER_OFFSET_S + np.arange(late_off_duration_samples) / sfreq
selected_epoch_z = (
    selected_component_band_epochs[best_epoch_index] - np.mean(selected_component_band_epochs[best_epoch_index])
) / (np.std(selected_component_band_epochs[best_epoch_index]) + 1e-12)
ground_truth_epoch_z = (
    ground_truth_base_band_epochs[best_epoch_index] - np.mean(ground_truth_base_band_epochs[best_epoch_index])
) / (np.std(ground_truth_base_band_epochs[best_epoch_index]) + 1e-12)
selected_peak_frequency_hz = peak_frequency_values[selected_component_index]
selected_peak_ratio = peak_ratio_values[selected_component_index]

fig2, (ax_trace, ax_topo, ax_psd) = plt.subplots(
    1,
    3,
    figsize=(13.4, 4.1),
    constrained_layout=True,
    gridspec_kw={"width_ratios": [1.8, 1.0, 1.3]},
)
ax_trace.plot(time_after_offset_s, ground_truth_epoch_z, color="darkorange", lw=1.6, label="GT (z)")
ax_trace.plot(time_after_offset_s, selected_epoch_z, color=CONDITION_COLORS["baseline"], lw=1.9, label=f"SSD comp {selected_component_number} (z)")
ax_trace.set_xlabel("Time after measured STIM offset (s)")
ax_trace.set_ylabel("Normalized amplitude")
ax_trace.set_title(f"Best-aligned baseline late-OFF epoch | r={epoch_correlations[best_epoch_index]:.2f}")
ax_trace.grid(alpha=0.2)
ax_trace.legend(fontsize=8, loc="upper right")

mne.viz.plot_topomap(
    np.asarray(selected_pattern, dtype=float),
    epochs_view_base.info,
    ch_type="eeg",
    axes=ax_topo,
    show=False,
    cmap=plot_helpers.TIMS_TOPO_CMAP,
)
ax_topo.set_title(f"Selected comp {selected_component_number}\nlambda={selected_component_lambda[0]:.2f}")

selected_psd_freqs_hz, selected_psd_values = welch(
    selected_component_epochs_base[0],
    fs=sfreq,
    nperseg=min(1024, selected_component_epochs_base.shape[-1]),
    axis=-1,
)
ground_truth_psd_freqs_hz, ground_truth_psd_values = welch(
    ground_truth_base_view_epochs,
    fs=sfreq,
    nperseg=min(1024, ground_truth_base_view_epochs.shape[-1]),
    axis=-1,
)
selected_mean_psd = np.mean(selected_psd_values, axis=0)
ground_truth_mean_psd = np.mean(ground_truth_psd_values, axis=0)
selected_visible_mask = (selected_psd_freqs_hz >= PSD_FREQUENCY_RANGE_HZ[0]) & (selected_psd_freqs_hz <= PSD_FREQUENCY_RANGE_HZ[1])
ground_truth_visible_mask = (ground_truth_psd_freqs_hz >= PSD_FREQUENCY_RANGE_HZ[0]) & (ground_truth_psd_freqs_hz <= PSD_FREQUENCY_RANGE_HZ[1])
selected_relative_psd = selected_mean_psd / max(float(np.max(selected_mean_psd[selected_visible_mask])), 1e-30)
ground_truth_relative_psd = ground_truth_mean_psd / max(float(np.max(ground_truth_mean_psd[ground_truth_visible_mask])), 1e-30)
ax_psd.plot(selected_psd_freqs_hz, selected_relative_psd, color=CONDITION_COLORS["baseline"], lw=2.0, label=f"SSD comp {selected_component_number}")
ax_psd.plot(ground_truth_psd_freqs_hz, ground_truth_relative_psd, color="darkorange", lw=1.3, ls="--", label="GT late-OFF")
ax_psd.axvspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.8)
ax_psd.axvline(gt_peak_frequency_hz, color="darkorange", lw=1.0, ls="--")
ax_psd.set_xlim(PSD_FREQUENCY_RANGE_HZ)
ax_psd.set_xlabel("Frequency (Hz)")
ax_psd.set_ylabel("Relative PSD")
ax_psd.set_title(f"Peak={selected_peak_frequency_hz:.2f} Hz | ratio={selected_peak_ratio:.2f}x")
ax_psd.grid(alpha=0.25)
ax_psd.legend(fontsize=8, loc="upper right")

fig2.suptitle("exp05: baseline selected-component summary", fontsize=13)
fig2.savefig(OUTPUT_DIRECTORY / "fig2_baseline_selected_component.png", dpi=220)
plt.close(fig2)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig2_baseline_selected_component.png'}")


# ============================================================
# 9b) BUILD TEMPORAL REFERENCE DATA (GT band-filtered & epoch-averaged)
# ============================================================
gt_temporal_mean_base = np.mean(
    mne.Epochs(
        mne.io.RawArray(ground_truth_base_band[np.newaxis, :], mne.create_info(1, sfreq, "eeg")),
        events_base,
        event_id=1,
        tmin=0,
        tmax=late_off_duration_s - (1.0 / sfreq),
        baseline=None,
        proj=False,
        preload=True,
        verbose=False
    ).get_data()[0],
    axis=0
)


# ============================================================
# 10) FIGURE 3: BASELINE COMPONENT GALLERY
# ============================================================
plot_helpers.plot_ssd_component_summary(
    epochs=epochs_view_base,
    spatial_patterns=patterns_train,
    component_epochs=component_epochs_base,
    spectral_ratios=evals_train,
    freq_band_hz=signal_band_hz,
    condition_name="baseline late-OFF SSD",
    output_path=OUTPUT_DIRECTORY / "fig3_baseline_component_gallery.png",
    noise_band_hz=PSD_FREQUENCY_RANGE_HZ,
    n_components=n_comp,
    psd_freq_range_hz=PSD_FREQUENCY_RANGE_HZ,
    line_color=CONDITION_COLORS["baseline"],
    reference_frequency_hz=gt_peak_frequency_hz,
    component_numbers=component_numbers.tolist(),
    temporal_reference_data=gt_temporal_mean_base,
)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig3_baseline_component_gallery.png'}")


# ============================================================
# 11) FIGURE 4: BASELINE SELECTED-COMPONENT TFR
# ============================================================
plot_helpers.plot_ssd_component_tfr(
    epochs=epochs_view_base,
    component_epochs=selected_component_epochs_base,
    spectral_ratios=selected_component_lambda,
    condition_name="baseline selected SSD component",
    output_path=OUTPUT_DIRECTORY / "fig4_baseline_selected_component_tfr.png",
    n_components=1,
    frequency_range_hz=PSD_FREQUENCY_RANGE_HZ,
    display_window_s=(0.0, late_off_duration_s),
    reference_frequency_hz=gt_peak_frequency_hz,
    component_numbers=selected_component_number_list,
    time_offset_s=OFF_WINDOW_START_AFTER_OFFSET_S,
)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig4_baseline_selected_component_tfr.png'}")


# ============================================================
# 12) SECONDARY TRANSFER FIGURES
# ============================================================
gt_temporal_mean_30 = np.mean(
    mne.Epochs(
        mne.io.RawArray(ground_truth_30_band[np.newaxis, :], mne.create_info(1, sfreq, "eeg")),
        events_30,
        event_id=1,
        tmin=0,
        tmax=late_off_duration_s - (1.0 / sfreq),
        baseline=None,
        proj=False,
        preload=True,
        verbose=False
    ).get_data()[0],
    axis=0
)

gt_temporal_mean_100 = np.mean(
    mne.Epochs(
        mne.io.RawArray(ground_truth_100_band[np.newaxis, :], mne.create_info(1, sfreq, "eeg")),
        events_100,
        event_id=1,
        tmin=0,
        tmax=late_off_duration_s - (1.0 / sfreq),
        baseline=None,
        proj=False,
        preload=True,
        verbose=False
    ).get_data()[0],
    axis=0
)

for condition_label, epochs_view, component_epochs, line_color, figure_path, gt_temporal_ref in [
    ("30%", epochs_view_30, component_epochs_30, CONDITION_COLORS["30%"], OUTPUT_DIRECTORY / "fig5_ssd_components_30pct.png", gt_temporal_mean_30),
    ("100%", epochs_view_100, component_epochs_100, CONDITION_COLORS["100%"], OUTPUT_DIRECTORY / "fig6_ssd_components_100pct.png", gt_temporal_mean_100),
]:
    plot_helpers.plot_ssd_component_summary(
        epochs=epochs_view,
        spatial_patterns=patterns_train,
        component_epochs=component_epochs,
        spectral_ratios=evals_train,
        freq_band_hz=signal_band_hz,
        condition_name=f"{condition_label} | baseline-trained SSD",
        output_path=figure_path,
        noise_band_hz=PSD_FREQUENCY_RANGE_HZ,
        n_components=n_comp,
        psd_freq_range_hz=PSD_FREQUENCY_RANGE_HZ,
        line_color=line_color,
        reference_frequency_hz=gt_peak_frequency_hz,
        comparison_component_epochs=component_epochs_base,
        comparison_color=CONDITION_COLORS["baseline"],
        comparison_label="baseline reference",
        component_numbers=component_numbers.tolist(),
        temporal_reference_data=gt_temporal_ref,
    )
    print(f"Saved -> {figure_path}")

for condition_label, epochs_view, component_epochs, figure_path in [
    ("30%", epochs_view_30, selected_component_epochs_30, OUTPUT_DIRECTORY / "fig7_selected_component_tfr_30pct.png"),
    ("100%", epochs_view_100, selected_component_epochs_100, OUTPUT_DIRECTORY / "fig8_selected_component_tfr_100pct.png"),
]:
    plot_helpers.plot_ssd_component_tfr(
        epochs=epochs_view,
        component_epochs=component_epochs,
        spectral_ratios=selected_component_lambda,
        condition_name=f"{condition_label} selected SSD component",
        output_path=figure_path,
        n_components=1,
        frequency_range_hz=PSD_FREQUENCY_RANGE_HZ,
        display_window_s=(0.0, late_off_duration_s),
        reference_frequency_hz=gt_peak_frequency_hz,
        component_numbers=selected_component_number_list,
        time_offset_s=OFF_WINDOW_START_AFTER_OFFSET_S,
    )
    print(f"Saved -> {figure_path}")


# ============================================================
# 13) SAVE NUMERIC SUMMARY
# ============================================================
summary_lines = [
    "exp05 ssd recovery",
    "analysis_mode=baseline_first_late_off",
    f"baseline_file={BASELINE_VHDR.name}",
    f"stim_30_file={STIM_30_VHDR.name}",
    f"stim_100_file={STIM_100_VHDR.name}",
    f"gt_peak_frequency_hz={gt_peak_frequency_hz:.6f}",
    f"gt_peak_30_hz={peak_30_hz:.6f}",
    f"gt_peak_100_hz={peak_100_hz:.6f}",
    f"signal_band_hz=({signal_band_hz[0]:.6f}, {signal_band_hz[1]:.6f})",
    f"psd_frequency_range_hz={PSD_FREQUENCY_RANGE_HZ}",
    f"late_off_window_s=({OFF_WINDOW_START_AFTER_OFFSET_S:.3f}, {OFF_WINDOW_STOP_AFTER_OFFSET_S:.3f})",
    f"late_off_epoch_duration_s={late_off_duration_s:.3f}",
    f"baseline_events={len(events_base)}",
    f"30_events={len(events_30)}",
    f"100_events={len(events_100)}",
    f"selection_mode={selection_mode}",
    f"selected_component={selected_component_number}",
    f"selected_component_lambda={selected_component_lambda[0]:.6f}",
    f"selected_component_peak_frequency_hz={selected_peak_frequency_hz:.6f}",
    f"selected_component_peak_ratio={selected_peak_ratio:.6f}",
    f"selected_component_sign_flipped={sign_flipped}",
    f"best_epoch_index={best_epoch_index}",
    f"best_epoch_correlation={epoch_correlations[best_epoch_index]:.6f}",
]
for metrics_row in component_metrics:
    component_number = metrics_row["component_index"] + 1
    summary_lines.extend(
        [
            f"comp{component_number}_lambda={metrics_row['lambda']:.6f}",
            f"comp{component_number}_coherence={metrics_row['coherence']:.6f}",
            f"comp{component_number}_plv={metrics_row['plv']:.6f}",
            f"comp{component_number}_plv_p={metrics_row['plv_p']:.6f}",
            f"comp{component_number}_peak_ratio={metrics_row['peak_ratio']:.6f}",
            f"comp{component_number}_peak_frequency_hz={metrics_row['peak_frequency_hz']:.6f}",
            f"comp{component_number}_peak_in_target_band={metrics_row['peak_in_target_band']}",
        ]
    )
for label in ("baseline", "30%", "100%"):
    safe_label = label.replace("%", "pct")
    summary_lines.extend(
        [
            f"{safe_label}_coherence={results[label]['coherence']:.6f}",
            f"{safe_label}_plv={results[label]['plv']:.6f}",
            f"{safe_label}_plv_p={results[label]['plv_p']:.6f}",
            f"{safe_label}_peak_ratio={results[label]['peak_ratio']:.6f}",
            f"{safe_label}_peak_frequency_hz={results[label]['peak_frequency_hz']:.6f}",
            f"{safe_label}_eval_seconds={results[label]['eval_seconds']:.3f}",
        ]
    )

summary_path = OUTPUT_DIRECTORY / "ssd_summary.txt"
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
