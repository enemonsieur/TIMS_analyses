"""Pre/post resting-state exp04 band power and wPLI summary."""
from pathlib import Path

import mne
import numpy as np
from scipy.signal import hilbert, welch

import plot_helpers
import preprocessing


def summarize_metric_rows(metric_rows):
    """Reduce epoch-level rows to condition summaries and pre-based percent change."""
    grouped_values = {}
    for row in metric_rows:
        grouping_key = (
            str(row["condition"]),
            str(row["metric_family"]),
            str(row["metric_name"]),
            str(row["roi_or_network"]),
        )
        grouped_values.setdefault(grouping_key, []).append(float(row["value"]))

    baseline_lookup = {}
    summary_rows = []
    for grouping_key, values in grouped_values.items():
        values_array = np.asarray(values, dtype=float)
        condition, metric_family, metric_name, roi_or_network = grouping_key
        baseline_lookup[(metric_family, metric_name, roi_or_network, condition)] = float(values_array.mean())

    for grouping_key, values in grouped_values.items():
        values_array = np.asarray(values, dtype=float)
        condition, metric_family, metric_name, roi_or_network = grouping_key
        baseline_mean = baseline_lookup[(metric_family, metric_name, roi_or_network, "Pre")]
        percent_change_vs_pre = 100.0 * (float(values_array.mean()) - baseline_mean) / (baseline_mean + 1e-30)
        summary_rows.append(
            {
                "condition": condition,
                "metric_family": metric_family,
                "metric_name": metric_name,
                "roi_or_network": roi_or_network,
                "mean": float(values_array.mean()),
                "median": float(np.median(values_array)),
                "std": float(values_array.std(ddof=1)) if values_array.size > 1 else 0.0,
                "n_epochs": int(values_array.size),
                "percent_change_vs_pre": float(percent_change_vs_pre),
            }
        )
    return summary_rows


def mean_pair_value(matrix_2d, index_pairs):
    """Average a small predefined set of channel-pair values."""
    if not index_pairs:
        raise ValueError("index_pairs is empty.")
    pair_values = [float(matrix_2d[row_index, column_index]) for row_index, column_index in index_pairs]
    return float(np.mean(np.asarray(pair_values, dtype=float)))


# ============================================================
# FIXED INPUTS
# Edit only this block.
# ============================================================
INPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
PRE_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-baseline-fullOFFstim-run01.vhdr"
POST_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-baseline-after--fullOFFstim-run02.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP04_dynamics_analysis")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

QC_CHANNELS = ["F3", "CP5", "F5"]
BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]
ROI_CHANNELS = {
    "left_motor": ["F3", "FC5", "FC1", "C5", "C1", "CP5"],
    "right_motor": ["F4", "FC6", "FC2", "C6", "C2", "CP6"],
}
INTERHEMISPHERIC_CHANNEL_PAIRS = [
    ("F3", "F4"),
    ("FC5", "FC6"),
    ("FC1", "FC2"),
    ("C5", "C6"),
    ("C1", "C2"),
    ("CP5", "CP6"),
]
WPLI_PLOT_CHANNEL_PAIRS = [
    ("F3", "FC5"),
    ("F3", "FC1"),
    ("FC5", "FC1"),
    ("FC5", "C5"),
    ("FC1", "C1"),
    ("C5", "CP5"),
    ("C1", "CP5"),
    ("FC5", "CP5"),
    ("FC1", "CP5"),
    ("F4", "FC6"),
    ("F4", "FC2"),
    ("FC6", "FC2"),
    ("FC6", "C6"),
    ("FC2", "C2"),
    ("C6", "CP6"),
    ("C2", "CP6"),
    ("FC6", "CP6"),
    ("FC2", "CP6"),
    ("F3", "F4"),
    ("FC5", "FC1"),
    ("FC5", "FC6"),
    ("FC1", "FC2"),
    ("C5", "C6"),
    ("C1", "C2"),
    ("CP5", "CP6"),
]
POWER_BANDS_HZ = {
    "alpha": (8.0, 12.0),
    "beta": (13.0, 30.0),
    "low_gamma": (30.0, 40.0),
}
WPLI_BANDS_HZ = {
    "theta": (4.0, 7.0),
    "alpha": (8.0, 12.0),
    "beta": (13.0, 30.0),
    "low_gamma": (30.0, 40.0),
}
REFERENCE_CHANNELS = "average"
NOTCH_HZ = 50.0
FILTER_BAND_HZ = (1.0, 45.0)
EPOCH_LENGTH_S = 4.0


