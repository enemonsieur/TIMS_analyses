"""Split-segment spectral analysis for exp04 stimulation epochs."""
from pathlib import Path

import mne
import numpy as np
from mne.time_frequency import tfr_array_morlet

import plot_helpers
import preprocessing


# ============================================================
# FIXED INPUTS
# Edit only this block.
# ============================================================
INPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-stim-mod-50hz-pulse-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP04_spectral_analysis")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]
ROI_CHANNELS = ["FC5", "FC1", "Pz", "CP5", "CP6"]


# ============================================================
# 1) LOAD THE STIM RECORDING
# ============================================================
raw_stim = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)


# ============================================================
# 2) KEEP ONLY THE EXP04 ROI USED IN THE TEP SCRIPT
# ============================================================
# Use the same fixed bad-channel list and ROI as the TEP script so the
# spectral branch stays directly comparable to that exp04 analysis.
raw_stim.pick_types(eeg=True).drop_channels([channel for channel in BAD_CHANNELS if channel in raw_stim.ch_names])
raw_stim.pick_channels([channel for channel in ROI_CHANNELS if channel in raw_stim.ch_names], ordered=True)
if "CP6" not in raw_stim.ch_names:
    raise ValueError("CP6 must remain available for the exp04 timing detection.")

sfreq = float(raw_stim.info["sfreq"])


# ============================================================
# 3) DETECT THE STIM BLOCKS FROM CP6 EXACTLY LIKE THE TEP SCRIPT
# ============================================================
# CP6 shows the clearest step at stimulation onset in this recording.
cp6_data = raw_stim.copy().pick(["CP6"]).get_data()[0]
# The first 10 s are clean off-period and anchor the derivative threshold.
cp6_data = cp6_data - np.mean(cp6_data[:10000])
candidate_onsets = np.where(np.abs(np.diff(cp6_data)) > 0.01)[0] + 1
if candidate_onsets.size == 0:
    raise ValueError("Manual onset detection found no candidates.")

stim_block_onsets_samples = [int(candidate_onsets[0])]
for sample_index in candidate_onsets[1:]:
    if sample_index - stim_block_onsets_samples[-1] > 1200:
        stim_block_onsets_samples.append(int(sample_index))
stim_block_onsets_samples = np.asarray(stim_block_onsets_samples, dtype=int)
# In exp04 the actual pulse falls 1008 samples after the block onset step.
stim_pulse_onsets_samples = stim_block_onsets_samples + 1008
median_interval_s = float(np.median(np.diff(stim_pulse_onsets_samples)) / sfreq)
print(f"QC onset detection: {stim_pulse_onsets_samples.size} pulses, median interval {median_interval_s:.3f} s")


# ============================================================
# 4) BUILD WIDE EPOCHS AROUND EACH PULSE
# ============================================================
# Keep the full 4 s cycle around each pulse visible before any split decisions.
events = np.column_stack(
    [
        stim_pulse_onsets_samples,
        np.zeros(stim_pulse_onsets_samples.size, dtype=int),
        np.ones(stim_pulse_onsets_samples.size, dtype=int),
    ]
).astype(int)
epochs_wide = mne.Epochs(raw_stim, events, event_id=1, tmin=-3.0, tmax=3.0, baseline=None, preload=True, verbose=False)
wide_data = epochs_wide.get_data(copy=True)
wide_times_s = epochs_wide.times
print(f"QC wide epochs: {wide_data.shape}")


# ============================================================
# 5) SPLIT PRE / EXCLUDED / POST BEFORE ANY SPECTRAL PROCESSING
# ============================================================
# The 1 s stimulation train occupies [-1.0, 0.0] s and the post-pulse edge
# remains contaminated until +0.08 s, so the spectral branch must never run
# a filter or wavelet transform across that gap.
# These masks define the raw clean segments only. Later display and summary
# windows start later because the Morlet edge guard trims the interpretable post range.
pre_mask = (wide_times_s >= -2.9) & (wide_times_s <= -1.0)
post_mask = (wide_times_s >= 0.08) & (wide_times_s <= 2.9)
pre_epochs = wide_data[:, :, pre_mask]
post_epochs = wide_data[:, :, post_mask]
pre_times_s = wide_times_s[pre_mask]
post_times_s = wide_times_s[post_mask]
print(f"QC split segments: pre={pre_epochs.shape}, post={post_epochs.shape}")


