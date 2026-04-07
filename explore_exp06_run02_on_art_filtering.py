"""Export run02 ON-window SSD ITPC courses for a claim-first intensity figure."""

from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import mne
import numpy as np

import plot_helpers
import preprocessing


# ============================================================
# CONFIG
# ============================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"  # measured run02 stimulation recording
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")  # explicit output folder
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]  # run02 dose order
BLOCK_CYCLES_PER_INTENSITY = 20  # ON cycles per block
ON_WINDOW_S = (0.3, 1.5)  # accepted ON window
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}  # keep the run02 EEG set aligned with the baseline SSD work

TARGET_CENTER_HZ = 12.451172  # measured baseline GT peak carried forward as the target frequency
SIGNAL_HALF_WIDTH_HZ = 0.5  # narrower band keeps the ON metric tied to the measured 12.45 Hz target
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
VIEW_BAND_HZ = (4.0, 20.0)  # broad inspection band for SSD fit and ranking
N_SSD_COMPONENTS = 6  # small candidate pool keeps selection readable

RUN02_STIM_THRESHOLD_FRACTION = 0.08  # recover weak first block
TIMING_PADDING_BEFORE_S = 2.0  # timing figure context
TIMING_PADDING_AFTER_S = 0.5  # timing figure tail
INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]  # dose blocks

TIMING_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_timing.png"  # orientation figure
EXPORT_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_itpc.npz"  # machine-readable export
MANIFEST_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_itpc.txt"  # short export manifest


# ============================================================
# PIPELINE
# ============================================================
# run02 recording
#   |
# measured ON timing
#   |
# accepted ON windows
#   |
# per-block ON SSD fit and GT-based component selection
#   |
# SSD ITPC-course export + orientation figure


# ============================================================
# 1) LOAD THE RUN02 RECORDING
# ============================================================
# 1.1 Read BrainVision run02
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

# 1.2 Check required channels
if "stim" not in raw_stim_full.ch_names or "ground_truth" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channels: stim and ground_truth.")

# 1.3 Pull timing and GT traces
sfreq = float(raw_stim_full.info["sfreq"])
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]  # stim channel voltage trace
gt_trace = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]  # recorded GT voltage trace

# 1.4 Keep the run02 EEG set explicit
raw_eeg = raw_stim_full.copy().drop_channels(
    [
        channel_name
        for channel_name in raw_stim_full.ch_names
        if channel_name.lower() in {"stim", "ground_truth"}
        or channel_name.startswith("STI")
        or channel_name in EXCLUDED_CHANNELS
    ]
)
if len(raw_eeg.ch_names) == 0:
    raise RuntimeError("No retained EEG channels remain after removing stim, GT, and excluded channels.")


# ============================================================
# 2) RECOVER MEASURED ON TIMING
# ============================================================
# 2.1 Detect measured ON blocks
# The first 10% block is weak, so the
# lower detector threshold is part of
# the scientific timing definition here.
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace,
    sfreq,
    threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION,
)

