"""Test whether baseline-trained SSD recovers the measured GT band in exp05 late-OFF windows."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import plot_helpers
import preprocessing


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
BASELINE_VHDR_PATH = DATA_DIRECTORY / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
STIM_30_VHDR_PATH = DATA_DIRECTORY / "exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr"
STIM_100_VHDR_PATH = DATA_DIRECTORY / "exp05-phantom-rs-STIM-ON-GT-cTBS-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP05_ssd_recovery_skript")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Measure the GT peak from the baseline run, then keep the SSD target band tight
# around that measured peak so the component ranking stays tied to the recorded data.
GT_SEARCH_RANGE_HZ = (4.0, 12.0)
VIEW_RANGE_HZ = (5.0, 15.0)
SIGNAL_HALF_WIDTH_HZ = 1.0

# The late-OFF window starts after the measured block offset so the SSD test is
# explicitly about recovery after the stimulation train, not activity during ON blocks.
LATE_OFF_START_S = 1.5
LATE_OFF_STOP_S = 2.5

# Baseline windows are fixed-length surrogate late-OFF windows used only to
# train and score the baseline SSD reference.
BASELINE_FIRST_WINDOW_START_S = 2.0
N_COMPONENTS = 10


# ===== Load ===================================================================
raw_baseline = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)
raw_stim_30 = mne.io.read_raw_brainvision(str(STIM_30_VHDR_PATH), preload=True, verbose=False)
raw_stim_100 = mne.io.read_raw_brainvision(str(STIM_100_VHDR_PATH), preload=True, verbose=False)

sampling_rate_hz = float(raw_baseline.info["sfreq"])
if not np.isclose(sampling_rate_hz, float(raw_stim_30.info["sfreq"])) or not np.isclose(
    sampling_rate_hz, float(raw_stim_100.info["sfreq"])
):
    raise RuntimeError("Baseline, 30%, and 100% recordings must share the same sampling rate.")

# Pull GT and stim markers before dropping non-EEG channels.
ground_truth_baseline = raw_baseline.copy().pick(["ground_truth"]).get_data()[0]
ground_truth_30 = raw_stim_30.copy().pick(["ground_truth"]).get_data()[0]
ground_truth_100 = raw_stim_100.copy().pick(["ground_truth"]).get_data()[0]
# Stim marker encodes ON/OFF block timing; extract before channel drop.
stim_marker_30 = raw_stim_30.copy().pick(["stim"]).get_data()[0]
stim_marker_100 = raw_stim_100.copy().pick(["stim"]).get_data()[0]

for raw in (raw_baseline, raw_stim_30, raw_stim_100):
    raw.drop_channels(["STIM", "ground_truth"])

common_eeg_channels = sorted(set(raw_baseline.ch_names) & set(raw_stim_30.ch_names) & set(raw_stim_100.ch_names))
for raw in (raw_baseline, raw_stim_30, raw_stim_100):
    raw.pick(common_eeg_channels)

print(f"Loaded exp05 runs: channels={len(common_eeg_channels)} sfreq={sampling_rate_hz:.0f} Hz")


# ===== Block 1: Build windows =================================================
# detect_stim_blocks: stim marker (1-D) + sfreq → (onsets_samples, offsets_samples).
# Outputs feed directly into MNE event arrays and then mne.Epochs.
block_onsets_30, block_offsets_30 = preprocessing.detect_stim_blocks(stim_marker_30, sampling_rate_hz)
block_onsets_100, block_offsets_100 = preprocessing.detect_stim_blocks(stim_marker_100, sampling_rate_hz)

late_off_duration_s = LATE_OFF_STOP_S - LATE_OFF_START_S
late_off_duration_samples = int(round(late_off_duration_s * sampling_rate_hz))

off_durations_30_s = (block_onsets_30[1:] - block_offsets_30[:-1]) / sampling_rate_hz
off_durations_100_s = (block_onsets_100[1:] - block_offsets_100[:-1]) / sampling_rate_hz
shortest_off_duration_s = float(min(np.min(off_durations_30_s), np.min(off_durations_100_s)))
if shortest_off_duration_s <= LATE_OFF_STOP_S:
    raise RuntimeError(
        f"Late-OFF stop {LATE_OFF_STOP_S:.2f} s does not fit inside the shortest measured OFF gap {shortest_off_duration_s:.2f} s."
    )

late_off_starts_30 = block_offsets_30[:-1] + int(round(LATE_OFF_START_S * sampling_rate_hz))
late_off_starts_100 = block_offsets_100[:-1] + int(round(LATE_OFF_START_S * sampling_rate_hz))
valid_late_off_30 = late_off_starts_30 + late_off_duration_samples <= block_onsets_30[1:]
valid_late_off_100 = late_off_starts_100 + late_off_duration_samples <= block_onsets_100[1:]

# Package late-OFF starts as MNE event arrays: [sample_index, 0, event_id].
events_30 = preprocessing.build_event_array(late_off_starts_30[valid_late_off_30])
events_100 = preprocessing.build_event_array(late_off_starts_100[valid_late_off_100])
# Baseline: fixed-length windows starting at 2s to match the late-OFF duration.
events_baseline = mne.make_fixed_length_events(
    raw_baseline,
    start=BASELINE_FIRST_WINDOW_START_S,
    duration=late_off_duration_s,
    overlap=0.0,
)

print(
    f"Late-OFF windows: baseline={len(events_baseline)} 30%={len(events_30)} 100%={len(events_100)} "
    f"window={LATE_OFF_START_S:.1f}-{LATE_OFF_STOP_S:.1f}s after offset"
)


# ===== Ground-truth peak ======================================================
# Use MNE's Welch PSD directly on the GT arrays so the target band selection
# stays visible in the script instead of disappearing into a helper.
gt_psd_baseline, gt_frequencies_hz = mne.time_frequency.psd_array_welch(
    ground_truth_baseline,
    sfreq=sampling_rate_hz,
    fmin=GT_SEARCH_RANGE_HZ[0],
    fmax=GT_SEARCH_RANGE_HZ[1],
    n_fft=min(4096, ground_truth_baseline.size),
    verbose=False,
)
gt_peak_frequency_hz = float(gt_frequencies_hz[int(np.argmax(gt_psd_baseline))])
signal_band_hz = (
    max(VIEW_RANGE_HZ[0], gt_peak_frequency_hz - SIGNAL_HALF_WIDTH_HZ),
    min(VIEW_RANGE_HZ[1], gt_peak_frequency_hz + SIGNAL_HALF_WIDTH_HZ),
)
signal_band_width_hz = signal_band_hz[1] - signal_band_hz[0]

print(
    f"Measured baseline GT peak={gt_peak_frequency_hz:.2f} Hz "
    f"| SSD target band={signal_band_hz[0]:.2f}-{signal_band_hz[1]:.2f} Hz"
)


# ===== Fig 1: Timing windows ==================================================
timing_start_sample = int(round(5.0 * sampling_rate_hz))
timing_stop_sample = min(timing_start_sample + int(round(40.0 * sampling_rate_hz)), raw_stim_100.n_times)
timing_axis_seconds = np.arange(timing_stop_sample - timing_start_sample, dtype=float) / sampling_rate_hz

cz_index_100 = raw_stim_100.ch_names.index("Cz")
stim_100_trace_uv = raw_stim_100.get_data(start=timing_start_sample, stop=timing_stop_sample)[cz_index_100]
stim_marker_segment = stim_marker_100[timing_start_sample:timing_stop_sample]

timing_figure, (stim_axis, eeg_axis) = plt.subplots(2, 1, figsize=(12.0, 5.5), sharex=True, constrained_layout=True)
stim_axis.plot(timing_axis_seconds, stim_marker_segment, color="black", lw=1.0)
stim_axis.set_ylabel("STIM (V)")
stim_axis.set_title("100% run: measured ON blocks and late-OFF windows")
stim_axis.grid(alpha=0.2)

eeg_axis.plot(timing_axis_seconds, stim_100_trace_uv, color="steelblue", lw=0.8)
eeg_axis.set_ylabel("Cz (uV)")
eeg_axis.set_xlabel("Time from 5 s after record start (s)")
eeg_axis.grid(alpha=0.2)

for onset_sample, offset_sample in zip(block_onsets_100, block_offsets_100):
    if timing_start_sample <= onset_sample < timing_stop_sample:
        onset_s = (onset_sample - timing_start_sample) / sampling_rate_hz
        offset_s = (offset_sample - timing_start_sample) / sampling_rate_hz
        stim_axis.axvspan(onset_s, offset_s, color="gray", alpha=0.30)
        eeg_axis.axvspan(onset_s, offset_s, color="gray", alpha=0.30)

for late_off_start_sample in events_100[:, 0]:
    if timing_start_sample <= late_off_start_sample < timing_stop_sample:
        late_off_start_s = (late_off_start_sample - timing_start_sample) / sampling_rate_hz
        late_off_stop_s = late_off_start_s + late_off_duration_s
        stim_axis.axvspan(late_off_start_s, late_off_stop_s, color="cyan", alpha=0.35)
        eeg_axis.axvspan(late_off_start_s, late_off_stop_s, color="cyan", alpha=0.35)

timing_figure_path = OUTPUT_DIRECTORY / "fig1_timing_windows.png"
timing_figure.savefig(timing_figure_path, dpi=220)
plt.close(timing_figure)
print(f"Saved -> {timing_figure_path}")


# ===== Block 2: Select component ==============================================
# Keep SSD itself in the shared helper because the generalized eigen-decomposition
# is reused and non-trivial. The analysis assumption stays visible here:
# train on baseline late-OFF windows, then reuse the same filters on 30% and 100%.
n_components = min(N_COMPONENTS, len(common_eeg_channels))

# run_ssd: raw (EEG only) + events (window starts) + signal/noise bands + n_comp + epoch_duration
#          → spatial filters, patterns, eigenvalues trained on signal_band vs. flanking noise.
ssd_filters, spatial_patterns, eigenvalues = plot_helpers.run_ssd(
    raw_baseline,
    events_baseline,
    signal_band_hz,
    VIEW_RANGE_HZ,
    n_comp=n_components,
    epoch_duration_s=late_off_duration_s,
)

# Apply baseline-trained SSD filters to all conditions: channel space → component space.
epochs_view_baseline, component_epochs_baseline = plot_helpers.build_ssd_component_epochs(
    raw_baseline,
    events_baseline,
    ssd_filters,
    VIEW_RANGE_HZ,
    late_off_duration_s,
)
epochs_view_30, component_epochs_30 = plot_helpers.build_ssd_component_epochs(
    raw_stim_30,
    events_30,
    ssd_filters,
    VIEW_RANGE_HZ,
    late_off_duration_s,
)
epochs_view_100, component_epochs_100 = plot_helpers.build_ssd_component_epochs(
    raw_stim_100,
    events_100,
    ssd_filters,
    VIEW_RANGE_HZ,
    late_off_duration_s,
)


# ===== Rank baseline components ===============================================
# Band-pass GT to match the SSD signal band; used as coherence reference.
# Note: preprocessing.filter_signal wraps IIR butter — mne.filter.filter_data is an equivalent MNE-native alternative.
gt_band_baseline = preprocessing.filter_signal(ground_truth_baseline, sampling_rate_hz, signal_band_hz[0], signal_band_hz[1])
late_off_mask = np.zeros(raw_baseline.n_times, dtype=bool)
for start_sample in events_baseline[:, 0]:
    late_off_mask[int(start_sample):int(start_sample) + late_off_duration_samples] = True

raw_view = raw_baseline.copy().filter(*VIEW_RANGE_HZ, verbose=False)
raw_signal = raw_baseline.copy().filter(*signal_band_hz, verbose=False)

comp_numbers = np.arange(1, n_components + 1, dtype=int)
coherence_scores = []
peak_ratios = []
peak_freqs = []
for component_index in range(n_components):
    component_signal = ssd_filters[component_index] @ raw_signal.get_data()
    component_view = ssd_filters[component_index] @ raw_view.get_data()
    coherence_scores.append(
        preprocessing.compute_coherence_band(
            component_signal[late_off_mask],
            gt_band_baseline[late_off_mask],
            sampling_rate_hz,
            signal_band_hz[0],
            signal_band_hz[1],
        )
    )
    peak_ratios.append(
        preprocessing.compute_band_peak_ratio(
            component_view[late_off_mask],
            sampling_rate_hz,
            signal_band_hz,
            flank_width_hz=signal_band_width_hz,
            flank_gap_hz=0.5,
        )
    )
    peak_freqs.append(
        preprocessing.find_psd_peak_frequency(
            component_view[late_off_mask],
            sampling_rate_hz,
            VIEW_RANGE_HZ,
        )
    )

in_band_mask = [
    signal_band_hz[0] <= peak_freq_hz <= signal_band_hz[1]
    for peak_freq_hz in peak_freqs
]
candidate_indices = [index for index, is_in_band in enumerate(in_band_mask) if is_in_band]
selection_pool = candidate_indices if candidate_indices else list(range(n_components))
selected_component_index = max(
    selection_pool,
    key=lambda index: (coherence_scores[index], peak_ratios[index], float(eigenvalues[index])),
)
selected_component_number = selected_component_index + 1

print(
    f"Selected component={selected_component_number} "
    f"| coherence={coherence_scores[selected_component_index]:.3f} "
    f"| peak_ratio={peak_ratios[selected_component_index]:.2f}x "
    f"| peak_frequency={peak_freqs[selected_component_index]:.2f} Hz"
)


# ===== Fig 2: Baseline component ranking ======================================
selection_figure, (lambda_axis, metric_axis, peak_axis) = plt.subplots(1, 3, figsize=(13.8, 4.2), constrained_layout=True)

# TIMS_CONDITION_COLORS: shared color map keyed by condition name ("baseline", "30%", "100%") — keeps figures consistent across scripts.
lambda_axis.bar(comp_numbers, eigenvalues[:n_components], color=plot_helpers.TIMS_CONDITION_COLORS["baseline"], alpha=0.85)
lambda_axis.axvline(selected_component_number, color="darkorange", ls="--", lw=1.0)
lambda_axis.axhline(1.0, color="gray", ls="--", lw=0.8)
lambda_axis.set_xlabel("Baseline SSD component")
lambda_axis.set_ylabel("Eigenvalue lambda")
lambda_axis.set_title("Baseline SSD separation")

metric_axis.bar(comp_numbers, coherence_scores, color="steelblue", alpha=0.90)
metric_axis.axvline(selected_component_number, color="darkorange", ls="--", lw=1.0)
metric_axis.set_xlabel("Baseline SSD component")
metric_axis.set_ylabel("GT-band coherence")
metric_axis.set_title("Baseline GT match")

peak_axis.bar(comp_numbers, peak_ratios, color="slateblue", alpha=0.90)
peak_axis.axvline(selected_component_number, color="darkorange", ls="--", lw=1.0)
peak_axis.axhline(1.0, color="gray", ls="--", lw=0.8)
peak_axis.set_xlabel("Baseline SSD component")
peak_axis.set_ylabel("Peak / flank ratio")
peak_axis.set_title("Target-band peak sanity")

peak_frequency_axis = peak_axis.twinx()
peak_frequency_axis.scatter(comp_numbers, peak_freqs, color="black", s=25, zorder=3)
peak_frequency_axis.axhspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.45)
peak_frequency_axis.axhline(gt_peak_frequency_hz, color="darkorange", ls="--", lw=1.0)
peak_frequency_axis.set_ylabel("Peak frequency (Hz)")
peak_frequency_axis.set_ylim(VIEW_RANGE_HZ)

selection_figure.suptitle("exp05 baseline-trained SSD: component ranking", fontsize=13)
selection_figure_path = OUTPUT_DIRECTORY / "fig2_component_ranking.png"
selection_figure.savefig(selection_figure_path, dpi=220)
plt.close(selection_figure)
print(f"Saved -> {selection_figure_path}")


# ===== Block 3: Save outputs ==================================================
selected_pattern = spatial_patterns[:, selected_component_index]
selected_epochs_baseline = component_epochs_baseline[selected_component_index]
selected_epochs_30 = component_epochs_30[selected_component_index]
selected_epochs_100 = component_epochs_100[selected_component_index]

psd_baseline, frequencies_hz = mne.time_frequency.psd_array_welch(
    selected_epochs_baseline,
    sfreq=sampling_rate_hz,
    fmin=VIEW_RANGE_HZ[0],
    fmax=VIEW_RANGE_HZ[1],
    n_fft=min(1024, selected_epochs_baseline.shape[-1]),
    verbose=False,
)
psd_30, _ = mne.time_frequency.psd_array_welch(
    selected_epochs_30,
    sfreq=sampling_rate_hz,
    fmin=VIEW_RANGE_HZ[0],
    fmax=VIEW_RANGE_HZ[1],
    n_fft=min(1024, selected_epochs_30.shape[-1]),
    verbose=False,
)
psd_100, _ = mne.time_frequency.psd_array_welch(
    selected_epochs_100,
    sfreq=sampling_rate_hz,
    fmin=VIEW_RANGE_HZ[0],
    fmax=VIEW_RANGE_HZ[1],
    n_fft=min(1024, selected_epochs_100.shape[-1]),
    verbose=False,
)

mean_psd_baseline = psd_baseline.mean(axis=0)
mean_psd_30 = psd_30.mean(axis=0)
mean_psd_100 = psd_100.mean(axis=0)

selected_signal_band_baseline = preprocessing.filter_signal(selected_epochs_baseline, sampling_rate_hz, signal_band_hz[0], signal_band_hz[1]).reshape(-1)
selected_signal_band_30 = preprocessing.filter_signal(selected_epochs_30, sampling_rate_hz, signal_band_hz[0], signal_band_hz[1]).reshape(-1)
selected_signal_band_100 = preprocessing.filter_signal(selected_epochs_100, sampling_rate_hz, signal_band_hz[0], signal_band_hz[1]).reshape(-1)

# Extract GT windows per condition, band-pass, flatten — same shape as selected_signal_band_*.
gt_inputs = [
    (ground_truth_baseline, events_baseline, "baseline"),
    (ground_truth_30, events_30, "30%"),
    (ground_truth_100, events_100, "100%"),
]
gt_bands = {}
for gt_signal, events, label in gt_inputs:
    gt_epochs = np.asarray(
        [gt_signal[int(s):int(s) + late_off_duration_samples] for s in events[:, 0]],
        dtype=float,
    )
    gt_bands[label] = preprocessing.filter_signal(
        gt_epochs, sampling_rate_hz, signal_band_hz[0], signal_band_hz[1]
    ).reshape(-1)

ground_truth_band_baseline = gt_bands["baseline"]
ground_truth_band_30 = gt_bands["30%"]
ground_truth_band_100 = gt_bands["100%"]

transfer_rows = []
for label, selected_band, gt_band in [
    ("baseline", selected_signal_band_baseline, ground_truth_band_baseline),
    ("30%", selected_signal_band_30, ground_truth_band_30),
    ("100%", selected_signal_band_100, ground_truth_band_100),
]:
    transfer_rows.append(
        {
            "label": label,
            "coherence": preprocessing.compute_coherence_band(
                selected_band,
                gt_band,
                sampling_rate_hz,
                signal_band_hz[0],
                signal_band_hz[1],
            ),
            "peak_ratio": preprocessing.compute_band_peak_ratio(
                selected_band,
                sampling_rate_hz,
                signal_band_hz,
                flank_width_hz=signal_band_width_hz,
                flank_gap_hz=0.5,
            ),
        }
    )


# ===== Fig 3: Selected-component transfer ====================================
transfer_figure, (topomap_axis, psd_axis, text_axis) = plt.subplots(
    1,
    3,
    figsize=(13.8, 4.3),
    constrained_layout=True,
    gridspec_kw={"width_ratios": [1.0, 1.6, 1.2]},
)

mne.viz.plot_topomap(
    np.asarray(selected_pattern, dtype=float),
    epochs_view_baseline.info,
    ch_type="eeg",
    axes=topomap_axis,
    show=False,
    cmap=plot_helpers.TIMS_TOPO_CMAP,
)
topomap_axis.set_title(f"Selected comp {selected_component_number}\nlambda={float(eigenvalues[selected_component_index]):.2f}")

psd_axis.plot(frequencies_hz, mean_psd_baseline / np.max(mean_psd_baseline), color=plot_helpers.TIMS_CONDITION_COLORS["baseline"], lw=1.8, label="baseline")
psd_axis.plot(frequencies_hz, mean_psd_30 / np.max(mean_psd_30), color=plot_helpers.TIMS_CONDITION_COLORS["30%"], lw=1.8, label="30%")
psd_axis.plot(frequencies_hz, mean_psd_100 / np.max(mean_psd_100), color=plot_helpers.TIMS_CONDITION_COLORS["100%"], lw=1.8, label="100%")
psd_axis.axvspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.80)
psd_axis.axvline(gt_peak_frequency_hz, color="darkorange", ls="--", lw=1.0)
psd_axis.set_xlim(VIEW_RANGE_HZ)
psd_axis.set_xlabel("Frequency (Hz)")
psd_axis.set_ylabel("Relative PSD")
psd_axis.set_title("Selected component across runs")
psd_axis.grid(alpha=0.25)
psd_axis.legend(fontsize=8, loc="upper right")

text_axis.axis("off")
text_axis.text(
    0.0,
    1.0,
    "\n".join(
        [
            f"question: baseline-trained SSD recovery",
            f"gt_peak_hz={gt_peak_frequency_hz:.3f}",
            f"signal_band_hz=({signal_band_hz[0]:.3f}, {signal_band_hz[1]:.3f})",
            f"selected_component={selected_component_number}",
            *[
                f"{row['label']}: coherence={row['coherence']:.3f} peak_ratio={row['peak_ratio']:.2f}x"
                for row in transfer_rows
            ],
        ]
    ),
    va="top",
    family="monospace",
)

transfer_figure.suptitle("exp05 baseline-trained SSD: selected-component transfer", fontsize=13)
transfer_figure_path = OUTPUT_DIRECTORY / "fig3_selected_component_transfer.png"
transfer_figure.savefig(transfer_figure_path, dpi=220)
plt.close(transfer_figure)
print(f"Saved -> {transfer_figure_path}")


# ===== Summary ================================================================
summary_lines = [
    "exp05 ssd recovery skript version",
    f"gt_peak_frequency_hz={gt_peak_frequency_hz:.6f}",
    f"signal_band_hz=({signal_band_hz[0]:.6f}, {signal_band_hz[1]:.6f})",
    f"late_off_window_s=({LATE_OFF_START_S:.3f}, {LATE_OFF_STOP_S:.3f})",
    f"baseline_windows={len(events_baseline)}",
    f"windows_30={len(events_30)}",
    f"windows_100={len(events_100)}",
    f"selected_component={selected_component_number}",
    f"selected_lambda={float(eigenvalues[selected_component_index]):.6f}",
]
for row in transfer_rows:
    safe_label = row["label"].replace("%", "pct")
    summary_lines.append(f"{safe_label}_coherence={row['coherence']:.6f}")
    summary_lines.append(f"{safe_label}_peak_ratio={row['peak_ratio']:.6f}")

summary_path = OUTPUT_DIRECTORY / "ssd_summary.txt"
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
