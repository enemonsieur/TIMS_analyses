"""
Preprocessing utilities for TIMS dose-response EEG analysis.

Contains only functions with genuinely complex logic (>15 lines, non-obvious).
Simple operations (loading, epoching, demeaning, HPF, saving) are inline recipes
documented in readme.md — not hidden behind function calls.

Design: No classes. Explicit array-shape comments. Pure numpy/scipy where possible.
"""

from __future__ import annotations

from pathlib import Path
import csv
from typing import Any

import mne
from mne.time_frequency import tfr_array_morlet
import numpy as np
from scipy.signal import butter, coherence, filtfilt, find_peaks, hilbert, iirnotch, sosfiltfilt, welch


def filter_signal(
    data: np.ndarray,
    sampling_rate_hz: float,
    low_hz: float,
    high_hz: float,
    notch_hz: float = 50.0,
    notch_q: float = 30.0,
    order: int = 4,
) -> np.ndarray:
    """Apply notch + bandpass filtering to 1D or 2D arrays."""
    if low_hz <= 0 or high_hz <= low_hz:
        raise ValueError("Filter limits must satisfy 0 < low_hz < high_hz.")

    input_array = np.asarray(data, dtype=float)
    notch_b, notch_a = iirnotch(w0=notch_hz, Q=notch_q, fs=sampling_rate_hz)
    notch_filtered = filtfilt(notch_b, notch_a, input_array, axis=-1)

    bandpass_sos = butter(order, [low_hz, high_hz], btype="bandpass", fs=sampling_rate_hz, output="sos")
    bandpassed = sosfiltfilt(bandpass_sos, notch_filtered, axis=-1)

    if bandpassed.shape != input_array.shape:
        raise RuntimeError("Filtering changed array shape unexpectedly.")
    if not np.all(np.isfinite(bandpassed)):
        raise RuntimeError("Filtering produced non-finite values.")
    return bandpassed


def load_exp06_saved_ssd_artifact(weights_path: Path) -> dict[str, Any]:
    """Load the saved exp06 SSD artifact and validate the required fields."""
    artifact_path = Path(weights_path)
    if not artifact_path.exists():
        raise FileNotFoundError(f"Required baseline SSD artifact is missing: {artifact_path}")

    required_fields = {
        "channel_names",
        "sampling_rate_hz",
        "signal_band_hz",
        "view_band_hz",
        "selected_component_index",
        "selected_filter",
        "selected_pattern",
        "selected_lambda",
        "baseline_peak_hz",
    }
    with np.load(artifact_path) as loaded_artifact:
        missing_fields = sorted(field_name for field_name in required_fields if field_name not in loaded_artifact.files)
        if missing_fields:
            raise KeyError(f"Saved SSD artifact is missing required fields: {', '.join(missing_fields)}")

        artifact = {
            "channel_names": loaded_artifact["channel_names"].astype(str).tolist(),
            "sampling_rate_hz": float(np.asarray(loaded_artifact["sampling_rate_hz"], dtype=float).ravel()[0]),
            "signal_band_hz": tuple(np.asarray(loaded_artifact["signal_band_hz"], dtype=float).tolist()),
            "view_band_hz": tuple(np.asarray(loaded_artifact["view_band_hz"], dtype=float).tolist()),
            "selected_component_index": int(np.asarray(loaded_artifact["selected_component_index"], dtype=int).ravel()[0]),
            "selected_filter": np.asarray(loaded_artifact["selected_filter"], dtype=float).ravel(),
            "selected_pattern": np.asarray(loaded_artifact["selected_pattern"], dtype=float).ravel(),
            "selected_lambda": float(np.asarray(loaded_artifact["selected_lambda"], dtype=float).ravel()[0]),
            "baseline_peak_hz": float(np.asarray(loaded_artifact["baseline_peak_hz"], dtype=float).ravel()[0]),
        }

    if len(artifact["signal_band_hz"]) != 2 or len(artifact["view_band_hz"]) != 2:
        raise ValueError("Saved SSD artifact band fields must each contain exactly two frequencies.")
    return artifact


def validate_exp06_saved_ssd_against_raw(
    raw_eeg: Any,
    saved_channel_names: list[str],
    saved_sampling_rate_hz: float,
    selected_filter: np.ndarray,
    focus_channel: str | None = None,
) -> None:
    """Fail fast if a saved exp06 SSD artifact is incompatible with a target EEG recording."""
    if list(raw_eeg.ch_names) != list(saved_channel_names):
        raise RuntimeError("Stim EEG channels do not match the saved baseline SSD channel order.")
    if not np.isclose(float(raw_eeg.info["sfreq"]), float(saved_sampling_rate_hz)):
        raise RuntimeError(
            f"Sampling rate mismatch between target EEG ({float(raw_eeg.info['sfreq']):.3f} Hz) and saved baseline "
            f"weights ({float(saved_sampling_rate_hz):.3f} Hz)."
        )

    filter_vector = np.asarray(selected_filter, dtype=float).ravel()
    if filter_vector.size != len(saved_channel_names):
        raise RuntimeError("Saved selected_filter length does not match the saved channel list.")
    if focus_channel is not None and focus_channel not in raw_eeg.ch_names:
        raise RuntimeError(f"Required focus channel is missing from retained EEG channels: {focus_channel}")


def apply_exp06_saved_ssd_to_events(
    raw_eeg: Any,
    events: np.ndarray,
    selected_filter: np.ndarray,
    view_band_hz: tuple[float, float],
    epoch_duration_s: float,
) -> tuple[Any, np.ndarray]:
    """Apply one saved exp06 SSD filter to epoched EEG and return one component trace per epoch."""
    import plot_helpers

    spatial_filter = np.asarray(selected_filter, dtype=float).ravel()[np.newaxis, :]
    epochs_view, component_epochs = plot_helpers.build_ssd_component_epochs(
        raw_eeg,
        events,
        spatial_filter,
        view_band_hz,
        epoch_duration_s,
    )
    if component_epochs.shape[0] != 1:
        raise RuntimeError("Saved SSD transfer expected exactly one component.")
    return epochs_view, np.asarray(component_epochs[0], dtype=float)


def compute_band_limited_epoch_triplet_metrics(
    signal_epochs: np.ndarray,
    reference_epochs: np.ndarray,
    sampling_rate_hz: float,
    band_hz: tuple[float, float],
) -> dict[str, np.ndarray]:
    """Filter matched epoch sets and compute z-scored means plus GT-locked ITPC."""
    signal_array = np.asarray(signal_epochs, dtype=float)
    reference_array = np.asarray(reference_epochs, dtype=float)
    n_epochs = min(signal_array.shape[0], reference_array.shape[0])
    if n_epochs < 1:
        raise ValueError("Need at least one matched epoch to compute band-limited metrics.")

    signal_band_epochs = filter_signal(signal_array[:n_epochs], sampling_rate_hz, band_hz[0], band_hz[1])
    reference_band_epochs = filter_signal(reference_array[:n_epochs], sampling_rate_hz, band_hz[0], band_hz[1])
    phase_diff = np.angle(hilbert(signal_band_epochs, axis=-1)) - np.angle(hilbert(reference_band_epochs, axis=-1))
    itpc_curve = np.abs(np.mean(np.exp(1j * phase_diff), axis=0))

    def _zscore_trace(trace: np.ndarray) -> np.ndarray:
        trace_1d = np.asarray(trace, dtype=float).ravel()
        return (trace_1d - np.mean(trace_1d)) / (np.std(trace_1d) + 1e-12)

    return {
        "signal_band_epochs": signal_band_epochs,
        "reference_band_epochs": reference_band_epochs,
        "mean_signal_trace_z": _zscore_trace(signal_band_epochs.mean(axis=0)),
        "mean_reference_trace_z": _zscore_trace(reference_band_epochs.mean(axis=0)),
        "itpc_curve": itpc_curve,
    }