# ============================================================
# 1) LOAD PRE AND POST RESTING RECORDINGS
# ============================================================
raw_pre = mne.io.read_raw_brainvision(str(PRE_VHDR_PATH), preload=True, verbose=False)
raw_post = mne.io.read_raw_brainvision(str(POST_VHDR_PATH), preload=True, verbose=False)
print(
    f"QC load: pre duration={raw_pre.n_times / raw_pre.info['sfreq']:.1f} s, "
    f"post duration={raw_post.n_times / raw_post.info['sfreq']:.1f} s"
)
available_qc_channels = [channel_name for channel_name in QC_CHANNELS if channel_name in raw_pre.ch_names and channel_name in raw_post.ch_names]
missing_qc_channels = [channel_name for channel_name in QC_CHANNELS if channel_name not in available_qc_channels]
channel_qc_path = None
if available_qc_channels:
    channel_qc_path = plot_helpers.plot_exp04_channel_artifact_qc(
        pre_raw=raw_pre.copy().pick_types(eeg=True),
        post_raw=raw_post.copy().pick_types(eeg=True),
        channel_names=available_qc_channels,
        output_directory=OUTPUT_DIRECTORY,
    )
print(f"QC requested channels present in both runs: {available_qc_channels}")
if missing_qc_channels:
    print(f"QC requested channels missing from recording: {missing_qc_channels}")


# ============================================================
# 2) CHANNEL SELECTION AND SHARED PREPROCESSING
# ============================================================
# Average reference is applied before ROI picking so both hemispheres are
# measured against the same full-head EEG context.
required_roi_channels = ROI_CHANNELS["left_motor"] + ROI_CHANNELS["right_motor"]
for raw in (raw_pre, raw_post):
    raw.pick_types(eeg=True)
    raw.drop_channels([channel_name for channel_name in BAD_CHANNELS if channel_name in raw.ch_names])
    missing_required_channels = [channel_name for channel_name in required_roi_channels if channel_name not in raw.ch_names]
    if missing_required_channels:
        raise ValueError(f"Missing required ROI channels after bad-channel drop: {missing_required_channels}")

if raw_pre.ch_names != raw_post.ch_names:
    raise ValueError("Pre and post EEG channels do not match after dropping bad channels.")
if float(raw_pre.info["sfreq"]) != float(raw_post.info["sfreq"]):
    raise ValueError("Sampling rate mismatch across pre and post recordings.")

for raw in (raw_pre, raw_post):
    raw.set_eeg_reference(ref_channels=REFERENCE_CHANNELS, verbose=False)
    raw.notch_filter([NOTCH_HZ], notch_widths=2.0, verbose=False)
    raw.filter(FILTER_BAND_HZ[0], FILTER_BAND_HZ[1], verbose=False)
    raw.pick_channels(required_roi_channels, ordered=True)

analysis_channel_names = list(raw_pre.ch_names)
left_roi_indices = [analysis_channel_names.index(channel_name) for channel_name in ROI_CHANNELS["left_motor"]]
right_roi_indices = [analysis_channel_names.index(channel_name) for channel_name in ROI_CHANNELS["right_motor"]]
within_left_pairs = [(left_roi_indices[i], left_roi_indices[j]) for i in range(len(left_roi_indices)) for j in range(i + 1, len(left_roi_indices))]
within_right_pairs = [(right_roi_indices[i], right_roi_indices[j]) for i in range(len(right_roi_indices)) for j in range(i + 1, len(right_roi_indices))]
interhemispheric_pairs = [
    (analysis_channel_names.index(left_name), analysis_channel_names.index(right_name))
    for left_name, right_name in INTERHEMISPHERIC_CHANNEL_PAIRS
]
wpli_plot_pairs = [
    (
        channel_name_a,
        channel_name_b,
        analysis_channel_names.index(channel_name_a),
        analysis_channel_names.index(channel_name_b),
    )
    for channel_name_a, channel_name_b in WPLI_PLOT_CHANNEL_PAIRS
]
sfreq = float(raw_pre.info["sfreq"])
print(f"QC channels: {analysis_channel_names}")
print(f"QC reference/filter: {REFERENCE_CHANNELS}, notch={NOTCH_HZ:.0f} Hz, bandpass={FILTER_BAND_HZ}")


# ============================================================
# 3) BUILD FIXED RESTING-STATE EPOCHS
# ============================================================
# Equal 4 s non-overlapping epochs keep the PSD and wPLI units identical
# across pre and post without inventing pseudo-trials of different lengths.
epoch_samples = int(round(EPOCH_LENGTH_S * sfreq))
epoch_tmax_s = EPOCH_LENGTH_S - (1.0 / sfreq)
pre_event_samples = np.arange(0, raw_pre.n_times - epoch_samples + 1, epoch_samples, dtype=int)
post_event_samples = np.arange(0, raw_post.n_times - epoch_samples + 1, epoch_samples, dtype=int)
events_pre = np.column_stack(
    [pre_event_samples, np.zeros(pre_event_samples.size, dtype=int), np.ones(pre_event_samples.size, dtype=int)]
)
events_post = np.column_stack(
    [post_event_samples, np.zeros(post_event_samples.size, dtype=int), np.ones(post_event_samples.size, dtype=int)]
)
epochs_pre = mne.Epochs(raw_pre, events_pre, event_id=1, tmin=0.0, tmax=epoch_tmax_s, baseline=None, preload=True, verbose=False)
epochs_post = mne.Epochs(raw_post, events_post, event_id=1, tmin=0.0, tmax=epoch_tmax_s, baseline=None, preload=True, verbose=False)
pre_epoch_data = epochs_pre.get_data(copy=True)
post_epoch_data = epochs_post.get_data(copy=True)
print(f"QC events: pre={len(events_pre)}, post={len(events_post)}")
print(f"QC epochs: pre={pre_epoch_data.shape}, post={post_epoch_data.shape}")


