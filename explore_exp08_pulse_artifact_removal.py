"""Remove EXP08 run01 single-pulse artifacts from raw EEG before epoching."""

from pathlib import Path
import warnings

import mne

import plot_helpers
import preprocessing


# ============================================================
# CONFIG
# ============================================================

data_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
stim_vhdr_path = data_directory / "exp08-STIM-pulse_run01_10-100.vhdr"  # run01 single pulses, not triplet run02
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
output_directory.mkdir(parents=True, exist_ok=True)

intensity_levels = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # percent MSO blocks
pulses_per_intensity = 20
inter_pulse_interval_s = 5.0
first_pulse_sample = 20530  # user-confirmed run01 first pulse peak

on_window_s = (-1.0, 2.0)  # match explore_exp08_pulses.py single-pulse epochs
excluded_channels = {"TP9", "Fp1", "TP10"}  # same retained EEG set as EXP08 extraction

baseline_window_ms = (-100, -10)  # local pre-pulse drift/noise estimate
artifact_start_ms = -10           # run01 EEG impulse peaks 3 ms before the scheduled pulse sample
min_artifact_end_ms = 20          # acute pulse is about 15 ms wide
max_artifact_end_ms = 200         # cap deletion before the physiological window dominates
peak_window_ms = (0, 20)          # peak-relative floor for thresholding
threshold_sd_multiplier = 5.0
peak_fraction = 0.02
debounce_ms = 20


def make_eeg_epochs(raw_eeg, event_samples, intensity_pct):
    """Create run01 ON epochs for one intensity from EEG-only raw data."""
    return mne.Epochs(
        raw_eeg,
        preprocessing.build_event_array(event_samples),
        {f"intensity_{intensity_pct}pct": 1},
        tmin=on_window_s[0],
        tmax=on_window_s[1],
        baseline=None,
        preload=True,
        verbose=False,
    )


# ============================================================
# 1) LOAD RUN01 RAW DATA
# ============================================================

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc*")
    raw_full = mne.io.read_raw_brainvision(str(stim_vhdr_path), preload=True, verbose=False)

sampling_rate_hz = float(raw_full.info["sfreq"])
if "stim" not in raw_full.ch_names or "ground_truth" not in raw_full.ch_names:
    raise RuntimeError("Run01 must contain both stim and ground_truth channels.")

non_eeg_channels = {"stim", "ground_truth"} | excluded_channels
raw_eeg = raw_full.copy().drop_channels(
    [channel for channel in raw_full.ch_names if channel in non_eeg_channels or channel.startswith("STI")]
)
if len(raw_eeg.ch_names) == 0:
    raise RuntimeError("No retained EEG channels remain after exclusions.")

pulse_count = len(intensity_levels) * pulses_per_intensity
pulse_samples = preprocessing.build_fixed_interval_event_samples(
    first_pulse_sample,
    pulse_count,
    inter_pulse_interval_s,
    sampling_rate_hz,
    raw_full.n_times,
    pre_margin_s=abs(baseline_window_ms[0]) / 1000.0,
    post_margin_s=max_artifact_end_ms / 1000.0,
)
intensity_pulses = preprocessing.split_event_samples_by_blocks(
    pulse_samples,
    intensity_levels,
    pulses_per_intensity,
)

print(f"Loaded run01: {raw_full.n_times / sampling_rate_hz:.1f} s, {len(raw_eeg.ch_names)} EEG channels")
print(f"Pulse schedule: {pulse_samples.size} pulses, first={pulse_samples[0]}, IPI={inter_pulse_interval_s:.1f} s")


# ============================================================
# 2) CLEAN CONTINUOUS EEG
# ============================================================

clean_data_v, all_durations_ms, all_thresholds_uv = preprocessing.interpolate_pulse_artifacts_by_threshold(
    raw_eeg.get_data(),
    pulse_samples,
    sampling_rate_hz,
    baseline_window_ms,
    artifact_start_ms,
    min_artifact_end_ms,
    max_artifact_end_ms,
    peak_window_ms,
    threshold_sd_multiplier,
    peak_fraction,
    debounce_ms,
)
raw_clean = raw_eeg.copy()
raw_clean._data[:] = clean_data_v


# ============================================================
# 3) REBUILD RUN01 EPOCHS AND SAVE OUTPUTS
# ============================================================

