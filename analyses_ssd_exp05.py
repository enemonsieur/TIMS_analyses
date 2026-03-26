"""Compare exp05 GT recovery using baseline-trained SSD on STIM-defined OFF windows."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import find_peaks, hilbert, welch

import plot_helpers
import preprocessing


# ============================================================
# FIXED INPUTS
# ============================================================
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
BASELINE_VHDR = DATA_DIR / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
STIM_100_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-GT-cTBS-run01.vhdr"
STIM_30_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP_05\ssd_recovery")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

GT_SEARCH_RANGE_HZ = (4.0, 12.0)
PSD_FREQUENCY_RANGE_HZ = (4.0, 25.0)
NOISE_BAND_HZ = (4.0, 25.0)
SIGNAL_HALF_WIDTH_HZ = 1.0
N_COMP = 6
OFF_MARGIN_S = 0.5
PEAK_FLANK_GAP_HZ = 0.5
CONDITION_COLORS = plot_helpers.TIMS_CONDITION_COLORS


def sample_phase_differences(reference_signal, target_signal, sampling_rate_hz, reference_frequency_hz):
    """Sample wrapped SSD-vs-GT phase differences once per GT cycle."""
    min_peak_distance_samples = max(1, int(round(0.8 * sampling_rate_hz / reference_frequency_hz)))
    reference_peaks, _ = find_peaks(reference_signal, distance=min_peak_distance_samples)
    if reference_peaks.size < 4:
        reference_peaks = np.arange(0, len(reference_signal), min_peak_distance_samples, dtype=int)
    phase_difference = np.angle(hilbert(target_signal)) - np.angle(hilbert(reference_signal))
    return np.angle(np.exp(1j * phase_difference[reference_peaks]))


def approximate_rayleigh_p(phases):
    """Approximate Rayleigh p-value for a circular phase sample."""
    phase_vector = np.asarray(phases, dtype=float).ravel()
    if phase_vector.size < 2:
        return float("nan")
    resultant_length = float(np.abs(np.sum(np.exp(1j * phase_vector))))
    z_value = (resultant_length ** 2) / float(phase_vector.size)
    return float(max(np.exp(-z_value) * (1.0 + (2.0 * z_value - z_value ** 2) / (4.0 * phase_vector.size)), 0.0))


def find_psd_peak_frequency(signal_1d, sampling_rate_hz, frequency_range_hz):
    """Return the strongest Welch PSD peak inside one display band."""
    frequencies_hz, psd_values = welch(np.asarray(signal_1d, dtype=float), fs=sampling_rate_hz, nperseg=min(4096, len(signal_1d)))
    visible_mask = (frequencies_hz >= frequency_range_hz[0]) & (frequencies_hz <= frequency_range_hz[1])
    if not np.any(visible_mask):
        return float("nan")
    visible_freqs_hz = frequencies_hz[visible_mask]
    visible_psd_values = psd_values[visible_mask]
    return float(visible_freqs_hz[int(np.argmax(visible_psd_values))])


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
# 2) BUILD STIM-DEFINED OFF EVENTS
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

# exp05 OFF epochs must fit inside the measured OFF gap after a 0.5 s safety margin.
min_off_duration_s = float(min(np.min(off_durations_100_s), np.min(off_durations_30_s)))
off_epoch_duration_s = min_off_duration_s - OFF_MARGIN_S - (1.0 / sfreq)
if off_epoch_duration_s <= 0.5:
    raise RuntimeError(f"OFF epoch duration is too short after margin: {off_epoch_duration_s:.3f} s")

off_margin_samples = int(round(OFF_MARGIN_S * sfreq))
off_epoch_samples = int(round(off_epoch_duration_s * sfreq))

off_starts_100 = block_offsets_100[:-1] + off_margin_samples
off_stops_100 = block_onsets_100[1:]
valid_off_mask_100 = off_starts_100 + off_epoch_samples <= off_stops_100
events_100 = np.column_stack([
    off_starts_100[valid_off_mask_100],
    np.zeros(np.sum(valid_off_mask_100), dtype=int),
    np.ones(np.sum(valid_off_mask_100), dtype=int),
])

off_starts_30 = block_offsets_30[:-1] + off_margin_samples
off_stops_30 = block_onsets_30[1:]
valid_off_mask_30 = off_starts_30 + off_epoch_samples <= off_stops_30
events_30 = np.column_stack([
    off_starts_30[valid_off_mask_30],
    np.zeros(np.sum(valid_off_mask_30), dtype=int),
    np.ones(np.sum(valid_off_mask_30), dtype=int),
])

baseline_stride_samples = int(round(max_cycle_s * sfreq))
baseline_start_sample = int(round(2.0 * sfreq))
baseline_stop_sample = raw_base.n_times - int(round(1.0 * sfreq))
baseline_pseudo_onsets = np.arange(baseline_start_sample, baseline_stop_sample, baseline_stride_samples, dtype=int)
events_base = np.column_stack([
    baseline_pseudo_onsets,
    np.zeros(len(baseline_pseudo_onsets), dtype=int),
    np.ones(len(baseline_pseudo_onsets), dtype=int),
])

off_mask_base = np.ones(raw_base.n_times, dtype=bool)
off_mask_30 = np.zeros(raw_30.n_times, dtype=bool)
off_mask_100 = np.zeros(raw_100.n_times, dtype=bool)
for offset_sample, next_onset_sample in zip(block_offsets_30[:-1], block_onsets_30[1:]):
    start_sample = int(offset_sample + off_margin_samples)
    end_sample = int(next_onset_sample)
    if start_sample < end_sample:
        off_mask_30[start_sample:end_sample] = True
for offset_sample, next_onset_sample in zip(block_offsets_100[:-1], block_onsets_100[1:]):
    start_sample = int(offset_sample + off_margin_samples)
    end_sample = int(next_onset_sample)
    if start_sample < end_sample:
        off_mask_100[start_sample:end_sample] = True

print("=== STIM-TIMED OFF WINDOWS ===")
print("Nominal paradigm: 2 s ON / 3 s OFF")
print(f"100%: ON={median_on_100_s:.3f} s  OFF={median_off_100_s:.3f} s")
print(f" 30%: ON={median_on_30_s:.3f} s  OFF={median_off_30_s:.3f} s")
print(f"OFF margin: {OFF_MARGIN_S:.3f} s")
print(f"Shortest measured OFF gap: {min_off_duration_s:.3f} s")
print(f"SSD OFF epoch duration: {off_epoch_duration_s:.3f} s")
print(f"SSD events -- baseline: {len(events_base)}  |  30%: {len(events_30)}  |  100%: {len(events_100)}")


# ============================================================
# 3) MEASURE THE ACTUAL GT PEAK FROM THE RECORDED GT CHANNEL
# ============================================================
gt_freqs_base_hz, gt_psd_base = welch(ground_truth_base, fs=sfreq, nperseg=min(4096, ground_truth_base.size))
gt_freqs_30_hz, gt_psd_30 = welch(ground_truth_30, fs=sfreq, nperseg=min(4096, ground_truth_30.size))
gt_freqs_100_hz, gt_psd_100 = welch(ground_truth_100, fs=sfreq, nperseg=min(4096, ground_truth_100.size))
gt_search_mask = (gt_freqs_base_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_base_hz <= GT_SEARCH_RANGE_HZ[1])
if not np.any(gt_search_mask):
    raise ValueError("GT_SEARCH_RANGE_HZ does not overlap the Welch frequencies.")
gt_peak_frequency_hz = float(gt_freqs_base_hz[gt_search_mask][np.argmax(gt_psd_base[gt_search_mask])])
signal_band_hz = (
    max(NOISE_BAND_HZ[0], gt_peak_frequency_hz - SIGNAL_HALF_WIDTH_HZ),
    min(NOISE_BAND_HZ[1], gt_peak_frequency_hz + SIGNAL_HALF_WIDTH_HZ),
)
tfr_display_window_s = (0.0, off_epoch_duration_s)

peak_30_hz = float(gt_freqs_30_hz[(gt_freqs_30_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_30_hz <= GT_SEARCH_RANGE_HZ[1])][np.argmax(gt_psd_30[(gt_freqs_30_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_30_hz <= GT_SEARCH_RANGE_HZ[1])])])
peak_100_hz = float(gt_freqs_100_hz[(gt_freqs_100_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_100_hz <= GT_SEARCH_RANGE_HZ[1])][np.argmax(gt_psd_100[(gt_freqs_100_hz >= GT_SEARCH_RANGE_HZ[0]) & (gt_freqs_100_hz <= GT_SEARCH_RANGE_HZ[1])])])

print("\n=== RECORDED GT PEAK ===")
print(f"baseline GT peak: {gt_peak_frequency_hz:.3f} Hz")
print(f"    30% GT peak: {peak_30_hz:.3f} Hz")
print(f"   100% GT peak: {peak_100_hz:.3f} Hz")
print(f"SSD signal band: {signal_band_hz[0]:.3f}-{signal_band_hz[1]:.3f} Hz")


# ============================================================
# 4) FIGURE 0: GT PSD CHECK
# ============================================================
fig0, ax0 = plt.subplots(figsize=(8.2, 4.6))
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
# 5) TRAIN SSD ON THE GT BASELINE ONLY
# ============================================================
n_comp = min(N_COMP, len(common_channels))
W_train, patterns_train, evals_train = plot_helpers.run_ssd(
    raw_base,
    events_base,
    signal_band_hz,
    NOISE_BAND_HZ,
    n_comp=n_comp,
    epoch_duration_s=off_epoch_duration_s,
)
epochs_view_base, component_epochs_base = plot_helpers.build_ssd_component_epochs(raw_base, events_base, W_train, NOISE_BAND_HZ, off_epoch_duration_s)
epochs_view_30, component_epochs_30 = plot_helpers.build_ssd_component_epochs(raw_30, events_30, W_train, NOISE_BAND_HZ, off_epoch_duration_s)
epochs_view_100, component_epochs_100 = plot_helpers.build_ssd_component_epochs(raw_100, events_100, W_train, NOISE_BAND_HZ, off_epoch_duration_s)

raw_base_band = raw_base.copy().filter(*signal_band_hz, verbose=False)
raw_30_band = raw_30.copy().filter(*signal_band_hz, verbose=False)
raw_100_band = raw_100.copy().filter(*signal_band_hz, verbose=False)
raw_base_view = raw_base.copy().filter(*PSD_FREQUENCY_RANGE_HZ, verbose=False)
raw_30_view = raw_30.copy().filter(*PSD_FREQUENCY_RANGE_HZ, verbose=False)
raw_100_view = raw_100.copy().filter(*PSD_FREQUENCY_RANGE_HZ, verbose=False)

ground_truth_base_band = preprocessing.filter_signal(ground_truth_base, sfreq, signal_band_hz[0], signal_band_hz[1])
signal_band_width_hz = signal_band_hz[1] - signal_band_hz[0]
component_metrics = []
for component_index in range(n_comp):
    baseline_component_band = W_train[component_index] @ raw_base_band.get_data()
    baseline_component_view = W_train[component_index] @ raw_base_view.get_data()
    component_coherence = preprocessing.compute_coherence_band(
        baseline_component_band,
        ground_truth_base_band,
        sfreq,
        signal_band_hz[0],
        signal_band_hz[1],
    )
    phase_samples = sample_phase_differences(
        ground_truth_base_band,
        baseline_component_band,
        sfreq,
        gt_peak_frequency_hz,
    )
    component_plv = float(np.abs(np.mean(np.exp(1j * phase_samples))))
    component_peak_ratio = preprocessing.compute_band_peak_ratio(
        baseline_component_view,
        sfreq,
        signal_band_hz,
        flank_width_hz=signal_band_width_hz,
        flank_gap_hz=PEAK_FLANK_GAP_HZ,
    )
    component_metrics.append(
        {
            "component_index": int(component_index),
            "coherence": component_coherence,
            "plv": component_plv,
            "plv_p": approximate_rayleigh_p(phase_samples),
            "peak_ratio": component_peak_ratio,
            "peak_frequency_hz": find_psd_peak_frequency(baseline_component_view, sfreq, PSD_FREQUENCY_RANGE_HZ),
        }
    )

selected_component_index = max(
    range(n_comp),
    key=lambda component_index: (
        component_metrics[component_index]["coherence"],
        component_metrics[component_index]["plv"],
        component_metrics[component_index]["peak_ratio"],
    ),
)
selected_component_number = selected_component_index + 1
selected_filter = W_train[selected_component_index]

print("\n=== BASELINE COMPONENT SELECTION ===")
for metrics_row in component_metrics:
    print(
        f"Comp {metrics_row['component_index'] + 1}: "
        f"coh={metrics_row['coherence']:.3f}  "
        f"PLV={metrics_row['plv']:.3f}  "
        f"peak_ratio={metrics_row['peak_ratio']:.2f}x  "
        f"peak={metrics_row['peak_frequency_hz']:.2f} Hz"
    )
print(f"Selected baseline component: {selected_component_number}")


# ============================================================
# 6) APPLY THE BASELINE-SELECTED FILTER TO ALL CONDITIONS
# ============================================================
ssd_source_base = selected_filter @ raw_base_band.get_data()
ssd_source_30 = selected_filter @ raw_30_band.get_data()
ssd_source_100 = selected_filter @ raw_100_band.get_data()
ssd_view_source_base = selected_filter @ raw_base_view.get_data()
ssd_view_source_30 = selected_filter @ raw_30_view.get_data()
ssd_view_source_100 = selected_filter @ raw_100_view.get_data()


# ============================================================
# 7) EVALUATE ONLY INSIDE MEASURED OFF WINDOWS
# ============================================================
def evaluate_condition(label, ssd_source_band, ssd_source_view, ground_truth_signal, eval_mask):
    source_band_eval = ssd_source_band[eval_mask]
    source_view_eval = ssd_source_view[eval_mask]
    ground_truth_eval = ground_truth_signal[eval_mask]
    ground_truth_band = preprocessing.filter_signal(ground_truth_eval, sfreq, signal_band_hz[0], signal_band_hz[1])
    coherence_value = preprocessing.compute_coherence_band(
        source_band_eval,
        ground_truth_band,
        sfreq,
        signal_band_hz[0],
        signal_band_hz[1],
    )
    phase_samples = sample_phase_differences(
        ground_truth_band,
        source_band_eval,
        sfreq,
        gt_peak_frequency_hz,
    )
    peak_ratio = preprocessing.compute_band_peak_ratio(
        source_view_eval,
        sfreq,
        signal_band_hz,
        flank_width_hz=signal_band_width_hz,
        flank_gap_hz=PEAK_FLANK_GAP_HZ,
    )
    return {
        "coherence": coherence_value,
        "plv": float(np.abs(np.mean(np.exp(1j * phase_samples)))),
        "plv_p": approximate_rayleigh_p(phase_samples),
        "phase_samples": phase_samples,
        "peak_ratio": peak_ratio,
        "peak_frequency_hz": find_psd_peak_frequency(source_view_eval, sfreq, PSD_FREQUENCY_RANGE_HZ),
        "off_seconds": float(np.sum(eval_mask) / sfreq),
    }


results = {}
for label, ssd_source_band, ssd_source_view, ground_truth, off_mask in [
    ("baseline", ssd_source_base, ssd_view_source_base, ground_truth_base, off_mask_base),
    ("30%", ssd_source_30, ssd_view_source_30, ground_truth_30, off_mask_30),
    ("100%", ssd_source_100, ssd_view_source_100, ground_truth_100, off_mask_100),
]:
    results[label] = evaluate_condition(
        label,
        ssd_source_band,
        ssd_source_view,
        ground_truth,
        off_mask,
    )
    print(
        f"{label:>10s}  coh={results[label]['coherence']:.3f}  "
        f"PLV={results[label]['plv']:.3f}  peak_ratio={results[label]['peak_ratio']:.2f}x  "
        f"peak={results[label]['peak_frequency_hz']:.2f} Hz  "
        f"OFF={results[label]['off_seconds']:.1f} s"
    )


# ============================================================
# 8) FIGURE 1: BASELINE COMPONENT SELECTION
# ============================================================
component_numbers = np.arange(1, n_comp + 1, dtype=int)
selection_mask = component_numbers == selected_component_number
fig1, (ax_eval, ax_metric, ax_peak) = plt.subplots(1, 3, figsize=(13.0, 4.0), constrained_layout=True)
ax_eval.bar(component_numbers, evals_train[:n_comp], color=CONDITION_COLORS["baseline"], alpha=0.85)
ax_eval.bar(component_numbers[selection_mask], evals_train[selected_component_index:selected_component_index + 1], color="darkorange", alpha=0.95)
ax_eval.axhline(1.0, color="gray", ls="--", lw=0.8, label="signal = noise")
ax_eval.set_xlabel("Baseline-trained SSD component")
ax_eval.set_ylabel("Eigenvalue (signal / noise)")
ax_eval.set_title("Baseline SSD eigenvalues")
ax_eval.legend(fontsize=8, loc="upper right")

coherence_values = [metrics_row["coherence"] for metrics_row in component_metrics]
plv_values = [metrics_row["plv"] for metrics_row in component_metrics]
bar_width = 0.35
ax_metric.bar(component_numbers - bar_width / 2, coherence_values, bar_width, color="steelblue", alpha=0.9, label="Coherence")
ax_metric.bar(component_numbers + bar_width / 2, plv_values, bar_width, color="seagreen", alpha=0.9, label="PLV")
ax_metric.axvline(selected_component_number, color="darkorange", ls="--", lw=1.0)
ax_metric.set_xlabel("Baseline-trained SSD component")
ax_metric.set_ylabel("GT recovery metric")
ax_metric.set_title(f"GT-guided selection around {gt_peak_frequency_hz:.2f} Hz")
ax_metric.legend(fontsize=8, loc="upper right")

peak_ratio_values = [metrics_row["peak_ratio"] for metrics_row in component_metrics]
ax_peak.bar(component_numbers, peak_ratio_values, color="slateblue", alpha=0.9)
ax_peak.bar(component_numbers[selection_mask], [peak_ratio_values[selected_component_index]], color="darkorange", alpha=0.95)
ax_peak.axhline(1.0, color="gray", ls="--", lw=0.8, label="peak = flank")
ax_peak.set_xlabel("Baseline-trained SSD component")
ax_peak.set_ylabel("Local peak / flank ratio")
ax_peak.set_title("Peak prominence in 4-25 Hz view")
ax_peak.legend(fontsize=8, loc="upper right")

fig1.suptitle("exp05: baseline-trained SSD component selection", fontsize=13)
fig1.savefig(OUTPUT_DIRECTORY / "fig1_ssd_eigenvalues.png", dpi=220)
plt.close(fig1)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig1_ssd_eigenvalues.png'}")


# ============================================================
# 9) FIGURE 2: SSD SOURCE VS GROUND TRUTH
# ============================================================
segment_duration_s = min(2.0, off_epoch_duration_s)
segment_samples = int(round(segment_duration_s * sfreq))
segment_index_base = min(2, len(events_base) - 1)
segment_index_30 = min(2, len(events_30) - 1)
segment_index_100 = min(2, len(events_100) - 1)

fig2, axes2 = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
for ax, label, ssd_source, ground_truth, start_sample in [
    (axes2[0], "baseline", ssd_source_base, ground_truth_base, int(events_base[segment_index_base, 0])),
    (axes2[1], "30%", ssd_source_30, ground_truth_30, int(events_30[segment_index_30, 0])),
    (axes2[2], "100%", ssd_source_100, ground_truth_100, int(events_100[segment_index_100, 0])),
]:
    time_seconds = np.arange(segment_samples) / sfreq
    source_segment = ssd_source[start_sample:start_sample + segment_samples]
    ground_truth_segment = preprocessing.filter_signal(
        ground_truth[start_sample:start_sample + segment_samples],
        sfreq,
        signal_band_hz[0],
        signal_band_hz[1],
    )
    source_z = (source_segment - np.mean(source_segment)) / (np.std(source_segment) + 1e-12)
    ground_truth_z = (ground_truth_segment - np.mean(ground_truth_segment)) / (np.std(ground_truth_segment) + 1e-12)
    ax.plot(time_seconds, ground_truth_z, color="darkorange", lw=1.0, alpha=0.85, label="ground truth (z)")
    ax.plot(time_seconds, source_z, color=CONDITION_COLORS[label], lw=1.2, label=f"SSD source (comp {selected_component_number}, z)")
    ax.set_ylabel(label)
    ax.legend(fontsize=8, loc="upper right")

axes2[-1].set_xlabel("Time inside measured OFF window (s)")
fig2.suptitle(
    f"exp05: baseline-trained SSD source vs GT ({signal_band_hz[0]:.2f}-{signal_band_hz[1]:.2f} Hz)",
    fontsize=13,
)
fig2.tight_layout()
fig2.savefig(OUTPUT_DIRECTORY / "fig2_ssd_vs_gt.png", dpi=220)
plt.close(fig2)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig2_ssd_vs_gt.png'}")


# ============================================================
# 10) FIGURE 3: RECOVERY METRICS
# ============================================================
labels = list(results.keys())
colors = [CONDITION_COLORS["baseline"], CONDITION_COLORS["30%"], CONDITION_COLORS["100%"]]
fig3 = plt.figure(figsize=(13.2, 7.4), constrained_layout=True)
grid = fig3.add_gridspec(2, 3, height_ratios=[0.9, 1.2])
ax_coh = fig3.add_subplot(grid[0, 0])
ax_peak_ratio = fig3.add_subplot(grid[0, 1])
ax_peak_freq = fig3.add_subplot(grid[0, 2])

ax_coh.bar(labels, [results[label]["coherence"] for label in labels], color=colors, alpha=0.85)
ax_coh.set_title(f"Continuous coherence @ {gt_peak_frequency_hz:.2f} Hz", fontsize=11)
ax_coh.set_ylabel("Coherence")

ax_peak_ratio.bar(labels, [results[label]["peak_ratio"] for label in labels], color=colors, alpha=0.85)
ax_peak_ratio.axhline(1.0, color="gray", ls="--", lw=0.8)
ax_peak_ratio.set_title("Local peak / flank ratio", fontsize=11)
ax_peak_ratio.set_ylabel("Ratio")

ax_peak_freq.bar(labels, [results[label]["peak_frequency_hz"] for label in labels], color=colors, alpha=0.85)
ax_peak_freq.axhline(gt_peak_frequency_hz, color="darkorange", ls="--", lw=1.0)
ax_peak_freq.set_title("Selected component PSD peak", fontsize=11)
ax_peak_freq.set_ylabel("Peak frequency (Hz)")

for column_index, label in enumerate(labels):
    polar_axis = fig3.add_subplot(grid[1, column_index], projection="polar")
    p_text = "p<0.01" if results[label]["plv_p"] < 0.01 else f"p={results[label]['plv_p']:.2f}"
    plot_helpers.circplot(
        polar_axis,
        results[label]["phase_samples"],
        results[label]["plv"],
        results[label]["plv_p"],
        f"{label}: PLV={results[label]['plv']:.2f}, {p_text}",
        colors[column_index],
    )

fig3.suptitle(
    f"exp05: continuous GT recovery with baseline-trained SSD comp {selected_component_number}\n"
    "baseline = full GT run, 30% and 100% = measured OFF samples only",
    fontsize=13,
)
fig3.savefig(OUTPUT_DIRECTORY / "fig3_recovery_metrics.png", dpi=220)
plt.close(fig3)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig3_recovery_metrics.png'}")


# ============================================================
# 11) FIGURES 4-6: COMPONENT TOPOGRAPHY + PSD
# ============================================================
for condition_label, epochs_view, component_epochs, line_color, figure_path in [
    ("baseline", epochs_view_base, component_epochs_base, CONDITION_COLORS["baseline"], OUTPUT_DIRECTORY / "fig4_ssd_components_baseline.png"),
    ("30%", epochs_view_30, component_epochs_30, CONDITION_COLORS["30%"], OUTPUT_DIRECTORY / "fig5_ssd_components_30pct.png"),
    ("100%", epochs_view_100, component_epochs_100, CONDITION_COLORS["100%"], OUTPUT_DIRECTORY / "fig6_ssd_components_100pct.png"),
]:
    plot_helpers.plot_ssd_component_summary(
        epochs=epochs_view,
        spatial_patterns=patterns_train,
        component_epochs=component_epochs,
        spectral_ratios=evals_train,
        freq_band_hz=signal_band_hz,
        condition_name=f"{condition_label} | baseline-trained SSD",
        output_path=figure_path,
        noise_band_hz=NOISE_BAND_HZ,
        n_components=n_comp,
        psd_freq_range_hz=PSD_FREQUENCY_RANGE_HZ,
        line_color=line_color,
        reference_frequency_hz=gt_peak_frequency_hz,
        comparison_component_epochs=None if condition_label == "baseline" else component_epochs_base,
        comparison_color=CONDITION_COLORS["baseline"],
        comparison_label="baseline transfer reference",
        spectral_ratio_label="Base eval",
    )
    print(f"Saved -> {figure_path}")


# ============================================================
# 12) FIGURES 7-9: COMPONENT TFR
# ============================================================
for condition_label, epochs_view, component_epochs, figure_path in [
    ("baseline", epochs_view_base, component_epochs_base, OUTPUT_DIRECTORY / "fig7_ssd_component_tfr_baseline.png"),
    ("30%", epochs_view_30, component_epochs_30, OUTPUT_DIRECTORY / "fig8_ssd_component_tfr_30pct.png"),
    ("100%", epochs_view_100, component_epochs_100, OUTPUT_DIRECTORY / "fig9_ssd_component_tfr_100pct.png"),
]:
    plot_helpers.plot_ssd_component_tfr(
        epochs=epochs_view,
        component_epochs=component_epochs,
        spectral_ratios=evals_train,
        condition_name=f"{condition_label} | baseline-trained SSD",
        output_path=figure_path,
        n_components=min(3, n_comp),
        frequency_range_hz=PSD_FREQUENCY_RANGE_HZ,
        display_window_s=tfr_display_window_s,
        reference_frequency_hz=gt_peak_frequency_hz,
        spectral_ratio_label="Base eval",
    )
    print(f"Saved -> {figure_path}")


# ============================================================
# 13) SAVE NUMERIC SUMMARY
# ============================================================
summary_lines = [
    "exp05 ssd recovery",
    "training_mode=baseline_transfer",
    f"baseline_file={BASELINE_VHDR.name}",
    f"stim_30_file={STIM_30_VHDR.name}",
    f"stim_100_file={STIM_100_VHDR.name}",
    f"gt_peak_frequency_hz={gt_peak_frequency_hz:.6f}",
    f"gt_peak_30_hz={peak_30_hz:.6f}",
    f"gt_peak_100_hz={peak_100_hz:.6f}",
    f"signal_band_hz=({signal_band_hz[0]:.6f}, {signal_band_hz[1]:.6f})",
    f"noise_band_hz={NOISE_BAND_HZ}",
    f"psd_frequency_range_hz={PSD_FREQUENCY_RANGE_HZ}",
    f"off_margin_s={OFF_MARGIN_S:.3f}",
    f"off_epoch_duration_s={off_epoch_duration_s:.3f}",
    "tfr_mode=absolute_log_power",
    f"tfr_display_window_s=({tfr_display_window_s[0]:.3f}, {tfr_display_window_s[1]:.3f})",
    f"100_on_median_s={median_on_100_s:.3f}",
    f"100_off_median_s={median_off_100_s:.3f}",
    f"30_on_median_s={median_on_30_s:.3f}",
    f"30_off_median_s={median_off_30_s:.3f}",
    f"baseline_events={len(events_base)}",
    f"30_events={len(events_30)}",
    f"100_events={len(events_100)}",
    f"selected_component={selected_component_number}",
    f"selected_component_eval={evals_train[selected_component_index]:.6f}",
]
for metrics_row in component_metrics:
    component_number = metrics_row["component_index"] + 1
    summary_lines.extend(
        [
            f"comp{component_number}_baseline_coherence={metrics_row['coherence']:.6f}",
            f"comp{component_number}_baseline_plv={metrics_row['plv']:.6f}",
            f"comp{component_number}_baseline_peak_ratio={metrics_row['peak_ratio']:.6f}",
            f"comp{component_number}_baseline_peak_frequency_hz={metrics_row['peak_frequency_hz']:.6f}",
        ]
    )
for label in labels:
    safe_label = label.replace("%", "pct")
    summary_lines.extend(
        [
            f"{safe_label}_coherence={results[label]['coherence']:.6f}",
            f"{safe_label}_plv={results[label]['plv']:.6f}",
            f"{safe_label}_plv_p={results[label]['plv_p']:.6f}",
            f"{safe_label}_peak_ratio={results[label]['peak_ratio']:.6f}",
            f"{safe_label}_peak_frequency_hz={results[label]['peak_frequency_hz']:.6f}",
            f"{safe_label}_off_seconds={results[label]['off_seconds']:.3f}",
        ]
    )

summary_path = OUTPUT_DIRECTORY / "ssd_summary.txt"
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
