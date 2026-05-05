"""Does drift-free find_peaks artifact removal work across all channels and intensities?"""

import os, warnings
os.environ["QT_API"] = "pyqt6"; os.environ["MPLBACKEND"] = "qtagg"
import matplotlib; matplotlib.use("QtAgg", force=True)
import matplotlib.pyplot as plt; matplotlib.rcParams["backend"] = "QtAgg"; plt.ion()
import mne
import numpy as np
from scipy.signal import find_peaks


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# raw VHDR (28 EEG, 1000 Hz, ~360 s)
# ├─ Load: drop stim / GT / excluded → 28 EEG channels
# ├─ Schedule: 20530 + np.arange(200) × IPI → 200 pulse onsets
# │           split into 10 intensity blocks (10%→100%, 20 pulses each)
# ├─ Clean: for each intensity × each channel × each pulse:
# │         baseline_mean → artifact_deviation → recovery_threshold → find_peaks → interpolate
# ├─ Fig 1: worst channel + Oz at INSPECT_INTENSITY — mean epoch before vs after
# └─ Fig 2: heatmap of residual artifact amplitude after cleaning (channels × intensities)


# ════════════════════════════════════════════════════════════════════════════
# 1) LOAD RECORDING
# ════════════════════════════════════════════════════════════════════════════

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    raw = mne.io.read_raw_brainvision(
        r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp08-STIM-pulse_run01_10-100.vhdr",
        preload=True, verbose=False,
    )
# → MNE Raw: (28 EEG + stim + GT) @ 1000 Hz, ~360 s
sampling_rate = raw.info["sfreq"]
eeg_channels = [ch for ch in raw.ch_names
                if ch not in {"stim", "ground_truth", "TP9", "Fp1", "TP10"}
                and not ch.startswith("STI")]
raw_data = raw.get_data(picks=eeg_channels)  # (n_channels=28, n_samples) in Volts


# ════════════════════════════════════════════════════════════════════════════
# 2) PULSE SCHEDULE
# ════════════════════════════════════════════════════════════════════════════

# ══ 2.1 Fixed-interval pulse schedule ══
all_pulse_onsets = 20530 + np.arange(200) * int(round(5.0 * sampling_rate))
# → 200 sample indices: first pulse at sample 20530, one pulse every 5.0 s

