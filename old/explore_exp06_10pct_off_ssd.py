"""How well does the saved exp06 baseline SSD filter recover the 10% late-OFF target?"""

from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import plot_helpers
import preprocessing


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
# Measured STIM amplitudes show that run01 starts with the true 10% block,
# while run02 begins at higher doses.
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
WEIGHTS_PATH = OUTPUT_DIRECTORY / "exp06_baseline_ssd_component1_weights.npz"

TEN_PERCENT_BLOCK_CYCLES = 20
LATE_OFF_START_S = 1.5
LATE_OFF_STOP_S = 3.2
FOCUS_CHANNEL = "O2"
TIMING_PADDING_BEFORE_S = 2.0
TIMING_PADDING_AFTER_S = 0.5
RECOVERED_COLOR = "steelblue"
GROUND_TRUTH_COLOR = "darkorange"
RAW_CHANNEL_COLOR = "black"


# ===== Load ===================================================================
# Reuse the saved baseline SSD artifact instead of rerunning SSD here.
weights_artifact = preprocessing.load_exp06_saved_ssd_artifact(WEIGHTS_PATH)
saved_channel_names = weights_artifact["channel_names"]
saved_sampling_rate_hz = weights_artifact["sampling_rate_hz"]
signal_band_hz = weights_artifact["signal_band_hz"]
view_band_hz = weights_artifact["view_band_hz"]
selected_component_index = weights_artifact["selected_component_index"]
selected_component_number = selected_component_index + 1
# One SSD weight vector turns each multichannel OFF epoch into one component trace.
selected_filter = weights_artifact["selected_filter"]
selected_pattern = weights_artifact["selected_pattern"]
selected_lambda = weights_artifact["selected_lambda"]
baseline_peak_hz = weights_artifact["baseline_peak_hz"]

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_stim_full.ch_names or "ground_truth" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channels: stim and ground_truth.")

sampling_rate_hz = float(raw_stim_full.info["sfreq"])

# Keep GT, STIM, and EEG separate because they play different roles below.
ground_truth_stim_v = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]
stim_marker_v = raw_stim_full.copy().pick(["stim"]).get_data()[0]
raw_stim_eeg = raw_stim_full.copy().pick(saved_channel_names)
preprocessing.validate_exp06_saved_ssd_against_raw(
    raw_stim_eeg,
    saved_channel_names,
    saved_sampling_rate_hz,
    selected_filter,
    focus_channel=FOCUS_CHANNEL,
)

print(f"exp06 10pct | {len(saved_channel_names)} ch | {sampling_rate_hz:.0f} Hz")


# ===== Block 1: Build 10% late-OFF epochs =====================================
# Reuse the validated block detector because the iTBS pulse train is non-trivial
# and the OFF windows must be anchored to measured offsets rather than nominal timing.
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(stim_marker_v, sampling_rate_hz)
if len(block_onsets_samples) < TEN_PERCENT_BLOCK_CYCLES + 1:
    raise RuntimeError(
        f"Need at least {TEN_PERCENT_BLOCK_CYCLES + 1} measured ON blocks to build the 10% late-OFF epochs, "
        f"but found {len(block_onsets_samples)}."
    )

# The first 20 cycles are the 10% block.
ten_percent_onsets = block_onsets_samples[: TEN_PERCENT_BLOCK_CYCLES + 1]
ten_percent_offsets = block_offsets_samples[: TEN_PERCENT_BLOCK_CYCLES + 1]
# Build late-OFF events from measured offsets, not nominal timing.
events_10pct_off, late_off_duration_s, late_off_duration_samples = preprocessing.build_late_off_events(
    ten_percent_onsets,
    ten_percent_offsets,
    sampling_rate_hz,
    LATE_OFF_START_S,
    LATE_OFF_STOP_S,
)
if len(events_10pct_off) != TEN_PERCENT_BLOCK_CYCLES:
    raise RuntimeError(
        f"Expected {TEN_PERCENT_BLOCK_CYCLES} valid 10% late-OFF events, but built {len(events_10pct_off)}."
    )

median_on_duration_s = float(np.median((block_offsets_samples - block_onsets_samples) / sampling_rate_hz))
median_off_duration_s = float(np.median((block_onsets_samples[1:] - block_offsets_samples[:-1]) / sampling_rate_hz))
print(f"blocks={len(block_onsets_samples)} | on={median_on_duration_s:.2f}s | off={median_off_duration_s:.2f}s")
print(f"10pct_off={len(events_10pct_off)} | window={LATE_OFF_START_S:.1f}-{LATE_OFF_STOP_S:.1f}s")