# ============================================================
# 4) COMPUTE EPOCH-LEVEL BAND POWER
# ============================================================
band_power_rows = []
summary_input_rows = []
frequencies_hz = None
psd_frequency_mask = None
roi_mean_psd_by_condition = {"Pre": {}, "Post": {}}
condition_epoch_sets = {
    "Pre": pre_epoch_data,
    "Post": post_epoch_data,
}
roi_index_lookup = {
    "left_motor": left_roi_indices,
    "right_motor": right_roi_indices,
}

for condition_name, epoch_data in condition_epoch_sets.items():
    roi_mean_psd_per_epoch = {
        "left_motor": [],
        "right_motor": [],
    }

    for epoch_index, epoch_array in enumerate(epoch_data):
        epoch_frequencies_hz, epoch_psd = welch(
            epoch_array,
            fs=sfreq,
            axis=-1,
            nperseg=min(epoch_array.shape[-1], epoch_samples),
        )
        epoch_psd = np.asarray(epoch_psd, dtype=float)
        if not np.all(np.isfinite(epoch_psd)):
            raise RuntimeError(f"Non-finite PSD values in {condition_name} epoch {epoch_index}.")

        if frequencies_hz is None:
            frequencies_hz = np.asarray(epoch_frequencies_hz, dtype=float)
            psd_frequency_mask = (frequencies_hz >= FILTER_BAND_HZ[0]) & (frequencies_hz <= FILTER_BAND_HZ[1])

        for roi_name, roi_indices in roi_index_lookup.items():
            roi_psd = epoch_psd[roi_indices]
            roi_mean_psd = roi_psd.mean(axis=0)
            roi_mean_psd_per_epoch[roi_name].append(roi_mean_psd)

            roi_total_power = float(
                np.mean(
                    np.trapz(
                        roi_psd[:, psd_frequency_mask],
                        frequencies_hz[psd_frequency_mask],
                        axis=-1,
                    )
                )
            )

            for band_name, (band_low_hz, band_high_hz) in POWER_BANDS_HZ.items():
                band_mask = (frequencies_hz >= band_low_hz) & (frequencies_hz <= band_high_hz)
                if not np.any(band_mask):
                    raise ValueError(f"Band {band_name} does not overlap the PSD frequencies.")

                band_power_per_channel = np.trapz(
                    roi_psd[:, band_mask],
                    frequencies_hz[band_mask],
                    axis=-1,
                )
                absolute_power = float(np.mean(band_power_per_channel))
                relative_power = float(absolute_power / (roi_total_power + 1e-30))

                band_power_rows.append(
                    {
                        "condition": condition_name,
                        "epoch_index": int(epoch_index),
                        "band": band_name,
                        "power_type": "absolute",
                        "roi": roi_name,
                        "value": absolute_power,
                    }
                )
                band_power_rows.append(
                    {
                        "condition": condition_name,
                        "epoch_index": int(epoch_index),
                        "band": band_name,
                        "power_type": "relative",
                        "roi": roi_name,
                        "value": relative_power,
                    }
                )
                summary_input_rows.append(
                    {
                        "condition": condition_name,
                        "metric_family": "power",
                        "metric_name": f"{band_name}_absolute",
                        "roi_or_network": roi_name,
                        "value": absolute_power,
                    }
                )
                summary_input_rows.append(
                    {
                        "condition": condition_name,
                        "metric_family": "power",
                        "metric_name": f"{band_name}_relative",
                        "roi_or_network": roi_name,
                        "value": relative_power,
                    }
                )

    for roi_name, roi_psd_values in roi_mean_psd_per_epoch.items():
        roi_mean_psd_by_condition[condition_name][roi_name] = np.mean(
            np.asarray(roi_psd_values, dtype=float),
            axis=0,
        )

print(f"QC power rows: {len(band_power_rows)}")