# 2.2 Check expected block count
required_block_count = len(RUN02_INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY
if len(block_onsets_samples) < required_block_count:
    raise RuntimeError(
        f"Need at least {required_block_count} measured ON blocks to analyze run02, "
        f"but found {len(block_onsets_samples)}."
    )

# 2.3 Derive timing summaries
median_on_s = float(np.median((block_offsets_samples - block_onsets_samples) / sfreq))
median_off_s = float(np.median((block_onsets_samples[1:] - block_offsets_samples[:-1]) / sfreq))
window_len = float(ON_WINDOW_S[1] - ON_WINDOW_S[0])
window_size = int(round(window_len * sfreq))  # fixed ON-window size in samples
start_shift = int(round(ON_WINDOW_S[0] * sfreq))  # ON-window start shift in samples


# ============================================================
# 3) ANALYZE EACH DOSE BLOCK
# ============================================================
summary_rows = []  # one summary dict per dose block
timing_windows = []  # accepted ON starts by dose block
reference_band_trace = preprocessing.filter_signal(gt_trace, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
time_axis_s = None  # shared ON-window sample axis

# 3.1 Loop across intensities
for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    # 3.1.1 Slice this dose block
    block_start_index = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    block_stop_index = block_start_index + BLOCK_CYCLES_PER_INTENSITY
    dose_onsets = block_onsets_samples[block_start_index:block_stop_index]  # this block's ON starts
    dose_offsets = block_offsets_samples[block_start_index:block_stop_index]  # this block's ON offsets

    if len(dose_onsets) != BLOCK_CYCLES_PER_INTENSITY or len(dose_offsets) != BLOCK_CYCLES_PER_INTENSITY:
        raise RuntimeError(f"{intensity_label} in run02 does not contain the required 20 measured ON blocks.")

    # 3.1.2 Build accepted windows
    # Shift each ON block into the accepted
    # interior segment, then reject windows
    # that would overrun the measured offset.
    window_onsets = dose_onsets + start_shift  # candidate window start samples
    window_keep = window_onsets + window_size <= dose_offsets  # valid-window boolean mask
    event_samples = window_onsets[window_keep]  # accepted start sample array
    events_on = preprocessing.build_event_array(event_samples)  # MNE-style event array
    if len(events_on) != BLOCK_CYCLES_PER_INTENSITY:
        raise RuntimeError(
            f"Expected {BLOCK_CYCLES_PER_INTENSITY} valid ON windows for {intensity_label}, "
            f"but built {len(events_on)}."
        )

    # 3.1.3 Fit SSD on this run02 ON block
    # The ON claim should be earned from run02 itself.
    # We therefore fit the spatial filters on the accepted
    # run02 ON windows instead of transferring baseline weights.
    n_components = min(N_SSD_COMPONENTS, len(raw_eeg.ch_names))
    ssd_filters, _, _ = plot_helpers.run_ssd(
        raw_eeg,
        events_on,
        SIGNAL_BAND_HZ,
        VIEW_BAND_HZ,
        n_comp=n_components,
        epoch_duration_s=window_len,
    )
    epochs_view, component_epochs = plot_helpers.build_ssd_component_epochs(
        raw_eeg,
        events_on,
        ssd_filters,
        VIEW_BAND_HZ,
        window_len,
    )

    # 3.1.4 Extract the matched GT windows
    ground_truth_epochs = preprocessing.extract_event_windows(
        gt_trace,
        events_on[:, 0],
        window_size,
    )
    if time_axis_s is None:
        time_axis_s = np.asarray(epochs_view.times, dtype=float)

    # 3.1.5 Score each ON-fitted component against recorded GT
    # The chosen component should stay tied to the target band,
    # not merely maximize variance in one ON block.
    score_mask = np.zeros(raw_eeg.n_times, dtype=bool)
    for event_start_sample in events_on[:, 0]:
        score_mask[int(event_start_sample):int(event_start_sample) + window_size] = True
    signal_raw = raw_eeg.copy().filter(*SIGNAL_BAND_HZ, verbose=False)
    view_raw = raw_eeg.copy().filter(*VIEW_BAND_HZ, verbose=False)
    coherence_scores, peak_ratios, peak_freqs = preprocessing.rank_ssd_components_against_reference(
        spatial_filters=ssd_filters,
        raw_signal_band=signal_raw,
        raw_view_band=view_raw,
        evaluation_mask=score_mask,
        reference_band_signal=reference_band_trace,
        sampling_rate_hz=sfreq,
        signal_band_hz=SIGNAL_BAND_HZ,
        view_range_hz=VIEW_BAND_HZ,
    )
    candidate_indices = [
        component_index
        for component_index, component_peak_hz in enumerate(peak_freqs)
        if SIGNAL_BAND_HZ[0] <= component_peak_hz <= SIGNAL_BAND_HZ[1]
    ]
    selection_pool = candidate_indices if candidate_indices else list(range(n_components))
    selected_component_index = max(
        selection_pool,
        key=lambda component_index: (
            coherence_scores[component_index],
            peak_ratios[component_index],
        ),
    )
    selected_component_epochs = np.asarray(component_epochs[selected_component_index], dtype=float)
    selected_component_number = selected_component_index + 1

    # 3.1.6 Compute the SSD ITPC course
    # This is the primary export because the figure should
    # compare SSD GT-locking time courses across intensities.
    recovered_metrics = preprocessing.compute_band_limited_epoch_triplet_metrics(
        selected_component_epochs,
        ground_truth_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
    )

    # 3.1.7 Store block summaries
    intensity_pct = int(intensity_label.replace("%", ""))
    summary_rows.append(
        {
            "label": intensity_label,
            "intensity_pct": intensity_pct,
            "event_count": int(len(events_on)),
            "ssd_mean_gt_locking": float(np.mean(recovered_metrics["itpc_curve"])),
            "ssd_itpc_curve": np.asarray(recovered_metrics["itpc_curve"], dtype=float).copy(),
            "selected_component_number": int(selected_component_number),
            "component_peak_hz": float(peak_freqs[selected_component_index]),
            "component_coherence": float(coherence_scores[selected_component_index]),
            "component_peak_ratio": float(peak_ratios[selected_component_index]),
            "on_event_starts": events_on[:, 0].copy(),
        }
    )
    timing_windows.append(events_on[:, 0].copy())


# ============================================================
# 4) SAVE ORIENTATION FIGURE AND EXPORT
# ============================================================
# 4.1 Save the ON-window timing orientation figure
timing_start_sample = max(0, block_onsets_samples[0] - int(round(TIMING_PADDING_BEFORE_S * sfreq)))
timing_stop_sample = min(
    raw_stim_full.n_times,
    timing_windows[-1][-1] + window_size + int(round(TIMING_PADDING_AFTER_S * sfreq)),
)
timing_axis_s = (
    np.arange(timing_stop_sample - timing_start_sample, dtype=float) / sfreq
    + timing_start_sample / sfreq
    - block_onsets_samples[0] / sfreq
)
stim_segment = stim_trace[timing_start_sample:timing_stop_sample]
plot_helpers.save_multiblock_timing_windows_figure(
    timing_axis_s=timing_axis_s,
    stim_segment=stim_segment,
    block_onsets_s=block_onsets_samples[:required_block_count] / sfreq - block_onsets_samples[0] / sfreq,
    block_offsets_s=block_offsets_samples[:required_block_count] / sfreq - block_onsets_samples[0] / sfreq,
    window_starts_by_block_s=[
        row["on_event_starts"] / sfreq - block_onsets_samples[0] / sfreq for row in summary_rows
    ],
    window_duration_s=window_len,
    intensity_colors=INTENSITY_COLORS,
    output_path=TIMING_FIGURE_PATH,
    title="run02 ON windows come from the measured interior of each dose block",
    xlabel="Time from first run02 ON block (s)",
    annotation_text="Gray = measured ON blocks\nBlue shades = accepted run02 ON windows",
)

# 4.2 Save the machine-readable ITPC export
if time_axis_s is None:
    raise RuntimeError("No SSD ITPC time axis was built.")
np.savez(
    EXPORT_PATH,
    intensity_labels=np.asarray([row["label"] for row in summary_rows], dtype=str),
    intensity_pct=np.asarray([row["intensity_pct"] for row in summary_rows], dtype=int),
    event_counts=np.asarray([row["event_count"] for row in summary_rows], dtype=int),
    sampling_rate_hz=np.asarray([sfreq], dtype=float),
    on_window_s=np.asarray(ON_WINDOW_S, dtype=float),
    signal_band_hz=np.asarray(SIGNAL_BAND_HZ, dtype=float),
    time_axis_s=np.asarray(time_axis_s, dtype=float),
    ssd_itpc_curves=np.asarray([row["ssd_itpc_curve"] for row in summary_rows], dtype=float),
    selected_component_numbers=np.asarray([row["selected_component_number"] for row in summary_rows], dtype=int),
    selected_component_peak_hz=np.asarray([row["component_peak_hz"] for row in summary_rows], dtype=float),
    selected_component_coherence=np.asarray([row["component_coherence"] for row in summary_rows], dtype=float),
    selected_component_peak_ratio=np.asarray([row["component_peak_ratio"] for row in summary_rows], dtype=float),
)


# ============================================================
# 5) SAVE SHORT REPORT
# ============================================================
# 5.1 Write the export manifest
summary_lines = [
    "exp06 run02 ON SSD ITPC export",
    "question=Does the selected ON-fitted SSD show an intensity-dependent GT-referenced ITPC course across run02 ON windows?",
    f"stim_vhdr_path={STIM_VHDR_PATH}",
    f"excluded_channels={sorted(EXCLUDED_CHANNELS)}",
    f"signal_band_hz=({SIGNAL_BAND_HZ[0]:.6f}, {SIGNAL_BAND_HZ[1]:.6f})",
    f"view_band_hz=({VIEW_BAND_HZ[0]:.6f}, {VIEW_BAND_HZ[1]:.6f})",
    f"reference_peak_hz={TARGET_CENTER_HZ:.6f}",
    f"median_on_duration_s={median_on_s:.6f}",
    f"median_off_duration_s={median_off_s:.6f}",
    f"stim_threshold_fraction={RUN02_STIM_THRESHOLD_FRACTION:.3f}",
    f"on_window_s=({ON_WINDOW_S[0]:.6f}, {ON_WINDOW_S[1]:.6f})",
    "itpc_definition=Cross-epoch phase-locking between the selected SSD component and recorded GT after target-band filtering and Hilbert phase extraction.",
    f"timing_figure={TIMING_FIGURE_PATH.name}",
    f"export_npz={EXPORT_PATH.name}",
    "selection_note=Each block fits SSD on run02 ON windows, then keeps the in-band component with the strongest GT-band coherence and peak-to-flank ratio; if none are in-band, it keeps the strongest-ranked component.",
    "",
]
for row in summary_rows:
    summary_lines.extend(
        [
            f"{row['label']}",
            f"event_count={row['event_count']}",
            f"selected_component={row['selected_component_number']}",
            f"ssd_mean_gt_locking={row['ssd_mean_gt_locking']:.6f}",
            f"selected_component_peak_hz={row['component_peak_hz']:.6f}",
            f"selected_component_coherence={row['component_coherence']:.6f}",
            f"selected_component_peak_ratio={row['component_peak_ratio']:.6f}",
            "",
        ]
    )
MANIFEST_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

# 5.2 Print console summary
print(f"run=run02 | blocks={len(summary_rows)} | export={EXPORT_PATH.name}")
print(
    f"10% ssd_gt_locking={summary_rows[0]['ssd_mean_gt_locking']:.4f} "
    f"| comp={summary_rows[0]['selected_component_number']}"
)
print(f"timing={TIMING_FIGURE_PATH.name} | manifest={MANIFEST_PATH.name}")