def compute_mean_epoch_psd(
    epoch_array: np.ndarray,
    sampling_rate_hz: float,
    view_band_hz: tuple[float, float],
    n_fft: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute one mean Welch PSD across matched epochs."""
    psd_values, psd_freqs_hz = mne.time_frequency.psd_array_welch(
        np.asarray(epoch_array, dtype=float),
        sfreq=sampling_rate_hz,
        fmin=view_band_hz[0],
        fmax=view_band_hz[1],
        n_fft=n_fft,
        verbose=False,
    )
    return psd_freqs_hz, np.mean(psd_values, axis=0)


def pick_good_eeg_channels_from_baseline(
    baseline_raw: Any,
    include_candidates: list[str] | None = None,
    drop_flat: bool = True,
    flat_std_uv: float = 1e-6,
    outlier_mad_multiplier: float = 6.0,
) -> tuple[list[str], list[str]]:
    """Pick usable EEG channels from baseline variance statistics.

    Returns:
    - good_eeg_channels: channels kept for analysis
    - bad_eeg_channels: channels dropped as flat/noisy
    """
    eeg_channel_names = [
        channel_name
        for channel_name in baseline_raw.ch_names
        if channel_name not in {"stim", "ground_truth"} and not channel_name.upper().startswith("STI")
    ]
    if include_candidates is not None:
        eeg_channel_names = [channel_name for channel_name in include_candidates if channel_name in eeg_channel_names]
    if not eeg_channel_names:
        raise ValueError("No EEG channels available for channel-quality selection.")

    # baseline_eeg_data shape: (n_channels, n_times)
    baseline_eeg_data = baseline_raw.copy().pick(eeg_channel_names).get_data()
    channel_std_uv = baseline_eeg_data.std(axis=1) * 1e6

    if drop_flat:
        flat_mask = channel_std_uv <= flat_std_uv
    else:
        flat_mask = np.zeros_like(channel_std_uv, dtype=bool)

    non_flat_std_uv = channel_std_uv[~flat_mask]
    if non_flat_std_uv.size >= 3:
        median_std_uv = float(np.median(non_flat_std_uv))
        mad_std_uv = float(np.median(np.abs(non_flat_std_uv - median_std_uv)))
        if mad_std_uv > 0:
            robust_sigma = 1.4826 * mad_std_uv
            high_noise_threshold_uv = median_std_uv + outlier_mad_multiplier * robust_sigma
            noisy_mask = channel_std_uv > high_noise_threshold_uv
        else:
            noisy_mask = np.zeros_like(channel_std_uv, dtype=bool)
    else:
        noisy_mask = np.zeros_like(channel_std_uv, dtype=bool)

    drop_mask = flat_mask | noisy_mask
    good_eeg_channels = [channel_name for channel_name, drop in zip(eeg_channel_names, drop_mask) if not drop]
    bad_eeg_channels = [channel_name for channel_name, drop in zip(eeg_channel_names, drop_mask) if drop]

    if not good_eeg_channels:
        raise ValueError("All EEG channels were rejected. Relax channel-quality thresholds.")
    return good_eeg_channels, bad_eeg_channels


def detect_stim_onsets(
    stim_marker: np.ndarray,
    sampling_rate_hz: float,
    fallback_min_peaks: int = 5,
    min_ioi_seconds: float = 0.5,
    refractory_floor_seconds: float = 1.5,
    refractory_fraction_of_ioi: float = 0.6,
) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Detect one onset per stimulation pulse and estimate inter-onset interval.

    Returns:
    - onsets_samples: (n_onsets,) int
    - median_ioi_seconds: float
    - ioi_seconds: (n_onsets - 1,) float
    - onsets_seconds: (n_onsets,) float
    """
    marker_1d = np.asarray(stim_marker, dtype=float).ravel()
    if marker_1d.size == 0:
        raise ValueError("Stim marker is empty.")

    # Envelope makes pulse peaks polarity-agnostic and robust to sign changes.
    marker_envelope = np.abs(hilbert(marker_1d))

    # Adaptive prominence: robust to recordings with different marker amplitudes.
    prominence_value = max(
        3.0 * float(np.std(marker_envelope)),
        float(np.percentile(marker_envelope, 95) - np.percentile(marker_envelope, 50)),
    )
    candidate_onsets, _ = find_peaks(
        marker_envelope,
        prominence=prominence_value,
        distance=max(1, int(0.05 * sampling_rate_hz)),
    )

    # Fallback for low-SNR cases where strict prominence misses too many peaks.
    if len(candidate_onsets) < fallback_min_peaks:
        candidate_onsets, _ = find_peaks(
            marker_envelope,
            prominence=float(np.std(marker_envelope)),
            distance=max(1, int(0.02 * sampling_rate_hz)),
        )

    candidate_onsets = np.asarray(candidate_onsets, dtype=int)
    if candidate_onsets.size == 0:
        raise ValueError("No stimulation peaks detected in stim marker.")

    if candidate_onsets.size > 1:
        candidate_intervals_seconds = np.diff(candidate_onsets) / sampling_rate_hz
        candidate_intervals_seconds = candidate_intervals_seconds[candidate_intervals_seconds > min_ioi_seconds]
        median_ioi_guess_seconds = (
            float(np.median(candidate_intervals_seconds)) if candidate_intervals_seconds.size else 10.0
        )
    else:
        median_ioi_guess_seconds = 10.0

    # Refractory rule enforces one onset per pulse:
    # keep the first peak in a window, but if another peak inside the same window
    # is stronger, replace it. This merges within-pulse multi-peaks.
    refractory_samples = int(
        max(
            refractory_fraction_of_ioi * median_ioi_guess_seconds * sampling_rate_hz,
            refractory_floor_seconds * sampling_rate_hz,
        )
    )
    kept_onsets: list[int] = []
    last_kept = -10**9
    for candidate in candidate_onsets:
        if candidate - last_kept >= refractory_samples:
            kept_onsets.append(int(candidate))
            last_kept = int(candidate)
        elif marker_envelope[candidate] > marker_envelope[last_kept]:
            kept_onsets[-1] = int(candidate)
            last_kept = int(candidate)

    onsets_samples = np.asarray(kept_onsets, dtype=int)
    if onsets_samples.size == 0:
        raise ValueError("Onset detection failed after refractory filtering.")
    if not np.all(np.diff(onsets_samples) > 0):
        raise RuntimeError("Detected onsets are not strictly increasing.")

    ioi_seconds = np.diff(onsets_samples) / sampling_rate_hz if onsets_samples.size > 1 else np.array([], dtype=float)
    median_ioi_seconds = float(np.median(ioi_seconds)) if ioi_seconds.size else median_ioi_guess_seconds
    onsets_seconds = onsets_samples.astype(float) / sampling_rate_hz

    if not np.isfinite(median_ioi_seconds) or median_ioi_seconds <= 0:
        raise RuntimeError("Invalid median IOI computed.")
    return onsets_samples, median_ioi_seconds, ioi_seconds, onsets_seconds


def detect_stim_blocks(
    stim_data: np.ndarray,
    sampling_rate_hz: float,
    threshold_fraction: float = 0.1,
    max_inter_pulse_gap_s: float = 0.3,
    min_block_dur_s: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Detect ON-block start/end times directly from the STIM channel.

    Threshold the raw STIM trace to find pulse-active segments, then merge
    segments that are separated by only short within-block gaps.

    For exp05 cTBS, burst repetitions are every 200 ms and the longest gap
    inside an ON block is about 160 ms, while OFF blocks are about 3 s. A
    300 ms merge gap therefore preserves the full ON block without merging
    adjacent cycles.

    Parameters
    ----------
    stim_data : 1-D array
        Raw STIM channel time series.
    sampling_rate_hz : float
        Sampling rate in Hz.
    threshold_fraction : float
        Fraction of max absolute STIM amplitude used as active threshold.
    max_inter_pulse_gap_s : float
        Maximum gap between pulse-active segments that still belongs to the
        same ON block.
    min_block_dur_s : float
        Minimum block duration to keep (rejects transients).

    Returns
    -------
    block_onsets : (n_blocks,) int array — sample index of each ON-block start.
    block_offsets : (n_blocks,) int array — sample index of each ON-block end.
    """
    stim_1d = np.asarray(stim_data, dtype=float).ravel()
    if stim_1d.size == 0:
        raise ValueError("stim_data is empty.")

    stim_abs = np.abs(stim_1d)
    threshold = threshold_fraction * float(np.max(stim_abs))
    pulse_mask = stim_abs >= threshold
    if not np.any(pulse_mask):
        raise ValueError("No pulse-active samples detected in STIM channel.")

    transitions = np.diff(pulse_mask.astype(np.int8))
    raw_starts = np.where(transitions == 1)[0] + 1
    raw_ends = np.where(transitions == -1)[0] + 1
    if pulse_mask[0]:
        raw_starts = np.insert(raw_starts, 0, 0)
    if pulse_mask[-1]:
        raw_ends = np.append(raw_ends, stim_1d.size)

    merged_starts = [int(raw_starts[0])]
    merged_ends = [int(raw_ends[0])]
    max_gap_samples = max(1, int(round(max_inter_pulse_gap_s * sampling_rate_hz)))
    for start_sample, end_sample in zip(raw_starts[1:], raw_ends[1:]):
        if int(start_sample) - merged_ends[-1] <= max_gap_samples:
            merged_ends[-1] = int(end_sample)
        else:
            merged_starts.append(int(start_sample))
            merged_ends.append(int(end_sample))

    min_samples = int(min_block_dur_s * sampling_rate_hz)
    onsets, offsets = [], []
    for start_sample, end_sample in zip(merged_starts, merged_ends):
        if end_sample - start_sample >= min_samples:
            onsets.append(start_sample)
            offsets.append(end_sample)

    if not onsets:
        raise ValueError(f"No ON blocks longer than {min_block_dur_s} s found.")

    return np.array(onsets, dtype=int), np.array(offsets, dtype=int)


def build_event_array(start_samples: np.ndarray) -> np.ndarray:
    """Return an MNE-style events array from one vector of event starts."""
    start_vector = np.asarray(start_samples, dtype=int).ravel()
    return np.column_stack(
        [
            start_vector,
            np.zeros(start_vector.size, dtype=int),
            np.ones(start_vector.size, dtype=int),
        ]
    )


def build_late_off_events(
    block_onsets_samples: np.ndarray,
    block_offsets_samples: np.ndarray,
    sampling_rate_hz: float,
    window_start_s: float,
    window_stop_s: float,
) -> tuple[np.ndarray, float, int]:
    """Build measured late-OFF event starts that fully fit before the next ON block."""
    onsets = np.asarray(block_onsets_samples, dtype=int).ravel()
    offsets = np.asarray(block_offsets_samples, dtype=int).ravel()
    if onsets.size != offsets.size:
        raise ValueError("block_onsets_samples and block_offsets_samples must have the same length.")
    if onsets.size < 2:
        raise ValueError("Need at least two ON blocks to build late-OFF events.")
    if window_stop_s <= window_start_s:
        raise ValueError("window_stop_s must be greater than window_start_s.")

    window_duration_s = float(window_stop_s - window_start_s)
    window_duration_samples = int(round(window_duration_s * sampling_rate_hz))
    start_offset_samples = int(round(window_start_s * sampling_rate_hz))
    late_off_starts = offsets[:-1] + start_offset_samples
    valid_mask = late_off_starts + window_duration_samples <= onsets[1:]
    return build_event_array(late_off_starts[valid_mask]), window_duration_s, window_duration_samples


def extract_event_windows(
    signal_1d: np.ndarray,
    event_starts_samples: np.ndarray,
    window_duration_samples: int,
) -> np.ndarray:
    """Extract fixed-length windows from one 1-D signal using event starts."""
    vector = np.asarray(signal_1d, dtype=float).ravel()
    starts = np.asarray(event_starts_samples, dtype=int).ravel()
    if window_duration_samples < 1:
        raise ValueError("window_duration_samples must be >= 1.")
    if starts.size == 0:
        return np.empty((0, window_duration_samples), dtype=float)
    if np.any(starts < 0) or np.any(starts + window_duration_samples > vector.size):
        raise ValueError("Requested event window exceeds signal bounds.")
    return np.asarray(
        [vector[int(start_sample):int(start_sample) + window_duration_samples] for start_sample in starts],
        dtype=float,
    )


def rank_ssd_components_against_reference(
    spatial_filters: np.ndarray,
    raw_signal_band: Any,
    raw_view_band: Any,
    evaluation_mask: np.ndarray,
    reference_band_signal: np.ndarray,
    sampling_rate_hz: float,
    signal_band_hz: tuple[float, float],
    view_range_hz: tuple[float, float],
    flank_gap_hz: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Score SSD components by band-limited GT match and target-band peak shape."""
    filters = np.asarray(spatial_filters, dtype=float)
    mask = np.asarray(evaluation_mask, dtype=bool).ravel()
    reference = np.asarray(reference_band_signal, dtype=float).ravel()
    signal_band_width_hz = float(signal_band_hz[1] - signal_band_hz[0])
    if filters.ndim != 2:
        raise ValueError("spatial_filters must have shape (n_components, n_channels).")
    if signal_band_width_hz <= 0:
        raise ValueError("signal_band_hz must satisfy high > low.")

    signal_data = raw_signal_band.get_data()
    view_data = raw_view_band.get_data()
    coherence_scores = []
    peak_ratios = []
    peak_freqs = []
    for component_index in range(filters.shape[0]):
        component_signal = filters[component_index] @ signal_data
        component_view = filters[component_index] @ view_data
        coherence_scores.append(
            compute_coherence_band(
                component_signal[mask],
                reference[mask],
                sampling_rate_hz,
                signal_band_hz[0],
                signal_band_hz[1],
            )
        )
        peak_ratios.append(
            compute_band_peak_ratio(
                component_view[mask],
                sampling_rate_hz,
                signal_band_hz,
                flank_width_hz=signal_band_width_hz,
                flank_gap_hz=flank_gap_hz,
            )
        )
        peak_freqs.append(find_psd_peak_frequency(component_view[mask], sampling_rate_hz, view_range_hz))
    return np.asarray(coherence_scores, dtype=float), np.asarray(peak_ratios, dtype=float), np.asarray(peak_freqs, dtype=float)


def build_matched_triplet_events(
    stim_pulse_onsets_samples: np.ndarray,
    pre_n_times: int,
    stim_n_times: int,
    post_n_times: int,
    sampling_rate_hz: float,
    epoch_tmin_s: float,
    epoch_tmax_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build matched pre/stim/post event arrays from the stim pulse cadence."""
    stim_samples = np.asarray(stim_pulse_onsets_samples, dtype=int).ravel()
    if stim_samples.size < 2:
        raise ValueError("Need at least two stim pulse onsets to estimate the event interval.")
    if not np.all(np.diff(stim_samples) > 0):
        raise ValueError("stim_pulse_onsets_samples must be strictly increasing.")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")
    if epoch_tmin_s >= epoch_tmax_s:
        raise ValueError("epoch_tmin_s must be smaller than epoch_tmax_s.")

    median_interval_samples = int(round(float(np.median(np.diff(stim_samples)))))
    if median_interval_samples < 1:
        raise RuntimeError("Stim pulse interval must be at least 1 sample.")

    pre_margin_samples = int(np.ceil(abs(epoch_tmin_s) * sampling_rate_hz))
    post_margin_samples = int(np.ceil(epoch_tmax_s * sampling_rate_hz))
    first_pulse_sample = int(stim_samples[0])

    def _valid_epoch_centers(samples: np.ndarray, n_times: int) -> np.ndarray:
        centers = np.asarray(samples, dtype=int).ravel()
        valid_mask = (centers >= pre_margin_samples) & (centers + post_margin_samples < int(n_times))
        return centers[valid_mask]

    pre_samples = np.arange(first_pulse_sample, int(pre_n_times), median_interval_samples, dtype=int)
    post_samples = np.arange(first_pulse_sample, int(post_n_times), median_interval_samples, dtype=int)

    valid_pre_samples = _valid_epoch_centers(pre_samples, pre_n_times)
    valid_stim_samples = _valid_epoch_centers(stim_samples, stim_n_times)
    valid_post_samples = _valid_epoch_centers(post_samples, post_n_times)

    n_matched = min(valid_pre_samples.size, valid_stim_samples.size, valid_post_samples.size)
    if n_matched == 0:
        raise ValueError("No matched valid epochs remain across pre/stim/post.")

    def _as_events(samples: np.ndarray) -> np.ndarray:
        trimmed = np.asarray(samples[:n_matched], dtype=int)
        return np.column_stack(
            [trimmed, np.zeros(trimmed.size, dtype=int), np.ones(trimmed.size, dtype=int)]
        ).astype(int)

    return _as_events(valid_pre_samples), _as_events(valid_stim_samples), _as_events(valid_post_samples)


def remove_and_interpolate_pulse_window(
    epoch_data: np.ndarray,
    time_axis_seconds: np.ndarray,
    cut_window_s: tuple[float, float] = (-0.002, 0.010),
) -> tuple[np.ndarray, np.ndarray]:
    """Remove pulse window and linearly interpolate through the removed samples.

    Supports:
    - epoch_data shape (n_epochs, n_channels, n_samples)
    - epoch_data shape (n_epochs, n_samples)
    """
    input_epochs = np.asarray(epoch_data, dtype=float)
    input_time = np.asarray(time_axis_seconds, dtype=float).ravel()
    if input_epochs.shape[-1] != input_time.size:
        raise ValueError("Epoch sample axis and time_axis_seconds length must match.")

    cut_mask = (input_time >= cut_window_s[0]) & (input_time <= cut_window_s[1])
    cut_indices = np.where(cut_mask)[0]
    if cut_indices.size == 0:
        raise ValueError("Pulse cut window does not overlap epoch time axis.")

    left_index = int(cut_indices[0] - 1)
    right_index = int(cut_indices[-1] + 1)
    if left_index < 0 or right_index >= input_time.size:
        raise ValueError("Pulse cut window too close to epoch edges for interpolation.")

    if input_epochs.ndim == 2:
        working = input_epochs[:, np.newaxis, :].copy()  # (n_epochs, 1, n_samples)
        squeeze_output = True
    elif input_epochs.ndim == 3:
        working = input_epochs.copy()  # (n_epochs, n_channels, n_samples)
        squeeze_output = False
    else:
        raise ValueError("epoch_data must be 2D or 3D.")

    x_interp = input_time[cut_indices]
    x_support = np.array([input_time[left_index], input_time[right_index]], dtype=float)
    for epoch_index in range(working.shape[0]):
        for channel_index in range(working.shape[1]):
            y = working[epoch_index, channel_index]
            y_support = np.array([y[left_index], y[right_index]], dtype=float)
            y[cut_indices] = np.interp(x_interp, x_support, y_support)

    if not np.all(np.isfinite(working)):
        raise RuntimeError("Interpolation produced non-finite values.")
    if squeeze_output:
        return working[:, 0, :], cut_mask
    return working, cut_mask


def crop_epochs_time_window(
    epoch_data: np.ndarray,
    time_axis_seconds: np.ndarray,
    window_start_s: float,
    window_end_s: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | int]]:
    """Crop epoch samples to a requested time window.

    Input:
    - epoch_data shape: (n_epochs, n_channels, n_samples) in Volts
    - time_axis_seconds shape: (n_samples,)

    Returns:
    - cropped_epochs shape: (n_epochs, n_channels, n_cropped_samples)
    - cropped_time_seconds shape: (n_cropped_samples,)
    - details with selected sample indices and actual bounds
    """
    input_epochs = np.asarray(epoch_data, dtype=float)
    input_time = np.asarray(time_axis_seconds, dtype=float).ravel()

    if input_epochs.ndim != 3:
        raise ValueError("epoch_data must have shape (n_epochs, n_channels, n_samples).")
    if input_epochs.shape[-1] != input_time.size:
        raise ValueError("Epoch sample axis and time_axis_seconds length must match.")
    if window_end_s <= window_start_s:
        raise ValueError("window_end_s must be greater than window_start_s.")
    if input_time.size < 2:
        raise ValueError("time_axis_seconds must contain at least 2 samples.")
    if not np.all(np.diff(input_time) > 0):
        raise ValueError("time_axis_seconds must be strictly increasing.")
    min_time = float(input_time[0])
    max_time = float(input_time[-1])
    if window_end_s < min_time or window_start_s > max_time:
        raise ValueError("Requested post-pulse window does not overlap the epoch time axis.")

    start_index = int(np.searchsorted(input_time, window_start_s, side="left"))
    stop_index = int(np.searchsorted(input_time, window_end_s, side="right"))
    start_index = max(0, min(start_index, input_time.size - 1))
    stop_index = max(1, min(stop_index, input_time.size))
    if stop_index <= start_index:
        raise ValueError("Requested crop window returned no samples.")

    cropped_epochs = input_epochs[:, :, start_index:stop_index].copy()
    cropped_time_seconds = input_time[start_index:stop_index]
    if cropped_epochs.shape[-1] < 2:
        raise ValueError("Requested crop window is too short.")

    details: dict[str, float | int] = {
        "start_index": int(start_index),
        "end_index": int(stop_index - 1),
        "n_samples": int(cropped_epochs.shape[-1]),
        "time_start_s": float(cropped_time_seconds[0]),
        "time_end_s": float(cropped_time_seconds[-1]),
    }
    return cropped_epochs, cropped_time_seconds, details


def replace_block_with_zero_after_dual_center(epoch_data: np.ndarray, time_axis_seconds: np.ndarray, artifact_block_window_s: tuple[float, float], pre_center_window_s: tuple[float, float], post_center_window_s: tuple[float, float]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Center pre/post segments and replace artifact block with a zero constant."""
    input_epochs = np.asarray(epoch_data, dtype=float)
    input_time = np.asarray(time_axis_seconds, dtype=float).ravel()
    if input_epochs.shape[-1] != input_time.size:
        raise ValueError("Epoch sample axis and time_axis_seconds length must match.")
    artifact_mask = (input_time >= artifact_block_window_s[0]) & (input_time <= artifact_block_window_s[1])
    pre_window_mask = (input_time >= pre_center_window_s[0]) & (input_time <= pre_center_window_s[1])
    post_window_mask = (input_time >= post_center_window_s[0]) & (input_time <= post_center_window_s[1])
    if not np.any(artifact_mask) or not np.any(pre_window_mask) or not np.any(post_window_mask):
        raise ValueError("One or more center/cut windows do not overlap the epoch axis.")
    if np.any(artifact_mask & pre_window_mask) or np.any(artifact_mask & post_window_mask):
        raise ValueError("Center windows must not overlap artifact block window.")
    if input_epochs.ndim == 2:
        working = input_epochs[:, np.newaxis, :].copy()
    elif input_epochs.ndim == 3:
        working = input_epochs.copy()
    else:
        raise ValueError("epoch_data must be 2D or 3D.")
    squeeze_output = input_epochs.ndim == 2
    pre_segment_mask = input_time < artifact_block_window_s[0]
    post_segment_mask = input_time > artifact_block_window_s[1]
    if not np.any(pre_segment_mask) or not np.any(post_segment_mask):
        raise ValueError("Artifact block window leaves no pre or post segment.")
    pre_center_mean = working[:, :, pre_window_mask].mean(axis=-1, keepdims=True)
    post_center_mean = working[:, :, post_window_mask].mean(axis=-1, keepdims=True)
    working[:, :, pre_segment_mask] -= pre_center_mean
    working[:, :, post_segment_mask] -= post_center_mean
    working[:, :, artifact_mask] = 0.0
    if not np.all(np.isfinite(working)):
        raise RuntimeError("Dual-centering or block replacement produced non-finite values.")
    output = working[:, 0, :] if squeeze_output else working
    details = {"artifact_block_mask": artifact_mask, "pre_center_window_mask": pre_window_mask, "post_center_window_mask": post_window_mask, "pre_center_mean": pre_center_mean[:, :, 0], "post_center_mean": post_center_mean[:, :, 0]}
    return output, details


def compute_derivative_metric(
    epoch_data: np.ndarray,
    sampling_rate_hz: float,
    aggregate: str = "mean_abs",
) -> np.ndarray:
    """Compute a 1D derivative-based artifact metric over epoch time."""
    input_epochs = np.asarray(epoch_data, dtype=float)
    if input_epochs.ndim == 2:
        working = input_epochs[:, np.newaxis, :]
    elif input_epochs.ndim == 3:
        working = input_epochs
    else:
        raise ValueError("epoch_data must be 2D or 3D.")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")

    dt = 1.0 / float(sampling_rate_hz)
    derivative = np.gradient(working, dt, axis=-1)
    abs_derivative = np.abs(derivative)

    if aggregate == "mean_abs":
        metric = abs_derivative.mean(axis=(0, 1))
    elif aggregate == "median_abs":
        metric = np.median(abs_derivative, axis=(0, 1))
    elif aggregate == "rms":
        metric = np.sqrt(np.mean(derivative**2, axis=(0, 1)))
    else:
        raise ValueError("aggregate must be one of: 'mean_abs', 'median_abs', 'rms'.")

    if metric.ndim != 1:
        raise RuntimeError("Derivative metric must be 1D.")
    if not np.all(np.isfinite(metric)):
        raise RuntimeError("Derivative metric contains non-finite values.")
    return metric


def find_return_to_baseline_time(
    metric: np.ndarray,
    time_axis_seconds: np.ndarray,
    baseline_window_s: tuple[float, float],
    search_window_s: tuple[float, float],
    sigma_k: float = 5.0,
    min_consecutive_samples: int = 3,
) -> dict[str, float | int | bool]:
    """Find first search-window time where metric returns below baseline + k*sigma."""
    values = np.asarray(metric, dtype=float).ravel()
    time_axis = np.asarray(time_axis_seconds, dtype=float).ravel()
    if values.shape[0] != time_axis.shape[0]:
        raise ValueError("metric and time_axis_seconds must have the same length.")
    if values.size == 0:
        raise ValueError("metric is empty.")
    if min_consecutive_samples < 1:
        raise ValueError("min_consecutive_samples must be >= 1.")

    baseline_mask = (time_axis >= baseline_window_s[0]) & (time_axis <= baseline_window_s[1])
    if not np.any(baseline_mask):
        raise ValueError("baseline_window_s does not overlap the time axis.")
    baseline_values = values[baseline_mask]
    baseline_mean = float(np.mean(baseline_values))
    baseline_sigma = float(np.std(baseline_values))
    threshold = float(baseline_mean + sigma_k * baseline_sigma)

    search_mask = (time_axis >= search_window_s[0]) & (time_axis <= search_window_s[1])
    search_indices = np.where(search_mask)[0]
    if search_indices.size == 0:
        raise ValueError("search_window_s does not overlap the time axis.")

    condition = values[search_indices] <= threshold
    run_kernel = np.ones(min_consecutive_samples, dtype=int)
    run_hits = np.convolve(condition.astype(int), run_kernel, mode="valid")
    valid_run = np.where(run_hits >= min_consecutive_samples)[0]

    found = bool(valid_run.size > 0)
    if found:
        return_index = int(search_indices[int(valid_run[0])])
        return_time_s = float(time_axis[return_index])
    else:
        return_index = -1
        return_time_s = float("nan")

    return {
        "found": found,
        "return_index": return_index,
        "return_time_s": return_time_s,
        "baseline_mean": baseline_mean,
        "baseline_sigma": baseline_sigma,
        "threshold": threshold,
        "search_start_index": int(search_indices[0]),
        "search_end_index": int(search_indices[-1]),
        "min_consecutive_samples": int(min_consecutive_samples),
    }


def compute_window_bias_per_channel(
    epoch_data: np.ndarray,
    time_axis_seconds: np.ndarray,
    window_a_s: tuple[float, float],
    window_b_s: tuple[float, float],
) -> np.ndarray:
    """Per-channel median epoch bias: mean(window_a) - mean(window_b)."""
    input_epochs = np.asarray(epoch_data, dtype=float)
    input_time = np.asarray(time_axis_seconds, dtype=float).ravel()
    if input_epochs.ndim == 2:
        working = input_epochs[:, np.newaxis, :]
    elif input_epochs.ndim == 3:
        working = input_epochs
    else:
        raise ValueError("epoch_data must be 2D or 3D.")
    if working.shape[-1] != input_time.size:
        raise ValueError("Epoch sample axis and time_axis_seconds length must match.")

    window_a_mask = (input_time >= window_a_s[0]) & (input_time <= window_a_s[1])
    window_b_mask = (input_time >= window_b_s[0]) & (input_time <= window_b_s[1])
    if not np.any(window_a_mask):
        raise ValueError("window_a_s does not overlap epoch time axis.")
    if not np.any(window_b_mask):
        raise ValueError("window_b_s does not overlap epoch time axis.")

    mean_a = working[:, :, window_a_mask].mean(axis=-1)
    mean_b = working[:, :, window_b_mask].mean(axis=-1)
    bias_per_epoch_channel = mean_a - mean_b
    channel_median_bias = np.median(bias_per_epoch_channel, axis=0)

    if channel_median_bias.ndim != 1:
        raise RuntimeError("Channel bias output must be 1D.")
    if not np.all(np.isfinite(channel_median_bias)):
        raise RuntimeError("Channel bias contains non-finite values.")
    return channel_median_bias


def compute_coherence_band(
    signal_a: np.ndarray,
    signal_b: np.ndarray,
    sampling_rate_hz: float,
    low_hz: float,
    high_hz: float,
    nperseg: int = 4096,
) -> float:
    """Mean coherence in a band; fallback to nearest bin if band empty."""
    vector_a = np.asarray(signal_a, dtype=float).ravel()
    vector_b = np.asarray(signal_b, dtype=float).ravel()
    frequencies_hz, coherence_values = coherence(
        vector_a, vector_b, fs=sampling_rate_hz, nperseg=min(nperseg, vector_a.size, vector_b.size)
    )
    in_band = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
    if np.any(in_band):
        return float(np.mean(coherence_values[in_band]))
    center_hz = (low_hz + high_hz) / 2.0
    return float(coherence_values[int(np.argmin(np.abs(frequencies_hz - center_hz)))])


def compute_stage_ground_truth_metrics(
    stage_epochs: dict[str, Any],
    stage_ground_truth_epochs: dict[str, Any],
    channel_name: str,
    sampling_rate_hz: float,
    band_hz: tuple[float, float],
    recovery_time_s: float,
    eval_window_max_s: float,
    min_eval_samples: int = 16,
) -> list[dict[str, float | str]]:
    """Compute per-stage PLV and coherence between one EEG channel and ground_truth."""
    if not stage_epochs:
        raise ValueError("stage_epochs is empty.")
    if list(stage_epochs.keys()) != list(stage_ground_truth_epochs.keys()):
        raise ValueError("stage_epochs and stage_ground_truth_epochs must share ordered keys.")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")
    if band_hz[1] <= band_hz[0]:
        raise ValueError("band_hz must satisfy high > low.")

    band_sos = butter(4, [band_hz[0], band_hz[1]], btype="bandpass", fs=sampling_rate_hz, output="sos")
    metrics_rows: list[dict[str, float | str]] = []

    for stage_name in stage_epochs:
        eeg_epoch_data = stage_epochs[stage_name].get_data(picks=[channel_name]).squeeze(1)
        gt_epoch_data = stage_ground_truth_epochs[stage_name].get_data().squeeze(1)
        stage_time = stage_epochs[stage_name].times

        eval_window_start_s = max(float(stage_time[0]), float(recovery_time_s))
        eval_window_end_s = min(float(stage_time[-1]), float(eval_window_max_s))
        eval_mask = (stage_time >= eval_window_start_s) & (stage_time <= eval_window_end_s)

        coherence_values: list[float] = []
        plv_values: list[float] = []
        if int(np.sum(eval_mask)) >= int(min_eval_samples):
            for eeg_epoch, gt_epoch in zip(eeg_epoch_data, gt_epoch_data):
                eeg_band = sosfiltfilt(band_sos, eeg_epoch[eval_mask])
                gt_band = sosfiltfilt(band_sos, gt_epoch[eval_mask])
                coherence_values.append(
                    compute_coherence_band(
                        signal_a=eeg_band,
                        signal_b=gt_band,
                        sampling_rate_hz=sampling_rate_hz,
                        low_hz=float(band_hz[0]),
                        high_hz=float(band_hz[1]),
                    )
                )
                phase_diff = np.angle(hilbert(eeg_band)) - np.angle(hilbert(gt_band))
                plv_values.append(float(np.abs(np.mean(np.exp(1j * phase_diff)))))
            coherence_mean = float(np.mean(coherence_values))
            plv_mean = float(np.mean(plv_values))
        else:
            coherence_mean = float("nan")
            plv_mean = float("nan")

        metrics_rows.append(
            {
                "stage": stage_name,
                "plv": plv_mean,
                "coherence_8_12": coherence_mean,
                "eval_window_start_s": eval_window_start_s,
                "eval_window_end_s": eval_window_end_s,
            }
        )
    return metrics_rows


def did_ground_truth_recover(metrics_rows: list[dict[str, float | str]]) -> bool:
    """Compare first vs last stage; require PLV and coherence improvements."""
    if len(metrics_rows) < 2:
        return False
    first = metrics_rows[0]
    last = metrics_rows[-1]
    first_plv = float(first["plv"])
    last_plv = float(last["plv"])
    first_coh = float(first["coherence_8_12"])
    last_coh = float(last["coherence_8_12"])
    return bool(
        np.isfinite(first_plv)
        and np.isfinite(last_plv)
        and np.isfinite(first_coh)
        and np.isfinite(last_coh)
        and last_plv > first_plv
        and last_coh > first_coh
    )


def build_stage_overlay_inputs_uv(
    stage_epochs: dict[str, Any],
    stage_ground_truth_epochs: dict[str, Any],
    channel_name: str,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Prepare per-stage mean traces (uV) + time axes for overlay plotting."""
    if not stage_epochs:
        raise ValueError("stage_epochs is empty.")
    if list(stage_epochs.keys()) != list(stage_ground_truth_epochs.keys()):
        raise ValueError("stage_epochs and stage_ground_truth_epochs must share ordered keys.")

    stage_eeg_traces_uv: dict[str, np.ndarray] = {}
    stage_ground_truth_traces_uv: dict[str, np.ndarray] = {}
    stage_time_axes_seconds: dict[str, np.ndarray] = {}
    for stage_name in stage_epochs:
        eeg_trace_uv = stage_epochs[stage_name].get_data(picks=[channel_name]).mean(axis=0).squeeze() * 1e6
        ground_truth_trace_uv = stage_ground_truth_epochs[stage_name].get_data().mean(axis=0).squeeze() * 1e6
        stage_eeg_traces_uv[stage_name] = np.asarray(eeg_trace_uv, dtype=float)
        stage_ground_truth_traces_uv[stage_name] = np.asarray(ground_truth_trace_uv, dtype=float)
        stage_time_axes_seconds[stage_name] = np.asarray(stage_epochs[stage_name].times, dtype=float)
    return stage_eeg_traces_uv, stage_ground_truth_traces_uv, stage_time_axes_seconds


def compute_recovery_latency_from_stage(
    stage_epoch: Any,
    channel_name: str,
    sampling_rate_hz: float,
    baseline_window_s: tuple[float, float],
    search_window_s: tuple[float, float],
    sigma_k: float = 5.0,
    min_consecutive_samples: int = 3,
    aggregate: str = "mean_abs",
) -> dict[str, float | bool]:
    """Estimate recovery time from one stage using the derivative metric."""
    channel_epochs = stage_epoch.get_data(picks=[channel_name]).squeeze(1)
    derivative_metric = compute_derivative_metric(
        epoch_data=channel_epochs,
        sampling_rate_hz=sampling_rate_hz,
        aggregate=aggregate,
    )
    recovery_info = find_return_to_baseline_time(
        metric=derivative_metric,
        time_axis_seconds=stage_epoch.times,
        baseline_window_s=baseline_window_s,
        search_window_s=search_window_s,
        sigma_k=sigma_k,
        min_consecutive_samples=min_consecutive_samples,
    )
    found = bool(recovery_info["found"])
    recovery_time_s = float(recovery_info["return_time_s"]) if found else float(search_window_s[1])
    return {
        "found": found,
        "recovery_time_s": recovery_time_s,
        "recovery_latency_ms": 1000.0 * recovery_time_s,
    }


def save_metrics_rows_csv(
    metrics_rows: list[dict[str, float | str]],
    output_path: str | Path,
    fieldnames: list[str] | None = None,
) -> None:
    """Save metrics rows to CSV with deterministic field order."""
    if not metrics_rows:
        raise ValueError("metrics_rows is empty.")
    resolved_fields = fieldnames if fieldnames is not None else list(metrics_rows[0].keys())
    with open(Path(output_path), "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=resolved_fields)
        writer.writeheader()
        writer.writerows(metrics_rows)


def compute_band_snr_db(
    signal_1d: np.ndarray,
    sampling_rate_hz: float,
    signal_band_hz: tuple[float, float],
    noise_band_hz: tuple[float, float],
    exclude_band_hz: tuple[float, float] | None = None,
) -> float:
    """Band SNR estimate from Welch PSD using one signal band and one broad noise band."""
    vector = np.asarray(signal_1d, dtype=float).ravel()
    frequencies_hz, psd_values = welch(vector, fs=sampling_rate_hz, nperseg=min(4096, vector.size))

    def _band_power(low_hz: float, high_hz: float) -> float:
        in_band = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
        return float(np.trapz(psd_values[in_band], frequencies_hz[in_band])) if np.any(in_band) else 0.0

    signal_low_hz, signal_high_hz = map(float, signal_band_hz)
    noise_mask = (frequencies_hz >= float(noise_band_hz[0])) & (frequencies_hz <= float(noise_band_hz[1]))
    if exclude_band_hz is not None:
        exclude_low_hz, exclude_high_hz = map(float, exclude_band_hz)
        noise_mask &= ~((frequencies_hz >= exclude_low_hz) & (frequencies_hz <= exclude_high_hz))

    signal_power = _band_power(signal_low_hz, signal_high_hz)
    noise_power = float(np.trapz(psd_values[noise_mask], frequencies_hz[noise_mask])) if np.any(noise_mask) else 0.0
    return float(10.0 * np.log10((signal_power + 1e-30) / (noise_power + 1e-30)))


def compute_band_peak_ratio(
    signal_1d: np.ndarray,
    sampling_rate_hz: float,
    signal_band_hz: tuple[float, float],
    flank_width_hz: float,
    flank_gap_hz: float = 0.0,
) -> float:
    """Local peak ratio: mean PSD in the signal band divided by the adjacent flank PSD."""
    vector = np.asarray(signal_1d, dtype=float).ravel()
    frequencies_hz, psd_values = welch(vector, fs=sampling_rate_hz, nperseg=min(4096, vector.size))

    signal_low_hz, signal_high_hz = map(float, signal_band_hz)
    signal_mask = (frequencies_hz >= signal_low_hz) & (frequencies_hz <= signal_high_hz)
    lower_flank_mask = (
        (frequencies_hz >= max(0.0, signal_low_hz - flank_gap_hz - flank_width_hz))
        & (frequencies_hz <= max(0.0, signal_low_hz - flank_gap_hz))
    )
    upper_flank_mask = (
        (frequencies_hz >= signal_high_hz + flank_gap_hz)
        & (frequencies_hz <= signal_high_hz + flank_gap_hz + flank_width_hz)
    )
    flank_mask = lower_flank_mask | upper_flank_mask
    if not np.any(signal_mask) or not np.any(flank_mask):
        return float("nan")

    signal_density = float(np.mean(psd_values[signal_mask]))
    flank_density = float(np.mean(psd_values[flank_mask]))
    return float(signal_density / (flank_density + 1e-30))


def sample_phase_differences(
    reference_signal: np.ndarray,
    target_signal: np.ndarray,
    sampling_rate_hz: float,
    reference_frequency_hz: float,
    signal_band_hz: tuple[float, float] = None,
) -> np.ndarray:
    """Sample wrapped target-vs-reference phase differences once per reference cycle.

    If signal_band_hz is provided, filter signals to that band before Hilbert transform.
    """
    reference_vector = np.asarray(reference_signal, dtype=float).ravel()
    target_vector = np.asarray(target_signal, dtype=float).ravel()

    # Filter to signal band before Hilbert (if band specified)
    if signal_band_hz is not None:
        reference_vector = filter_signal(reference_vector[np.newaxis, :], sampling_rate_hz, signal_band_hz[0], signal_band_hz[1])[0]
        target_vector = filter_signal(target_vector[np.newaxis, :], sampling_rate_hz, signal_band_hz[0], signal_band_hz[1])[0]

    min_peak_distance_samples = max(1, int(round(0.8 * sampling_rate_hz / reference_frequency_hz)))
    reference_peaks, _ = find_peaks(reference_vector, distance=min_peak_distance_samples)
    if reference_peaks.size < 4:
        reference_peaks = np.arange(0, reference_vector.size, min_peak_distance_samples, dtype=int)
    phase_difference = np.angle(hilbert(target_vector)) - np.angle(hilbert(reference_vector))
    return np.angle(np.exp(1j * phase_difference[reference_peaks]))


def approximate_rayleigh_p(phases: np.ndarray) -> float:
    """Approximate Rayleigh p-value for one circular phase sample."""
    phase_vector = np.asarray(phases, dtype=float).ravel()
    if phase_vector.size < 2:
        return float("nan")
    resultant_length = float(np.abs(np.sum(np.exp(1j * phase_vector))))
    z_value = (resultant_length ** 2) / float(phase_vector.size)
    return float(max(np.exp(-z_value) * (1.0 + (2.0 * z_value - z_value ** 2) / (4.0 * phase_vector.size)), 0.0))


def find_psd_peak_frequency(
    signal_1d: np.ndarray,
    sampling_rate_hz: float,
    frequency_range_hz: tuple[float, float],
) -> float:
    """Return the strongest Welch PSD peak inside one frequency range."""
    vector = np.asarray(signal_1d, dtype=float).ravel()
    frequencies_hz, psd_values = welch(vector, fs=sampling_rate_hz, nperseg=min(4096, vector.size))
    visible_mask = (frequencies_hz >= frequency_range_hz[0]) & (frequencies_hz <= frequency_range_hz[1])
    if not np.any(visible_mask):
        return float("nan")
    visible_freqs_hz = frequencies_hz[visible_mask]
    visible_psd_values = psd_values[visible_mask]
    return float(visible_freqs_hz[int(np.argmax(visible_psd_values))])


def compute_epoch_plv_summary(
    signal_epochs: np.ndarray,
    reference_epochs: np.ndarray,
    sampling_rate_hz: float,
    signal_band_hz: tuple[float, float],
    reference_frequency_hz: float,
    time_window_s: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Compute one scalar PLV summary from matched epochs using one phase sample per reference cycle.

    If time_window_s is provided, restrict computation to [start_s, end_s] relative to epoch start.
    """
    # Crop to time window if specified
    if time_window_s is not None:
        start_sample = int(np.round(time_window_s[0] * sampling_rate_hz))
        end_sample = int(np.round(time_window_s[1] * sampling_rate_hz))
        signal_epochs = signal_epochs[:, start_sample:end_sample]
        reference_epochs = reference_epochs[:, start_sample:end_sample]

    band_metrics = compute_band_limited_epoch_triplet_metrics(
        signal_epochs,
        reference_epochs,
        sampling_rate_hz,
        signal_band_hz,
    )

    phase_samples = []
    for signal_epoch, reference_epoch in zip(
        band_metrics["signal_band_epochs"],
        band_metrics["reference_band_epochs"],
        strict=True,
    ):
        phase_samples.append(
            sample_phase_differences(
                reference_signal=reference_epoch,
                target_signal=signal_epoch,
                sampling_rate_hz=sampling_rate_hz,
                reference_frequency_hz=reference_frequency_hz,
                signal_band_hz=signal_band_hz,
            )
        )
    sampled_phase_differences = np.concatenate(phase_samples)
    plv_value = float(np.abs(np.mean(np.exp(1j * sampled_phase_differences))))
    return {
        "plv": plv_value,
        "p_value": approximate_rayleigh_p(sampled_phase_differences),
        "phase_samples": sampled_phase_differences,
        "mean_gt_locking": float(np.mean(band_metrics["itpc_curve"])),
    }


def select_top_channels_against_reference(
    channel_epochs: np.ndarray,
    reference_epochs: np.ndarray,
    channel_names: list[str],
    sampling_rate_hz: float,
    signal_band_hz: tuple[float, float],
    view_band_hz: tuple[float, float],
    reference_frequency_hz: float,
    top_channel_count: int,
) -> dict[str, Any]:
    """Keep the best in-band reference-matching channels and summarize their PLV."""
    channel_rows = []
    for channel_index, channel_name in enumerate(channel_names):
        channel_epoch_matrix = np.asarray(channel_epochs[:, channel_index, :], dtype=float)
        channel_peak_hz = find_psd_peak_frequency(
            channel_epoch_matrix.reshape(-1),
            sampling_rate_hz,
            view_band_hz,
        )
        channel_metrics = compute_epoch_plv_summary(
            channel_epoch_matrix,
            reference_epochs,
            sampling_rate_hz,
            signal_band_hz,
            reference_frequency_hz,
        )
        channel_rows.append(
            {
                "name": channel_name,
                "peak_hz": float(channel_peak_hz),
                "plv": float(channel_metrics["plv"]),
                "p_value": float(channel_metrics["p_value"]),
                "mean_gt_locking": float(channel_metrics["mean_gt_locking"]),
                "phase_samples": np.asarray(channel_metrics["phase_samples"], dtype=float),
            }
        )

    in_band_rows = [
        row
        for row in channel_rows
        if signal_band_hz[0] <= row["peak_hz"] <= signal_band_hz[1]
    ]
    if len(in_band_rows) == 0:
        return {
            "selected_rows": [],
            "pooled_phase_samples": np.array([], dtype=float),
            "pooled_plv": float("nan"),
            "pooled_p_value": float("nan"),
            "mean_selected_plv": float("nan"),
            "pooled_mean_gt_locking": float("nan"),
            "best_channel_name": "none",
            "best_channel_plv": float("nan"),
            "best_channel_p_value": float("nan"),
            "best_phase_samples": np.array([], dtype=float),
            "selection_note": "no in-band channel",
        }

    ranking_rows = in_band_rows
    selection_note = "in-band only"
    selected_rows = sorted(
        ranking_rows,
        key=lambda row: (row["plv"], -abs(row["peak_hz"] - reference_frequency_hz)),
        reverse=True,
    )[:top_channel_count]

    pooled_phase_samples = np.concatenate([row["phase_samples"] for row in selected_rows])
    pooled_plv = float(np.abs(np.mean(np.exp(1j * pooled_phase_samples))))
    return {
        "selected_rows": selected_rows,
        "pooled_phase_samples": pooled_phase_samples,
        "pooled_plv": pooled_plv,
        "pooled_p_value": approximate_rayleigh_p(pooled_phase_samples),
        "mean_selected_plv": float(np.mean([row["plv"] for row in selected_rows])),
        "pooled_mean_gt_locking": float(np.mean([row["mean_gt_locking"] for row in selected_rows])),
        "best_channel_name": str(selected_rows[0]["name"]),
        "best_channel_plv": float(selected_rows[0]["plv"]),
        "best_channel_p_value": float(selected_rows[0]["p_value"]),
        "best_phase_samples": np.asarray(selected_rows[0]["phase_samples"], dtype=float),
        "selection_note": selection_note,
    }


def compute_snr10_db(signal_1d: np.ndarray, sampling_rate_hz: float) -> float:
    """10 Hz SNR estimate: signal band 9-11 Hz vs noise bands 3-8 and 12-22 Hz."""
    return compute_band_snr_db(
        signal_1d=signal_1d,
        sampling_rate_hz=sampling_rate_hz,
        signal_band_hz=(9.0, 11.0),
        noise_band_hz=(3.0, 22.0),
        exclude_band_hz=(9.0, 11.0),
    )


def compute_roi_band_power_summary(
    roi_data: np.ndarray,
    sampling_rate_hz: float,
    theta_band_hz: tuple[float, float] = (4.0, 7.0),
    alpha_band_hz: tuple[float, float] = (8.0, 12.0),
    psd_band_hz: tuple[float, float] = (1.0, 20.0),
    notch_hz: float = 50.0,
) -> dict[str, float | np.ndarray]:
    """Summarize theta, alpha, and theta/alpha ratio for continuous ROI data."""
    roi_array = np.asarray(roi_data, dtype=float)
    if roi_array.ndim != 2:
        raise ValueError("roi_data must have shape (n_channels, n_times).")
    if roi_array.shape[0] < 1 or roi_array.shape[1] < 4:
        raise ValueError("roi_data must contain at least 1 channel and 4 samples.")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")

    filtered_roi = filter_signal(
        data=roi_array,
        sampling_rate_hz=sampling_rate_hz,
        low_hz=float(psd_band_hz[0]),
        high_hz=float(psd_band_hz[1]),
        notch_hz=notch_hz,
    )
    frequencies_hz, psd_per_channel = welch(
        filtered_roi,
        fs=sampling_rate_hz,
        axis=-1,
        nperseg=min(4096, filtered_roi.shape[-1]),
    )
    frequencies_hz = np.asarray(frequencies_hz, dtype=float)
    psd_per_channel = np.asarray(psd_per_channel, dtype=float)

    def _integrate_band(low_hz: float, high_hz: float) -> np.ndarray:
        band_mask = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
        if not np.any(band_mask):
            raise ValueError(f"Band {(low_hz, high_hz)} Hz does not overlap the PSD frequencies.")
        return np.trapz(psd_per_channel[:, band_mask], frequencies_hz[band_mask], axis=-1)

    theta_power_per_channel = np.asarray(_integrate_band(*theta_band_hz), dtype=float)
    alpha_power_per_channel = np.asarray(_integrate_band(*alpha_band_hz), dtype=float)
    theta_alpha_ratio_per_channel = theta_power_per_channel / (alpha_power_per_channel + 1e-30)

    if not np.all(np.isfinite(theta_alpha_ratio_per_channel)):
        raise RuntimeError("Theta/alpha ratio contains non-finite values.")

    return {
        "frequencies_hz": frequencies_hz,
        "psd_per_channel": psd_per_channel,
        "roi_mean_psd": psd_per_channel.mean(axis=0),
        "theta_power_per_channel": theta_power_per_channel,
        "alpha_power_per_channel": alpha_power_per_channel,
        "theta_alpha_ratio_per_channel": theta_alpha_ratio_per_channel,
        "theta_power": float(theta_power_per_channel.mean()),
        "alpha_power": float(alpha_power_per_channel.mean()),
        "theta_alpha_ratio": float(theta_alpha_ratio_per_channel.mean()),
    }


def compute_windowed_roi_plv(
    roi_data: np.ndarray,
    sampling_rate_hz: float,
    band_hz: tuple[float, float],
    window_length_s: float = 2.0,
    window_step_s: float = 1.0,
    notch_hz: float = 50.0,
) -> dict[str, float | np.ndarray]:
    """Compute mean pairwise ROI PLV over sliding windows of continuous data."""
    roi_array = np.asarray(roi_data, dtype=float)
    if roi_array.ndim != 2:
        raise ValueError("roi_data must have shape (n_channels, n_times).")
    if roi_array.shape[0] < 2:
        raise ValueError("Need at least 2 ROI channels to compute PLV.")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")
    if window_length_s <= 0 or window_step_s <= 0:
        raise ValueError("window_length_s and window_step_s must be > 0.")

    filtered_roi = filter_signal(
        data=roi_array,
        sampling_rate_hz=sampling_rate_hz,
        low_hz=float(band_hz[0]),
        high_hz=float(band_hz[1]),
        notch_hz=notch_hz,
    )
    analytic_signal = hilbert(filtered_roi, axis=-1)
    phase = np.angle(analytic_signal)

    window_length_samples = int(round(window_length_s * sampling_rate_hz))
    window_step_samples = int(round(window_step_s * sampling_rate_hz))
    if window_length_samples < 2 or window_step_samples < 1:
        raise ValueError("Window length/step produce too few samples.")
    if filtered_roi.shape[-1] < window_length_samples:
        raise ValueError("Continuous block is shorter than one PLV window.")

    window_plv_values: list[float] = []
    window_mean_angles: list[float] = []
    window_resultant_lengths: list[float] = []
    for start_index in range(0, filtered_roi.shape[-1] - window_length_samples + 1, window_step_samples):
        stop_index = start_index + window_length_samples
        phase_window = phase[:, start_index:stop_index]
        pair_plvs: list[float] = []
        pair_vectors: list[complex] = []
        for channel_a in range(phase_window.shape[0] - 1):
            for channel_b in range(channel_a + 1, phase_window.shape[0]):
                phase_diff = phase_window[channel_a] - phase_window[channel_b]
                pair_vector = np.mean(np.exp(1j * phase_diff))
                pair_vectors.append(pair_vector)
                pair_plvs.append(float(np.abs(pair_vector)))
        if pair_plvs:
            window_plv_values.append(float(np.mean(pair_plvs)))
            mean_vector = np.mean(np.asarray(pair_vectors, dtype=complex))
            window_mean_angles.append(float(np.angle(mean_vector)))
            window_resultant_lengths.append(float(np.abs(mean_vector)))

    window_plv = np.asarray(window_plv_values, dtype=float)
    window_mean_angle = np.asarray(window_mean_angles, dtype=float)
    window_resultant_length = np.asarray(window_resultant_lengths, dtype=float)
    if window_plv.size == 0:
        raise RuntimeError("No PLV windows were computed.")
    if not np.all(np.isfinite(window_plv)):
        raise RuntimeError("PLV summary contains non-finite values.")
    if not np.all(np.isfinite(window_mean_angle)) or not np.all(np.isfinite(window_resultant_length)):
        raise RuntimeError("PLV phase summary contains non-finite values.")

    mean_window_vector = np.mean(window_resultant_length * np.exp(1j * window_mean_angle))

    return {
        "window_plv": window_plv,
        "window_mean_angle": window_mean_angle,
        "window_resultant_length": window_resultant_length,
        "mean_angle": float(np.angle(mean_window_vector)),
        "mean_resultant_length": float(np.abs(mean_window_vector)),
        "mean_plv": float(window_plv.mean()),
        "std_plv": float(window_plv.std()),
        "n_windows": int(window_plv.size),
    }


def compute_windowed_roi_band_power(
    roi_data: np.ndarray,
    sampling_rate_hz: float,
    theta_band_hz: tuple[float, float] = (4.0, 7.0),
    alpha_band_hz: tuple[float, float] = (8.0, 12.0),
    psd_band_hz: tuple[float, float] = (1.0, 20.0),
    window_length_s: float = 10.0,
    window_step_s: float = 10.0,
    notch_hz: float = 50.0,
) -> dict[str, float | np.ndarray]:
    """Compute theta, alpha, and theta/alpha ratio over sliding windows."""
    roi_array = np.asarray(roi_data, dtype=float)
    if roi_array.ndim != 2:
        raise ValueError("roi_data must have shape (n_channels, n_times).")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")
    if window_length_s <= 0 or window_step_s <= 0:
        raise ValueError("window_length_s and window_step_s must be > 0.")

    window_length_samples = int(round(window_length_s * sampling_rate_hz))
    window_step_samples = int(round(window_step_s * sampling_rate_hz))
    if window_length_samples < 4 or window_step_samples < 1:
        raise ValueError("Window length/step produce too few samples.")
    if roi_array.shape[-1] < window_length_samples:
        raise ValueError("Continuous block is shorter than one power window.")

    theta_power_values: list[float] = []
    alpha_power_values: list[float] = []
    theta_alpha_ratio_values: list[float] = []
    window_start_seconds: list[float] = []
    window_stop_seconds: list[float] = []
    for start_index in range(0, roi_array.shape[-1] - window_length_samples + 1, window_step_samples):
        stop_index = start_index + window_length_samples
        window_summary = compute_roi_band_power_summary(
            roi_data=roi_array[:, start_index:stop_index],
            sampling_rate_hz=sampling_rate_hz,
            theta_band_hz=theta_band_hz,
            alpha_band_hz=alpha_band_hz,
            psd_band_hz=psd_band_hz,
            notch_hz=notch_hz,
        )
        theta_power_values.append(float(window_summary["theta_power"]))
        alpha_power_values.append(float(window_summary["alpha_power"]))
        theta_alpha_ratio_values.append(float(window_summary["theta_alpha_ratio"]))
        window_start_seconds.append(float(start_index / sampling_rate_hz))
        window_stop_seconds.append(float(stop_index / sampling_rate_hz))

    theta_power_per_window = np.asarray(theta_power_values, dtype=float)
    alpha_power_per_window = np.asarray(alpha_power_values, dtype=float)
    theta_alpha_ratio_per_window = np.asarray(theta_alpha_ratio_values, dtype=float)
    if theta_power_per_window.size == 0:
        raise RuntimeError("No power windows were computed.")

    return {
        "window_start_seconds": np.asarray(window_start_seconds, dtype=float),
        "window_stop_seconds": np.asarray(window_stop_seconds, dtype=float),
        "theta_power_per_window": theta_power_per_window,
        "alpha_power_per_window": alpha_power_per_window,
        "theta_alpha_ratio_per_window": theta_alpha_ratio_per_window,
        "theta_power": float(theta_power_per_window.mean()),
        "alpha_power": float(alpha_power_per_window.mean()),
        "theta_alpha_ratio": float(theta_alpha_ratio_per_window.mean()),
        "n_windows": int(theta_power_per_window.size),
    }


def compute_split_segment_post_tfr(
    pre_epochs: np.ndarray,
    pre_times_s: np.ndarray,
    post_epochs: np.ndarray,
    post_times_s: np.ndarray,
    sampling_rate_hz: float,
    baseline_window_s: tuple[float, float] = (-2.75, -1.25),
    display_window_s: tuple[float, float] = (0.25, 2.50),
    summary_windows_s: dict[str, tuple[float, float]] | None = None,
    band_definitions_hz: dict[str, tuple[float, float]] | None = None,
) -> dict[str, np.ndarray | list[dict[str, float | int | str]] | dict[str, tuple[float, float]]]:
    """Compute segment-safe Morlet power for separated pre/post epochs.

    The stimulation-contaminated interval must already be excluded. This helper
    pads each segment reflectively, computes Morlet power independently for the
    clean pre and post arrays, and normalizes post power to the clean pre
    baseline from the same trial.
    """
    pre_array = np.asarray(pre_epochs, dtype=float)
    post_array = np.asarray(post_epochs, dtype=float)
    pre_times = np.asarray(pre_times_s, dtype=float).ravel()
    post_times = np.asarray(post_times_s, dtype=float).ravel()
    if pre_array.ndim != 3 or post_array.ndim != 3:
        raise ValueError("pre_epochs and post_epochs must have shape (n_epochs, n_channels, n_times).")
    if pre_array.shape[:2] != post_array.shape[:2]:
        raise ValueError("Pre and post segments must match in n_epochs and n_channels.")
    if pre_array.shape[-1] != pre_times.size or post_array.shape[-1] != post_times.size:
        raise ValueError("Segment sample axis and time axis length must match.")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")

    resolved_summary_windows = (
        {"early": (0.30, 1.30), "late": (1.30, 2.30)}
        if summary_windows_s is None
        else summary_windows_s
    )
    resolved_band_definitions = (
        {
            "theta": (4.0, 7.0),
            "alpha": (8.0, 12.0),
            "beta": (13.0, 30.0),
            "low_gamma": (30.0, 40.0),
        }
        if band_definitions_hz is None
        else band_definitions_hz
    )

    frequencies_hz = np.arange(4.0, 41.0, 1.0, dtype=float)
    n_cycles = np.clip(frequencies_hz / 2.0, 3.0, 7.0)
    half_wavelet_s = n_cycles / (2.0 * frequencies_hz)
    max_half_wavelet_s = float(np.max(half_wavelet_s))
    pad_samples = int(np.ceil(max_half_wavelet_s * sampling_rate_hz))
    if pad_samples < 1:
        raise RuntimeError("Computed non-positive padding for Morlet transform.")

    pre_duration_s = float(pre_times[-1] - pre_times[0] + 1.0 / sampling_rate_hz)
    post_duration_s = float(post_times[-1] - post_times[0] + 1.0 / sampling_rate_hz)
    min_pre_duration_s = baseline_window_s[1] - baseline_window_s[0]
    min_post_duration_s = display_window_s[1] - display_window_s[0]
    if pre_duration_s < min_pre_duration_s:
        raise ValueError(
            f"Pre segment ({pre_duration_s:.3f}s) is shorter than the minimum "
            f"required duration ({min_pre_duration_s:.3f}s)."
        )
    if post_duration_s < min_post_duration_s:
        raise ValueError(
            f"Post segment ({post_duration_s:.3f}s) is shorter than the minimum "
            f"required duration ({min_post_duration_s:.3f}s)."
        )
    if pre_array.shape[-1] < 3 or post_array.shape[-1] < 3:
        raise ValueError("Each segment must contain at least 3 samples for reflective padding.")
    if pre_array.shape[-1] <= 1 or post_array.shape[-1] <= 1:
        raise ValueError("Segment is too short for reflective padding at the requested frequency range.")

    baseline_mask = (pre_times >= baseline_window_s[0]) & (pre_times <= baseline_window_s[1])
    if not np.any(baseline_mask):
        raise ValueError("baseline_window_s does not overlap the pre segment.")
    valid_post_time_mask = (post_times >= display_window_s[0]) & (post_times <= display_window_s[1])
    if not np.any(valid_post_time_mask):
        raise ValueError("display_window_s does not overlap the post segment.")

    pre_centered = pre_array - pre_array.mean(axis=-1, keepdims=True)
    post_centered = post_array - post_array.mean(axis=-1, keepdims=True)
    pre_padded = np.pad(pre_centered, ((0, 0), (0, 0), (pad_samples, pad_samples)), mode="reflect")
    post_padded = np.pad(post_centered, ((0, 0), (0, 0), (pad_samples, pad_samples)), mode="reflect")

    pre_power = np.asarray(
        tfr_array_morlet(
            pre_padded,
            sfreq=sampling_rate_hz,
            freqs=frequencies_hz,
            n_cycles=n_cycles,
            output="power",
            zero_mean=True,
        )[..., pad_samples:-pad_samples],
        dtype=np.float32,
    )
    post_power = np.asarray(
        tfr_array_morlet(
            post_padded,
            sfreq=sampling_rate_hz,
            freqs=frequencies_hz,
            n_cycles=n_cycles,
            output="power",
            zero_mean=True,
        )[..., pad_samples:-pad_samples],
        dtype=np.float32,
    )
    if pre_power.shape[-1] != pre_times.size or post_power.shape[-1] != post_times.size:
        raise RuntimeError("Morlet power shape does not match the segment time axis.")
    if not np.all(np.isfinite(pre_power)) or not np.all(np.isfinite(post_power)):
        raise RuntimeError("Morlet power contains non-finite values.")

    baseline_power = pre_power[..., baseline_mask].mean(axis=-1, keepdims=True)
    if np.any(baseline_power <= 0):
        raise RuntimeError("Baseline power must be strictly positive for log-ratio normalization.")
    post_power_logratio = np.asarray(
        10.0 * np.log10((post_power + 1e-30) / (baseline_power + 1e-30)),
        dtype=np.float32,
    )

    band_window_metrics: list[dict[str, float | int | str]] = []
    for band_name, (low_hz, high_hz) in resolved_band_definitions.items():
        band_mask = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
        if not np.any(band_mask):
            raise ValueError(f"Band {band_name} does not overlap the Morlet frequencies.")
        pre_baseline_per_epoch = pre_power[:, :, band_mask, :][..., baseline_mask].mean(axis=(1, 2, 3))
        for window_name, (window_start_s, window_stop_s) in resolved_summary_windows.items():
            window_mask = (post_times >= window_start_s) & (post_times <= window_stop_s)
            if not np.any(window_mask):
                raise ValueError(f"Summary window {window_name} does not overlap the post segment.")
            post_logratio_per_epoch = post_power_logratio[:, :, band_mask, :][..., window_mask].mean(axis=(1, 2, 3))
            post_power_per_epoch = post_power[:, :, band_mask, :][..., window_mask].mean(axis=(1, 2, 3))
            for epoch_index, (baseline_value, post_power_value, logratio_value) in enumerate(
                zip(pre_baseline_per_epoch, post_power_per_epoch, post_logratio_per_epoch, strict=True)
            ):
                band_window_metrics.append(
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

    return {
        "frequencies_hz": frequencies_hz,
        "pre_times_s": pre_times,
        "post_times_s": post_times,
        "pre_power": pre_power,
        "post_power": post_power,
        "post_power_logratio": post_power_logratio,
        "valid_post_time_mask": valid_post_time_mask,
        "band_window_metrics": band_window_metrics,
        "band_definitions_hz": resolved_band_definitions,
        "summary_windows_s": resolved_summary_windows,
        "edge_guard_seconds": max_half_wavelet_s,
    }


def compute_two_sample_permutation_stats(
    pre_values: np.ndarray,
    post_values: np.ndarray,
    n_permutations: int = 5000,
    n_bootstraps: int = 2000,
    random_seed: int = 0,
) -> dict[str, float | int]:
    """Two-sided permutation test with bootstrap CI for mean(post - pre)."""
    pre_array = np.asarray(pre_values, dtype=float).ravel()
    post_array = np.asarray(post_values, dtype=float).ravel()
    if pre_array.size == 0 or post_array.size == 0:
        raise ValueError("pre_values and post_values must both be non-empty.")
    if not np.all(np.isfinite(pre_array)) or not np.all(np.isfinite(post_array)):
        raise ValueError("pre_values and post_values must be finite.")
    if n_permutations < 1 or n_bootstraps < 1:
        raise ValueError("n_permutations and n_bootstraps must be >= 1.")

    rng = np.random.default_rng(random_seed)
    observed_difference = float(post_array.mean() - pre_array.mean())
    combined = np.concatenate([pre_array, post_array])
    n_pre = int(pre_array.size)
    permutation_differences = np.empty(n_permutations, dtype=float)
    for permutation_index in range(n_permutations):
        shuffled = rng.permutation(combined)
        permutation_differences[permutation_index] = float(shuffled[n_pre:].mean() - shuffled[:n_pre].mean())
    p_value = float(
        (1 + np.sum(np.abs(permutation_differences) >= abs(observed_difference))) / (n_permutations + 1)
    )

    bootstrap_differences = np.empty(n_bootstraps, dtype=float)
    for bootstrap_index in range(n_bootstraps):
        pre_boot = rng.choice(pre_array, size=pre_array.size, replace=True)
        post_boot = rng.choice(post_array, size=post_array.size, replace=True)
        bootstrap_differences[bootstrap_index] = float(post_boot.mean() - pre_boot.mean())
    ci_low, ci_high = np.percentile(bootstrap_differences, [2.5, 97.5])

    pre_var = float(np.var(pre_array, ddof=1)) if pre_array.size > 1 else 0.0
    post_var = float(np.var(post_array, ddof=1)) if post_array.size > 1 else 0.0
    pooled_variance = (
        ((pre_array.size - 1) * pre_var + (post_array.size - 1) * post_var) / max(pre_array.size + post_array.size - 2, 1)
    )
    pooled_sd = float(np.sqrt(max(pooled_variance, 0.0)))
    effect_size_d = float(observed_difference / pooled_sd) if pooled_sd > 0 else 0.0

    return {
        "pre_mean": float(pre_array.mean()),
        "post_mean": float(post_array.mean()),
        "difference": observed_difference,
        "p_value": p_value,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "effect_size_d": effect_size_d,
        "n_pre": int(pre_array.size),
        "n_post": int(post_array.size),
    }


def correct_pvalues_bh(p_values: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR correction."""
    values = np.asarray(p_values, dtype=float).ravel()
    if values.size == 0:
        raise ValueError("p_values is empty.")
    if not np.all(np.isfinite(values)) or np.any(values < 0) or np.any(values > 1):
        raise ValueError("p_values must be finite and within [0, 1].")

    order = np.argsort(values)
    ordered = values[order]
    n_values = ordered.size
    adjusted_desc = np.minimum.accumulate((ordered[::-1] * n_values) / np.arange(n_values, 0, -1))
    adjusted = np.clip(adjusted_desc[::-1], 0.0, 1.0)
    corrected = np.empty_like(adjusted)
    corrected[order] = adjusted
    return corrected


def compute_snr_linear(
    signal_epochs: np.ndarray,
    sampling_rate_hz: float,
    signal_band_hz: tuple[float, float],
    view_band_hz: tuple[float, float],
) -> np.ndarray | float:
    """Compute SNR as linear ratio: power(signal_band) / power(view_band).

    SNR = mean power in signal_band / mean power in broadband view_band.
    Supports 1D (n_samples), 2D (n_epochs, n_samples), or 3D (n_channels, n_epochs, n_samples).

    Returns scalar for 1D input, scalar for 2D (concatenated across epochs), (n_channels,) for 3D.
    """
    signal_array = np.asarray(signal_epochs, dtype=float)
    if signal_array.ndim > 3:
        raise ValueError("signal_epochs must be 1D, 2D, or 3D.")

    # Handle dimensionality
    if signal_array.ndim == 1:
        # 1D: flatten already (n_samples,)
        flat = signal_array
        is_multichannel = False
    elif signal_array.ndim == 2:
        # 2D: (n_epochs, n_samples) → concatenate to (n_epochs*n_samples,)
        flat = signal_array.reshape(-1)
        is_multichannel = False
    else:
        # 3D: (n_channels, n_epochs, n_samples) → per-channel (n_channels, n_epochs*n_samples)
        flat = signal_array.reshape(signal_array.shape[0], -1)
        is_multichannel = True

    # Compute power spectrum via FFT
    psd = np.abs(np.fft.rfft(flat, axis=-1)) ** 2
    freqs_hz = np.fft.rfftfreq(flat.shape[-1], 1.0 / sampling_rate_hz)

    # Frequency masks
    signal_mask = (freqs_hz >= signal_band_hz[0]) & (freqs_hz <= signal_band_hz[1])
    view_mask = (freqs_hz >= view_band_hz[0]) & (freqs_hz <= view_band_hz[1])

    # Compute power in each band
    if is_multichannel:
        signal_power = np.mean(psd[:, signal_mask], axis=1)
        view_power = np.mean(psd[:, view_mask], axis=1)
    else:
        signal_power = float(np.mean(psd[signal_mask]))
        view_power = float(np.mean(psd[view_mask]))

    # Avoid divide by zero
    view_power = np.maximum(view_power, 1e-10)
    snr = signal_power / view_power

    return snr


def compute_itpc_timecourse(
    signal_epochs: np.ndarray,
    reference_epochs: np.ndarray,
    sampling_rate_hz: float,
    band_hz: tuple[float, float],
    time_window_s: tuple[float, float] | None = None,
) -> np.ndarray:
    """Compute ITPC (Inter-Trial Phase Clustering) timecourse: phase coherence per sample.

    Band-pass filter matched epoch pairs, compute instantaneous phase via Hilbert,
    then compute phase synchrony per sample: ITPC = |mean(exp(i*phase_diff))|.

    If time_window_s is provided, restrict computation to [start_s, end_s] relative to epoch start.

    Returns (n_samples,) array with ITPC ∈ [0, 1] per sample.
    """
    signal_array = np.asarray(signal_epochs, dtype=float)
    reference_array = np.asarray(reference_epochs, dtype=float)
    n_epochs = min(signal_array.shape[0], reference_array.shape[0])
    if n_epochs < 1:
        raise ValueError("Need at least one matched epoch to compute ITPC.")

    # Band-pass filter to target band (before cropping, to maintain filter stability)
    signal_band = filter_signal(signal_array[:n_epochs], sampling_rate_hz, band_hz[0], band_hz[1])
    reference_band = filter_signal(reference_array[:n_epochs], sampling_rate_hz, band_hz[0], band_hz[1])

    # Crop to time window if specified
    if time_window_s is not None:
        start_sample = int(np.round(time_window_s[0] * sampling_rate_hz))
        end_sample = int(np.round(time_window_s[1] * sampling_rate_hz))
        signal_band = signal_band[:, start_sample:end_sample]
        reference_band = reference_band[:, start_sample:end_sample]

    # Instantaneous phase via Hilbert transform
    signal_phase = np.angle(hilbert(signal_band, axis=-1))
    reference_phase = np.angle(hilbert(reference_band, axis=-1))

    # Phase difference and ITPC timecourse
    phase_diff = signal_phase - reference_phase
    itpc_curve = np.abs(np.mean(np.exp(1j * phase_diff), axis=0))

    if itpc_curve.ndim != 1:
        raise RuntimeError("ITPC curve must be 1D.")
    if not np.all(np.isfinite(itpc_curve)):
        raise RuntimeError("ITPC curve contains non-finite values.")
    return np.asarray(itpc_curve, dtype=float)