# ============================================================
# 6) COMPUTE SEGMENT-SAFE MORLET POWER AND POST LOG-RATIO ERSP
# ============================================================
# Keep the spectral choices visible here rather than hiding them in defaults.
baseline_window_s = (-2.75, -1.25)
display_window_s = (0.2, 2.3)
summary_windows_s = {"early": (0.30, 1.30), "late": (1.30, 2.30)}
band_definitions_hz = {
    "theta": (4.0, 7.0),
    "alpha": (8.0, 12.0),
    "beta": (13.0, 30.0),
    "low_gamma": (30.0, 40.0),
}
frequencies_hz = np.arange(4.0, 37.0, 1.0, dtype=float)
n_cycles = np.clip(frequencies_hz / 2.0, 3.0, 7.0)
half_wavelet_s = n_cycles / (2.0 * frequencies_hz)
edge_guard_seconds = float(np.max(half_wavelet_s))
pad_samples = int(np.ceil(edge_guard_seconds * sfreq))
if pad_samples < 1:
    raise RuntimeError("Computed non-positive Morlet padding.")

pre_duration_s = float(pre_times_s[-1] - pre_times_s[0] + 1.0 / sfreq)
post_duration_s = float(post_times_s[-1] - post_times_s[0] + 1.0 / sfreq)
if pre_duration_s < baseline_window_s[1] - baseline_window_s[0]:
    raise ValueError("Pre segment is too short for the requested baseline window.")
if post_duration_s < display_window_s[1] - display_window_s[0]:
    raise ValueError("Post segment is too short for the requested display window.")
if pre_epochs.shape[-1] < 3 or post_epochs.shape[-1] < 3:
    raise ValueError("Each clean segment must contain at least 3 samples.")

baseline_mask = (pre_times_s >= baseline_window_s[0]) & (pre_times_s <= baseline_window_s[1])
valid_post_time_mask = np.zeros((frequencies_hz.size, post_times_s.size), dtype=bool)
for frequency_index, frequency_guard_s in enumerate(half_wavelet_s):
    valid_post_time_mask[frequency_index] = (
        (post_times_s >= max(display_window_s[0], float(post_times_s[0] + frequency_guard_s)))
        & (post_times_s <= min(display_window_s[1], float(post_times_s[-1] - frequency_guard_s)))
    )
if not np.any(baseline_mask):
    raise ValueError("Baseline window does not overlap the clean pre segment.")
if not np.any(valid_post_time_mask):
    raise ValueError("Display window does not overlap any Morlet-safe post samples.")

pre_epochs_centered = pre_epochs - pre_epochs.mean(axis=-1, keepdims=True)
post_epochs_centered = post_epochs - post_epochs.mean(axis=-1, keepdims=True)
pre_epochs_padded = np.pad(pre_epochs_centered, ((0, 0), (0, 0), (pad_samples, pad_samples)), mode="reflect")
post_epochs_padded = np.pad(post_epochs_centered, ((0, 0), (0, 0), (pad_samples, pad_samples)), mode="reflect")

pre_power = np.asarray(
    tfr_array_morlet(
        pre_epochs_padded,
        sfreq=sfreq,
        freqs=frequencies_hz,
        n_cycles=n_cycles,
        output="power",
        zero_mean=True,
    )[..., pad_samples:-pad_samples],
    dtype=np.float32,
)
post_power = np.asarray(
    tfr_array_morlet(
        post_epochs_padded,
        sfreq=sfreq,
        freqs=frequencies_hz,
        n_cycles=n_cycles,
        output="power",
        zero_mean=True,
    )[..., pad_samples:-pad_samples],
    dtype=np.float32,
)
if pre_power.shape[-1] != pre_times_s.size or post_power.shape[-1] != post_times_s.size:
    raise RuntimeError("Morlet power shape does not match the split time axes.")
if not np.all(np.isfinite(pre_power)) or not np.all(np.isfinite(post_power)):
    raise RuntimeError("Morlet power contains non-finite values.")

baseline_power = pre_power[..., baseline_mask].mean(axis=-1, keepdims=True)
if np.any(baseline_power <= 0):
    raise RuntimeError("Baseline power must stay positive for log-ratio normalization.")
post_power_logratio = np.asarray(
    10.0 * np.log10((post_power + 1e-30) / (baseline_power + 1e-30)),
    dtype=np.float32,
)
print(f"QC spectral summary: pre={pre_power.shape}, post={post_power.shape}")