# ===== Block 2: Apply saved baseline filter ===================================
# Apply the saved baseline component 1 filter directly to the measured 10% OFF
# epochs so the stim run is evaluated with the same spatial solution.
# `epochs_view_10pct` stays in channel space; `selected_component_epochs` is the
# same OFF data after the saved SSD filter is applied.
epochs_view_10pct, selected_component_epochs = preprocessing.apply_exp06_saved_ssd_to_events(
    raw_stim_eeg,
    events_10pct_off,
    selected_filter,
    view_band_hz,
    late_off_duration_s,
)
# Keep the three matched late-OFF views: GT, one raw channel, and SSD.
focus_channel_epochs = epochs_view_10pct.copy().pick([FOCUS_CHANNEL]).get_data()[:, 0, :]
ground_truth_epochs = preprocessing.extract_event_windows(
    ground_truth_stim_v,
    events_10pct_off[:, 0],
    late_off_duration_samples,
)

# Band-limit all three signals before comparing traces and phase-locking.
focus_metrics = preprocessing.compute_band_limited_epoch_triplet_metrics(
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
mean_ground_truth_trace_z = focus_metrics["mean_reference_trace_z"]
mean_focus_channel_trace_z = focus_metrics["mean_signal_trace_z"]
mean_recovered_trace_z = recovered_metrics["mean_signal_trace_z"]
itpc_focus = focus_metrics["itpc_curve"]
itpc_recovered = recovered_metrics["itpc_curve"]

# Check whether the transferred filter still peaks at the baseline rhythm.
recovered_peak_hz = preprocessing.find_psd_peak_frequency(
    selected_component_epochs.reshape(-1),
    sampling_rate_hz,
    view_band_hz,
)

print(f"comp={selected_component_number} | raw={FOCUS_CHANNEL} | peak={recovered_peak_hz:.2f} Hz | ref={baseline_peak_hz:.2f} Hz")


# ===== Block 3: Save figures ==================================================
# Figure 1: timing orientation.
timing_start_sample = max(0, ten_percent_onsets[0] - int(round(TIMING_PADDING_BEFORE_S * sampling_rate_hz)))
timing_stop_sample = min(
    raw_stim_full.n_times,
    events_10pct_off[-1, 0] + late_off_duration_samples + int(round(TIMING_PADDING_AFTER_S * sampling_rate_hz)),
)
timing_axis_s = (
    np.arange(timing_stop_sample - timing_start_sample, dtype=float) / sampling_rate_hz
    + timing_start_sample / sampling_rate_hz
    - ten_percent_onsets[0] / sampling_rate_hz
)
stim_segment = stim_marker_v[timing_start_sample:timing_stop_sample]

plot_helpers.save_timing_windows_figure(
    timing_axis_s=timing_axis_s,
    stim_segment=stim_segment,
    onsets_s=ten_percent_onsets[:TEN_PERCENT_BLOCK_CYCLES] / sampling_rate_hz - ten_percent_onsets[0] / sampling_rate_hz,
    offsets_s=ten_percent_offsets[:TEN_PERCENT_BLOCK_CYCLES] / sampling_rate_hz - ten_percent_onsets[0] / sampling_rate_hz,
    late_off_starts_s=events_10pct_off[:, 0] / sampling_rate_hz - ten_percent_onsets[0] / sampling_rate_hz,
    late_off_duration_s=late_off_duration_samples / sampling_rate_hz,
    output_path=OUTPUT_DIRECTORY / "exp06_10pct_off_timing_windows.png",
    title="20 valid late-OFF windows fit inside the 10% block",
)
timing_path = OUTPUT_DIRECTORY / "exp06_10pct_off_timing_windows.png"

# Figure 2: plain PSD plus saved SSD topography.
psd_summary_path = OUTPUT_DIRECTORY / "exp06_10pct_off_psd_comparison.png"
psd_freqs_hz, ground_truth_mean_psd = preprocessing.compute_mean_epoch_psd(
    ground_truth_epochs, sampling_rate_hz, view_band_hz, n_fft=min(1024, late_off_duration_samples)
)
_, focus_channel_mean_psd = preprocessing.compute_mean_epoch_psd(
    focus_channel_epochs, sampling_rate_hz, view_band_hz, n_fft=min(1024, late_off_duration_samples)
)
_, recovered_mean_psd = preprocessing.compute_mean_epoch_psd(
    selected_component_epochs, sampling_rate_hz, view_band_hz, n_fft=min(1024, late_off_duration_samples)
)
ground_truth_mean_psd /= np.max(ground_truth_mean_psd) + 1e-30
focus_channel_mean_psd /= np.max(focus_channel_mean_psd) + 1e-30
recovered_mean_psd /= np.max(recovered_mean_psd) + 1e-30
plot_helpers.save_psd_topomap_comparison(
    spatial_pattern=selected_pattern,
    info=epochs_view_10pct.info,
    spectral_ratio=selected_lambda,
    psd_freqs_hz=psd_freqs_hz,
    psd_lines=[
        ("GT", ground_truth_mean_psd, GROUND_TRUTH_COLOR, 2.0),
        (FOCUS_CHANNEL, focus_channel_mean_psd, RAW_CHANNEL_COLOR, 1.6),
        ("SSD", recovered_mean_psd, RECOVERED_COLOR, 2.0),
    ],
    signal_band_hz=signal_band_hz,
    reference_frequency_hz=baseline_peak_hz,
    view_band_hz=view_band_hz,
    output_path=psd_summary_path,
    title="SSD has the sharpest 12.45 Hz late-OFF peak",
    ylabel="Normalized PSD",
    topomap_title=f"Saved SSD pattern | lambda={selected_lambda:.2f}",
)

# Figure 3: mean late-OFF shape comparison.
timecourse_path = OUTPUT_DIRECTORY / "exp06_10pct_off_trace_comparison.png"
trace_axis_s = epochs_view_10pct.times + LATE_OFF_START_S
plot_helpers.save_line_comparison_figure(
    x_axis_s=trace_axis_s,
    line_specs=[
        ("GT", mean_ground_truth_trace_z, GROUND_TRUTH_COLOR, 2.2),
        (FOCUS_CHANNEL, mean_focus_channel_trace_z, RAW_CHANNEL_COLOR, 1.7),
        ("SSD comp 1", mean_recovered_trace_z, RECOVERED_COLOR, 2.0),
    ],
    output_path=timecourse_path,
    xlabel="Time after measured offset (s)",
    ylabel="Band-limited mean trace (z)",
    title=f"Raw {FOCUS_CHANNEL} is anti-phase to GT; SSD keeps the GT phase",
    zero_line=True,
)

# Figure 4: GT-locked ITPC time course.
itpc_path = OUTPUT_DIRECTORY / "exp06_10pct_off_itpc_comparison.png"
itpc_floor = min(float(np.min(itpc_focus)), float(np.min(itpc_recovered)))
itpc_ceiling = max(float(np.max(itpc_focus)), float(np.max(itpc_recovered)))
itpc_figure, itpc_axis = plt.subplots(figsize=(9.8, 4.1), constrained_layout=True)
itpc_axis.plot(trace_axis_s, itpc_focus, color=RAW_CHANNEL_COLOR, lw=1.8, label=f"GT vs {FOCUS_CHANNEL}")
itpc_axis.plot(trace_axis_s, itpc_recovered, color=RECOVERED_COLOR, lw=2.2, label="GT vs SSD")
itpc_axis.text(
    0.015,
    0.97,
    "Near-ceiling scale to show the small SSD advantage",
    transform=itpc_axis.transAxes,
    va="top",
    fontsize=8.5,
    bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 2.5},
)
itpc_axis.set(
    xlabel="Time after measured offset (s)",
    ylabel="ITPC",
    ylim=(max(0.0, itpc_floor - 0.00015), min(1.0002, itpc_ceiling + 0.00005)),
    title=f"SSD stays slightly more GT-locked than {FOCUS_CHANNEL} across late-OFF",
)
itpc_axis.legend(frameon=False, loc="lower right")
plot_helpers.style_clean_axis(itpc_axis, grid_alpha=0.15)
itpc_figure.savefig(itpc_path, dpi=220)
plt.close(itpc_figure)

print(f"saved={timing_path.name}")
print(f"saved={psd_summary_path.name}")
print(f"saved={timecourse_path.name}")
print(f"saved={itpc_path.name}")