# ══ 2.2 Group into intensity blocks ══
# 200 pulses ordered 10%→100%, 20 consecutive pulses per intensity level
pulses_by_intensity = {
    pct: all_pulse_onsets[block_idx * 20 : (block_idx + 1) * 20]
    for block_idx, pct in enumerate([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
}
# → pulses_by_intensity: {10: (20,), 20: (20,), ..., 100: (20,)} sample indices


# ════════════════════════════════════════════════════════════════════════════
# 3) ARTIFACT DETECTION + REMOVAL HELPERS
# ════════════════════════════════════════════════════════════════════════════

def ms_to_samples(milliseconds):
    """Convert a duration in milliseconds to the nearest integer sample count."""
    return int(round(milliseconds / 1000 * sampling_rate))


def find_artifact_end_sample(signal, pulse_onset):
    """Return the sample index where the TMS artifact has recovered to near-baseline.

    Strategy:
      1. Estimate baseline level and noise from the −100 to −10ms pre-pulse window.
         This avoids the artifact onset (which starts ~−3ms) and is long enough for
         a stable noise estimate.
      2. Compute artifact_deviation = |signal − baseline_mean|. Peaks in this curve
         mark artifact oscillations above baseline.
      3. Recovery threshold = max(5× baseline SD, 2% × first-20ms peak amplitude).
         - The 5× SD term sets a noise floor.
         - The 2% term ensures the threshold scales with TMS intensity: at 100% MSO
           the artifact can reach ~80,000 µV, so even 2% is far above noise.
      4. Find all peaks above threshold in the 20–200ms post-pulse search window.
         The LAST such peak is where the artifact finally drops below threshold.

    Returns:
        artifact_end: sample index of the last detectable artifact oscillation
    """
    pre_pulse_indices = np.arange(
        pulse_onset + ms_to_samples(-100),
        pulse_onset + ms_to_samples(-10),
    )
    baseline_mean  = np.mean(signal[pre_pulse_indices])
    baseline_noise = np.std(signal[pre_pulse_indices])   # noise floor for threshold

    artifact_deviation = np.abs(signal - baseline_mean)  # unsigned deviation from pre-pulse level

    # 2% floor scales threshold with TMS intensity so it doesn't get swamped at 100%
    first_20ms_peak_amplitude = np.max(artifact_deviation[pulse_onset : pulse_onset + ms_to_samples(20)])
    recovery_threshold = max(5.0 * baseline_noise, 0.02 * first_20ms_peak_amplitude)

    # Search window: starts at 20ms (past the main TMS spike), ends at 200ms (before physiology)
    search_start = pulse_onset + ms_to_samples(20)
    search_end   = pulse_onset + ms_to_samples(200)
    above_threshold_peak_offsets, _ = find_peaks(
        artifact_deviation[search_start:search_end],
        height=recovery_threshold,
    )

    # Last above-threshold peak = final artifact oscillation → artifact end
    if len(above_threshold_peak_offsets):
        return search_start + above_threshold_peak_offsets[-1]
    else:
        return search_start  # artifact too brief; conservative fallback: 20ms


def interpolate_artifact_window(signal, pulse_onset, artifact_end):
    """Replace the artifact window with a straight line bridging the two clean endpoints.

    Artifact window: −25ms (where TIMS transient onset is visible) to artifact_end.
    Endpoints are anchored to the actual signal values on both sides, so there is
    no discontinuity at the join.

    Returns:
        signal_cleaned: copy of signal with artifact window replaced by linear fill
    """
    artifact_window_start  = pulse_onset + ms_to_samples(-25)  # TIMS transient visible from ~−25ms
    artifact_window_indices = np.arange(artifact_window_start, artifact_end)

    signal_cleaned = signal.copy()
    signal_cleaned[artifact_window_indices] = np.linspace(
        signal[artifact_window_start],  # left anchor: actual pre-artifact signal value
        signal[artifact_end],           # right anchor: actual post-artifact signal value
        artifact_window_indices.size,
        endpoint=False,
    )
    return signal_cleaned


# ════════════════════════════════════════════════════════════════════════════
# 4) CLEAN ALL CHANNELS FOR ALL INTENSITIES
# ════════════════════════════════════════════════════════════════════════════

# For each intensity: start from raw and clean its 20 pulses across all 28 channels.
# Independent per intensity so we can compare residuals per intensity in Fig 2.
cleaned_data_by_intensity = {}
for intensity_pct, pulse_onsets in pulses_by_intensity.items():
    cleaned = raw_data.copy()
    for channel_idx in range(len(eeg_channels)):
        for pulse_onset in pulse_onsets.astype(int):
            artifact_end = find_artifact_end_sample(cleaned[channel_idx], pulse_onset)
            cleaned[channel_idx] = interpolate_artifact_window(
                cleaned[channel_idx], pulse_onset, artifact_end
            )
    cleaned_data_by_intensity[intensity_pct] = cleaned
    print(f"  cleaned {intensity_pct}%")




# ════════════════════════════════════════════════════════════════════════════
# 6) FIG 1 — WORST CHANNEL + Oz: MEAN EPOCH BEFORE vs AFTER
# ════════════════════════════════════════════════════════════════════════════

epoch_time_ms = np.arange(-100, 300)  # time axis: −100 to +299 ms relative to pulse onset

def compute_mean_pulse_epoch(data, channel_idx, pulse_onsets):
    """Average 20 pulse-locked epochs (−100 to +300ms) for one channel."""
    return np.mean(
        [data[channel_idx, int(onset) - 100 : int(onset) + 300] for onset in pulse_onsets],
        axis=0,
    )

fig1, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
for ax, channel_idx, subplot_title in zip(
    axes,
    [worst_channel_idx, oz_channel_idx],
    [f"worst: {eeg_channels[worst_channel_idx]}  "
     f"({mean_peak_amplitude_per_channel[worst_channel_idx] * 1e6:.0f} µV peak)", "Oz"],
):
    ax.plot(epoch_time_ms,
            compute_mean_pulse_epoch(raw_data,       channel_idx, inspect_pulse_onsets) * 1e6,
            lw=0.9, label="raw")
    ax.plot(epoch_time_ms,
            compute_mean_pulse_epoch(inspect_cleaned, channel_idx, inspect_pulse_onsets) * 1e6,
            lw=0.9, label="cleaned")
    ax.axvline(0, color="k", lw=0.6, ls="--")
    ax.set_ylabel("µV")
    ax.set_title(f"{subplot_title}  |  {INSPECT_INTENSITY}%  |  mean over 20 pulses")
    ax.legend(fontsize=8)
axes[1].set_xlabel("ms from pulse onset")
fig1.suptitle("Drift-free find_peaks artifact removal — all 28 channels")
plt.tight_layout()


# ════════════════════════════════════════════════════════════════════════════
# 7) FIG 2 — HEATMAP: RESIDUAL ARTIFACT AMPLITUDE AFTER CLEANING
# ════════════════════════════════════════════════════════════════════════════
#
# Metric: for each (channel, intensity), mean over 20 pulses of the max absolute
# deviation from baseline in the 0–50ms post-pulse window of the CLEANED signal.
# - Near-baseline values → artifact fully removed
# - Large values → some artifact remains (detection ended too early)
#
# Note: the first ~0ms to artifact_end region is interpolated (flat line), so
# any deviation here reflects a mismatch at the right anchor or late oscillations
# the threshold missed.

intensity_levels   = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
n_channels         = len(eeg_channels)
n_intensities      = len(intensity_levels)
residual_matrix_uv = np.zeros((n_channels, n_intensities))  # µV, rows=channels, cols=intensities

for col_idx, intensity_pct in enumerate(intensity_levels):
    pulse_onsets = pulses_by_intensity[intensity_pct].astype(int)
    cleaned      = cleaned_data_by_intensity[intensity_pct]
    for channel_idx in range(n_channels):
        per_pulse_residuals = []
        for pulse_onset in pulse_onsets:
            pre_pulse_mean = np.mean(
                cleaned[channel_idx,
                        pulse_onset + ms_to_samples(-100) : pulse_onset + ms_to_samples(-10)]
            )
            post_clean_deviation = np.abs(
                cleaned[channel_idx, pulse_onset : pulse_onset + ms_to_samples(50)] - pre_pulse_mean
            )
            per_pulse_residuals.append(np.max(post_clean_deviation))
        residual_matrix_uv[channel_idx, col_idx] = np.mean(per_pulse_residuals) * 1e6

fig2, ax2 = plt.subplots(figsize=(10, 8))
im = ax2.imshow(residual_matrix_uv, aspect="auto", cmap="YlOrRd")
ax2.set_xticks(range(n_intensities))
ax2.set_xticklabels([f"{pct}%" for pct in intensity_levels])
ax2.set_yticks(range(n_channels))
ax2.set_yticklabels(eeg_channels, fontsize=7)
ax2.set_xlabel("Intensity (% MSO)")
ax2.set_ylabel("Channel")
ax2.set_title(
    "Residual artifact after cleaning — mean peak |deviation from baseline| in 0–50ms  (µV)\n"
    "Yellow = clean  ·  Red = residual artifact"
)
plt.colorbar(im, ax=ax2, label="µV")
plt.tight_layout()


plt.show()
plt.pause(300)