# ============================================================
# 7) SUMMARIZE THE POST BAND METRICS
# ============================================================
trial_metrics_rows = []
summary_rows = []
for band_name, (low_hz, high_hz) in band_definitions_hz.items():
    band_mask = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
    if not np.any(band_mask):
        raise ValueError(f"Band {band_name} does not overlap the Morlet frequencies.")
    pre_baseline_per_epoch = pre_power[:, :, band_mask, :][..., baseline_mask].mean(axis=(1, 2, 3))
    band_valid_post_mask = valid_post_time_mask[band_mask].all(axis=0)
    for window_name, (window_start_s, window_stop_s) in summary_windows_s.items():
        window_mask = (
            (post_times_s >= window_start_s)
            & (post_times_s <= window_stop_s)
            & band_valid_post_mask
        )
        if not np.any(window_mask):
            raise ValueError(f"Summary window {window_name} does not overlap the Morlet-safe post segment.")
        post_power_per_epoch = post_power[:, :, band_mask, :][..., window_mask].mean(axis=(1, 2, 3))
        post_logratio_per_epoch = post_power_logratio[:, :, band_mask, :][..., window_mask].mean(axis=(1, 2, 3))
        for epoch_index, (baseline_value, post_power_value, logratio_value) in enumerate(
            zip(pre_baseline_per_epoch, post_power_per_epoch, post_logratio_per_epoch, strict=True)
        ):
            trial_metrics_rows.append(
                {
                    "epoch_index": int(epoch_index),
                    "band": band_name,
                    "window": window_name,
                    "window_start_s": float(window_start_s),
                    "window_stop_s": float(window_stop_s),
                    "pre_baseline_power": float(baseline_value),
                    "post_window_power": float(post_power_value),
                    "post_logratio_db": float(logratio_value),
                }
            )
        summary_rows.append(
            {
                "band": band_name,
                "window": window_name,
                "window_start_s": float(window_start_s),
                "window_stop_s": float(window_stop_s),
                "mean_post_logratio_db": float(post_logratio_per_epoch.mean()),
                "std_post_logratio_db": float(post_logratio_per_epoch.std(ddof=1)) if post_logratio_per_epoch.size > 1 else 0.0,
                "n_epochs": int(post_logratio_per_epoch.size),
            }
        )


# ============================================================
# 8) SAVE CSV OUTPUTS
# ============================================================
trial_csv_path = OUTPUT_DIRECTORY / "exp04_post_band_trial_metrics.csv"
summary_csv_path = OUTPUT_DIRECTORY / "exp04_post_band_summary.csv"
preprocessing.save_metrics_rows_csv(trial_metrics_rows, trial_csv_path)
preprocessing.save_metrics_rows_csv(summary_rows, summary_csv_path)


# ============================================================
# 9) SAVE QC AND ERSP FIGURES
# ============================================================
figure_paths = plot_helpers.plot_exp04_split_segment_spectral_summary(
    epoch_times_s=wide_times_s,
    cp6_epochs=wide_data[:, raw_stim.ch_names.index("CP6"), :],
    roi_epochs=wide_data,
    spectral_summary={
        "frequencies_hz": frequencies_hz,
        "post_times_s": post_times_s,
        "post_power_logratio": post_power_logratio,
        "valid_post_time_mask": valid_post_time_mask,
        "band_window_metrics": trial_metrics_rows,
        "band_definitions_hz": band_definitions_hz,
        "summary_windows_s": summary_windows_s,
    },
    output_directory=OUTPUT_DIRECTORY,
)


# ============================================================
# 10) PRINT SHORT QC SUMMARY
# ============================================================
kept_post_times_s = np.asarray(post_times_s, dtype=float)[valid_post_time_mask.any(axis=0)]
print(f"Detected stim pulses: {stim_pulse_onsets_samples.size}")
print(f"Median pulse interval (s): {median_interval_s:.3f}")
print(f"Wide epochs retained: {len(epochs_wide)}")
print(f"Pre segment samples: {pre_epochs.shape[-1]}")
print(f"Post segment samples: {post_epochs.shape[-1]}")
print(f"Baseline window (s): {baseline_window_s[0]:.2f} to {baseline_window_s[1]:.2f}")
print(f"Kept post time range (s): {kept_post_times_s[0]:.2f} to {kept_post_times_s[-1]:.2f}")
print(f"Theta-safe post start (s): {post_times_s[valid_post_time_mask[(frequencies_hz >= 4.0) & (frequencies_hz <= 7.0)].all(axis=0)][0]:.2f}")
print(f"Edge guard (s): {edge_guard_seconds:.3f}")
print(f"ROI channels: {raw_stim.ch_names}")
print(f"Saved -> {trial_csv_path}")
print(f"Saved -> {summary_csv_path}")
for figure_path in figure_paths.values():
    print(f"Saved -> {figure_path}")