# ============================================================
# 5) COMPUTE EPOCH-LEVEL WPLI
# ============================================================
wpli_rows = []
wpli_pair_rows = []
for condition_name, epoch_data in (("Pre", pre_epoch_data), ("Post", post_epoch_data)):
    for band_name, (band_low_hz, band_high_hz) in WPLI_BANDS_HZ.items():
        for epoch_index, epoch_array in enumerate(epoch_data):
            filtered_epoch = mne.filter.filter_data(epoch_array, sfreq, l_freq=band_low_hz, h_freq=band_high_hz, verbose=False)
            analytic_epoch = hilbert(filtered_epoch, axis=-1)
            imaginary_cross_spectrum = np.imag(
                analytic_epoch[:, np.newaxis, :] * np.conjugate(analytic_epoch[np.newaxis, :, :])
            )
            numerator = np.abs(np.mean(imaginary_cross_spectrum, axis=-1))
            denominator = np.mean(np.abs(imaginary_cross_spectrum), axis=-1) + 1e-30
            epoch_wpli = numerator / denominator
            np.fill_diagonal(epoch_wpli, np.nan)

            within_left_wpli = mean_pair_value(epoch_wpli, within_left_pairs)
            within_right_wpli = mean_pair_value(epoch_wpli, within_right_pairs)
            interhemispheric_wpli = mean_pair_value(epoch_wpli, interhemispheric_pairs)
            if not np.all(np.isfinite([within_left_wpli, within_right_wpli, interhemispheric_wpli])):
                raise RuntimeError(f"Non-finite wPLI values in {condition_name} {band_name} epoch {epoch_index}.")

            for summary_name, summary_value in (
                ("within_left", within_left_wpli),
                ("within_right", within_right_wpli),
                ("interhemispheric", interhemispheric_wpli),
            ):
                wpli_rows.append(
                    {
                        "condition": condition_name,
                        "epoch_index": int(epoch_index),
                        "band": band_name,
                        "summary_type": summary_name,
                        "value": float(summary_value),
                    }
                )
                summary_input_rows.append(
                    {
                        "condition": condition_name,
                        "metric_family": "wpli",
                        "metric_name": band_name,
                        "roi_or_network": summary_name,
                        "value": float(summary_value),
                    }
                )

            for channel_name_a, channel_name_b, channel_index_a, channel_index_b in wpli_plot_pairs:
                wpli_pair_rows.append(
                    {
                        "condition": condition_name,
                        "epoch_index": int(epoch_index),
                        "band": band_name,
                        "channel_a": channel_name_a,
                        "channel_b": channel_name_b,
                        "value": float(epoch_wpli[channel_index_a, channel_index_b]),
                    }
                )

print(f"QC wPLI rows: {len(wpli_rows)}")


# ============================================================
# 6) SUMMARIZE THE EPOCH-LEVEL METRICS
# ============================================================
summary_rows = summarize_metric_rows(summary_input_rows)
print(f"QC summary rows: {len(summary_rows)}")


# ============================================================
# 7) SAVE CSV OUTPUTS
# ============================================================
band_power_csv_path = OUTPUT_DIRECTORY / "exp04_pre_post_band_power_epochs.csv"
wpli_csv_path = OUTPUT_DIRECTORY / "exp04_pre_post_wpli_epochs.csv"
wpli_pair_csv_path = OUTPUT_DIRECTORY / "exp04_pre_post_wpli_pairs.csv"
summary_csv_path = OUTPUT_DIRECTORY / "exp04_pre_post_rs_summary.csv"
preprocessing.save_metrics_rows_csv(band_power_rows, band_power_csv_path)
preprocessing.save_metrics_rows_csv(wpli_rows, wpli_csv_path)
preprocessing.save_metrics_rows_csv(wpli_pair_rows, wpli_pair_csv_path)
preprocessing.save_metrics_rows_csv(summary_rows, summary_csv_path)


# ============================================================
# 8) SAVE FIGURES
# ============================================================
figure_paths = plot_helpers.plot_exp04_pre_post_resting_summary(
    frequencies_hz=frequencies_hz,
    roi_mean_psd_by_condition=roi_mean_psd_by_condition,
    summary_rows=summary_rows,
    wpli_pair_rows=wpli_pair_rows,
    output_directory=OUTPUT_DIRECTORY,
)


# ============================================================
# 9) PRINT SHORT SUMMARY
# ============================================================
print(f"Saved -> {band_power_csv_path}")
print(f"Saved -> {wpli_csv_path}")
print(f"Saved -> {wpli_pair_csv_path}")
print(f"Saved -> {summary_csv_path}")
for figure_path in figure_paths.values():
    print(f"Saved -> {figure_path}")
if channel_qc_path is not None:
    print(f"Saved -> {channel_qc_path}")
print(f"Epochs: pre={pre_epoch_data.shape[0]}, post={post_epoch_data.shape[0]}")
print(f"Retained channels: {analysis_channel_names}")
print(f"Main ROIs: {ROI_CHANNELS}")