artifact_rows = []
threshold_rows = []
epochs_100_original = None
epochs_100_clean = None

for level_index, intensity_pct in enumerate(intensity_levels):
    event_samples = intensity_pulses[intensity_pct]
    epochs_original = make_eeg_epochs(raw_eeg, event_samples, intensity_pct)
    epochs_clean = make_eeg_epochs(raw_clean, event_samples, intensity_pct)

    output_path = output_directory / f"exp08_epochs_{intensity_pct}pct_on_artremoved-epo.fif"
    epochs_clean.save(output_path, overwrite=True, verbose=False)

    row_slice = slice(level_index * pulses_per_intensity, (level_index + 1) * pulses_per_intensity)
    durations_ms = all_durations_ms[row_slice]
    thresholds_uv = all_thresholds_uv[row_slice]
    artifact_rows.append((intensity_pct, durations_ms))
    threshold_rows.append((intensity_pct, thresholds_uv))
    print(
        f"{intensity_pct:3d}%: saved {output_path.name}; "
        f"artifact end mean={durations_ms.mean():.1f} ms, range=[{durations_ms.min():.0f}, {durations_ms.max():.0f}] ms"
    )

    if intensity_pct == 100:
        epochs_100_original = epochs_original
        epochs_100_clean = epochs_clean

if epochs_100_original is None or epochs_100_clean is None:
    raise RuntimeError("Missing 100% epochs for QC plotting.")

qc_path = plot_helpers.save_exp08_run01_pulse_artifact_qc(
    artifact_rows,
    epochs_100_original,
    epochs_100_clean,
    intensity_levels,
    output_directory / "exp08_pulse_artremoved_qc.png",
)


# ============================================================
# 4) WRITE SUMMARY
# ============================================================

summary_lines = [
    "EXP08 RUN01 SINGLE-PULSE ARTIFACT REMOVAL SUMMARY",
    "=" * 72,
    f"Source: {stim_vhdr_path.name}",
    f"Sampling rate: {sampling_rate_hz:.0f} Hz",
    f"EEG channels retained: {len(raw_eeg.ch_names)}",
    f"Pulse count: {pulse_samples.size} (10 intensities x 20 pulses)",
    f"First pulse sample: {first_pulse_sample}",
    "",
    "Config:",
    f"  Baseline window: {baseline_window_ms[0]} to {baseline_window_ms[1]} ms",
    f"  Artifact window starts: {artifact_start_ms} ms",
    f"  Search window: {min_artifact_end_ms} to {max_artifact_end_ms} ms",
    f"  Threshold: max({threshold_sd_multiplier:g} x baseline residual std, {peak_fraction * 100:.1f}% x peak)",
    f"  Debounce: {debounce_ms} ms",
    "",
    "Artifact end statistics by intensity:",
    f"{'Intensity':>10}  {'Mean ms':>8}  {'Std':>8}  {'Min':>8}  {'Max':>8}  {'Mean threshold uV':>17}",
]
for (intensity_pct, durations_ms), (_, thresholds_uv) in zip(artifact_rows, threshold_rows):
    summary_lines.append(
        f"{intensity_pct:>9}%  {durations_ms.mean():>8.1f}  {durations_ms.std():>8.1f}  "
        f"{durations_ms.min():>8.0f}  {durations_ms.max():>8.0f}  {thresholds_uv.mean():>17.1f}"
    )
summary_lines.extend([
    "",
    "Outputs:",
    "  exp08_epochs_{10..100}pct_on_artremoved-epo.fif",
    f"  {qc_path.name}",
    "  exp08_artremoved_dataviz.png (regenerate with explore_exp08_artremoved_dataviz.py)",
    "",
    "Invalid source avoided:",
    "  exp08t_* files belong to triplet run02 and are not used by this run01 cleanup.",
])
summary_text = "\n".join(summary_lines) + "\n"
for filename in ["exp08_run01_pulse_artifact_summary.txt", "exp08_artifact_removal_summary.txt"]:
    (output_directory / filename).write_text(summary_text, encoding="utf-8")

print(f"Saved: {qc_path.name}")
print("Saved: exp08_run01_pulse_artifact_summary.txt")
print("Saved: exp08_artifact_removal_summary.txt")
