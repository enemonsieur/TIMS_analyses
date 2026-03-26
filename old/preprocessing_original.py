"""
Functional preprocessing utilities for TIMS pilot dose-response data.

Design goals:
- Minimal, readable, and easy to modify.
- No classes.
- Explicit array-shape comments at key boundaries.
"""

from __future__ import annotations

from pathlib import Path
import csv
import warnings
from typing import Any

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, coherence, filtfilt, find_peaks, hilbert, iirnotch, sosfiltfilt, welch


def load_and_extract_signals(
    stim_vhdr_path: str,
    baseline_vhdr_path: str,
    reference_channel: str = "Cz",
    bad_channels_to_drop: list[str] | None = None,
    preload: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """Load stim/baseline recordings and return all required arrays.

    Returns a dictionary with:
    - raw objects for plotting (`stim_raw`, `baseline_raw`)
    - core vectors (`stim_marker`, `ground_truth_*`, `*_reference`) shape: (n_times,)
    - EEG matrices (`stim_eeg`, `baseline_eeg`) shape: (n_eeg, n_times)
    - metadata (`sampling_rate_hz`, channel lists)
    """
    import mne

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="No coordinate information found for channels .*", category=RuntimeWarning)
        warnings.filterwarnings("ignore", message="Channels contain different highpass filters.*", category=RuntimeWarning)
        warnings.filterwarnings("ignore", message="Channels contain different lowpass filters.*", category=RuntimeWarning)
        warnings.filterwarnings("ignore", message="Not setting positions of .* misc channels found in montage.*", category=RuntimeWarning)
        stim_raw = mne.io.read_raw_brainvision(stim_vhdr_path, preload=preload, verbose=verbose)
        baseline_raw = mne.io.read_raw_brainvision(baseline_vhdr_path, preload=preload, verbose=verbose)
    stim_type_map = {}
    base_type_map = {}
    if "stim" in stim_raw.ch_names:
        stim_type_map["stim"] = "stim"
    if "ground_truth" in stim_raw.ch_names:
        stim_type_map["ground_truth"] = "misc"
    if "stim" in baseline_raw.ch_names:
        base_type_map["stim"] = "stim"
    if "ground_truth" in baseline_raw.ch_names:
        base_type_map["ground_truth"] = "misc"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="The unit for channel\\(s\\) stim has changed from NA to V\\.", category=RuntimeWarning)
        if stim_type_map:
            stim_raw.set_channel_types(stim_type_map, verbose=verbose)
        if base_type_map:
            baseline_raw.set_channel_types(base_type_map, verbose=verbose)

    required_channels = ["stim", "ground_truth", reference_channel]
    missing_stim = [channel_name for channel_name in required_channels if channel_name not in stim_raw.ch_names]
    missing_base = [channel_name for channel_name in required_channels if channel_name not in baseline_raw.ch_names]
    if missing_stim:
        raise ValueError(f"Stim recording missing required channels: {missing_stim}")
    if missing_base:
        raise ValueError(f"Baseline recording missing required channels: {missing_base}")

    sampling_rate_hz = float(stim_raw.info["sfreq"])
    if float(baseline_raw.info["sfreq"]) != sampling_rate_hz:
        raise ValueError("Stim and baseline sampling rates do not match.")

    eeg_channel_names = [
        channel_name
        for channel_name in stim_raw.ch_names
        if channel_name not in {"stim", "ground_truth"} and not channel_name.upper().startswith("STI")
    ]
    if bad_channels_to_drop:
        eeg_channel_names = [channel_name for channel_name in eeg_channel_names if channel_name not in bad_channels_to_drop]
    if not eeg_channel_names:
        raise ValueError("No EEG channels remain after channel exclusion.")

    missing_eeg_in_baseline = [channel_name for channel_name in eeg_channel_names if channel_name not in baseline_raw.ch_names]
    if missing_eeg_in_baseline:
        raise ValueError(f"Baseline recording missing EEG channels required by stim recording: {missing_eeg_in_baseline}")

    # Shapes:
    # - stim_eeg / baseline_eeg: (n_eeg, n_times)
    # - stim_marker / ground_truth_* / *_reference: (n_times,)
    stim_eeg = stim_raw.copy().pick(eeg_channel_names).get_data()
    baseline_eeg = baseline_raw.copy().pick(eeg_channel_names).get_data()
    stim_idx = stim_raw.ch_names.index("stim")
    gt_stim_idx = stim_raw.ch_names.index("ground_truth")
    gt_base_idx = baseline_raw.ch_names.index("ground_truth")
    ref_stim_idx = stim_raw.ch_names.index(reference_channel)
    ref_base_idx = baseline_raw.ch_names.index(reference_channel)
    stim_marker = stim_raw.get_data(picks=[stim_idx])[0]
    ground_truth_stim = stim_raw.get_data(picks=[gt_stim_idx])[0]
    ground_truth_baseline = baseline_raw.get_data(picks=[gt_base_idx])[0]
    stim_reference = stim_raw.get_data(picks=[ref_stim_idx])[0]
    baseline_reference = baseline_raw.get_data(picks=[ref_base_idx])[0]

    if stim_eeg.shape[1] != stim_marker.shape[0]:
        raise ValueError("Stim EEG samples and stim marker length do not match.")
    if baseline_eeg.shape[1] != ground_truth_baseline.shape[0]:
        raise ValueError("Baseline EEG samples and baseline ground_truth length do not match.")

    return {
        "sampling_rate_hz": sampling_rate_hz,
        "stim_raw": stim_raw,
        "baseline_raw": baseline_raw,
        "stim_marker": stim_marker,
        "ground_truth_stim": ground_truth_stim,
        "ground_truth_baseline": ground_truth_baseline,
        "stim_eeg": stim_eeg,
        "baseline_eeg": baseline_eeg,
        "stim_reference": stim_reference,
        "baseline_reference": baseline_reference,
        "eeg_channel_names": eeg_channel_names,
        "reference_channel_name": reference_channel,
    }


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


def build_stim_masks(
    onsets_samples: np.ndarray,
    total_samples: int,
    sampling_rate_hz: float,
    on_window_s: tuple[float, float] = (0.0, 1.0),
    end_window_s: tuple[float, float] = (0.9, 1.05),
    off_exclusion_window_s: tuple[float, float] = (0.0, 1.05),
) -> dict[str, np.ndarray]:
    """Build stimulation masks aligned to full continuous signal length.

    Returns boolean vectors with shape: (n_times,)
    """
    if total_samples <= 0:
        raise ValueError("total_samples must be > 0.")

    mask_on = np.zeros(total_samples, dtype=bool)
    mask_end = np.zeros(total_samples, dtype=bool)
    mask_off = np.ones(total_samples, dtype=bool)

    for onset in np.asarray(onsets_samples, dtype=int):
        on_start = max(0, min(total_samples, int(onset + on_window_s[0] * sampling_rate_hz)))
        on_stop = max(0, min(total_samples, int(onset + on_window_s[1] * sampling_rate_hz)))
        end_start = max(0, min(total_samples, int(onset + end_window_s[0] * sampling_rate_hz)))
        end_stop = max(0, min(total_samples, int(onset + end_window_s[1] * sampling_rate_hz)))
        off_start = max(0, min(total_samples, int(onset + off_exclusion_window_s[0] * sampling_rate_hz)))
        off_stop = max(0, min(total_samples, int(onset + off_exclusion_window_s[1] * sampling_rate_hz)))

        mask_on[on_start:on_stop] = True
        mask_end[end_start:end_stop] = True
        mask_off[off_start:off_stop] = False

    return {"mask_on": mask_on, "mask_end": mask_end, "mask_off": mask_off}


def epoch_signal(
    signal_1d: np.ndarray,
    onsets_samples: np.ndarray,
    sampling_rate_hz: float,
    window_start_s: float,
    window_end_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Epoch a 1D signal around onsets using one generic window definition.

    Returns:
    - epochs: (n_epochs, n_window_samples)
    - time_axis_seconds: (n_window_samples,)
    - valid_onsets_samples: (n_epochs,)
    """
    signal_vector = np.asarray(signal_1d, dtype=float).ravel()
    start_offset = int(round(window_start_s * sampling_rate_hz))
    end_offset = int(round(window_end_s * sampling_rate_hz))
    if end_offset <= start_offset:
        raise ValueError("window_end_s must be greater than window_start_s.")

    valid_onsets = []
    for onset in np.asarray(onsets_samples, dtype=int):
        if onset + start_offset >= 0 and onset + end_offset <= signal_vector.size:
            valid_onsets.append(int(onset))
    valid_onsets_samples = np.asarray(valid_onsets, dtype=int)
    if valid_onsets_samples.size == 0:
        raise ValueError("No valid epochs for the requested window.")

    # epochs shape: (n_epochs, n_window_samples)
    epochs = np.stack(
        [signal_vector[onset + start_offset : onset + end_offset] for onset in valid_onsets_samples],
        axis=0,
    )
    time_axis_seconds = np.arange(start_offset, end_offset, dtype=float) / sampling_rate_hz
    return epochs, time_axis_seconds, valid_onsets_samples


def epoch_multichannel(
    signal_2d: np.ndarray,
    onsets_samples: np.ndarray,
    sampling_rate_hz: float,
    window_start_s: float,
    window_end_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Epoch multichannel data around onsets.

    Input:
    - signal_2d shape: (n_channels, n_times)

    Returns:
    - epochs shape: (n_epochs, n_channels, n_window_samples)
    - time_axis_seconds shape: (n_window_samples,)
    - valid_onsets_samples shape: (n_epochs,)
    """
    input_data = np.asarray(signal_2d, dtype=float)
    if input_data.ndim != 2:
        raise ValueError("signal_2d must have shape (n_channels, n_times).")

    start_offset = int(round(window_start_s * sampling_rate_hz))
    end_offset = int(round(window_end_s * sampling_rate_hz))
    if end_offset <= start_offset:
        raise ValueError("window_end_s must be greater than window_start_s.")

    n_times = input_data.shape[1]
    valid_onsets = []
    for onset in np.asarray(onsets_samples, dtype=int):
        if onset + start_offset >= 0 and onset + end_offset <= n_times:
            valid_onsets.append(int(onset))
    valid_onsets_samples = np.asarray(valid_onsets, dtype=int)
    if valid_onsets_samples.size == 0:
        raise ValueError("No valid multichannel epochs for requested window.")

    epochs = np.stack(
        [input_data[:, onset + start_offset : onset + end_offset] for onset in valid_onsets_samples],
        axis=0,
    )
    time_axis_seconds = np.arange(start_offset, end_offset, dtype=float) / sampling_rate_hz
    return epochs, time_axis_seconds, valid_onsets_samples


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


def demean_with_window(
    epoch_data: np.ndarray,
    time_axis_seconds: np.ndarray,
    demean_window_s: tuple[float, float] = (-0.70, -0.10),
) -> tuple[np.ndarray, np.ndarray]:
    """Demean epochs using only a selected clean time window."""
    input_epochs = np.asarray(epoch_data, dtype=float)
    input_time = np.asarray(time_axis_seconds, dtype=float).ravel()
    if input_epochs.shape[-1] != input_time.size:
        raise ValueError("Epoch sample axis and time_axis_seconds length must match.")

    demean_mask = (input_time >= demean_window_s[0]) & (input_time <= demean_window_s[1])
    if not np.any(demean_mask):
        raise ValueError("Demean window does not overlap epoch time axis.")

    if input_epochs.ndim == 2:
        working = input_epochs[:, np.newaxis, :]
        squeeze_output = True
    elif input_epochs.ndim == 3:
        working = input_epochs
        squeeze_output = False
    else:
        raise ValueError("epoch_data must be 2D or 3D.")

    window_mean = working[:, :, demean_mask].mean(axis=-1, keepdims=True)
    demeaned = working - window_mean
    if not np.all(np.isfinite(demeaned)):
        raise RuntimeError("Demeaning produced non-finite values.")
    if squeeze_output:
        return demeaned[:, 0, :], demean_mask
    return demeaned, demean_mask


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


def highpass_filter_epochs_iir_mne(
    epoch_data: np.ndarray,
    sampling_rate_hz: float,
    high_pass_hz: float,
    iir_order: int,
) -> np.ndarray:
    """Apply high-pass filtering to epochs without changing shape.

    Input:
    - epoch_data shape: (n_epochs, n_channels, n_samples) in Volts

    Returns:
    - filtered_epochs shape: (n_epochs, n_channels, n_samples) in Volts
    """
    import mne

    input_epochs = np.asarray(epoch_data, dtype=float)
    if input_epochs.ndim != 3:
        raise ValueError("epoch_data must have shape (n_epochs, n_channels, n_samples).")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")
    if high_pass_hz <= 0:
        raise ValueError("high_pass_hz must be > 0.")
    if iir_order < 1:
        raise ValueError("iir_order must be >= 1.")
    if input_epochs.shape[-1] < 2:
        raise ValueError("epoch_data must contain at least 2 samples.")

    channel_count = int(input_epochs.shape[1])
    info = mne.create_info(
        ch_names=[f"EEG{channel_index:03d}" for channel_index in range(channel_count)],
        sfreq=float(sampling_rate_hz),
        ch_types=["eeg"] * channel_count,
    )
    epochs_mne = mne.EpochsArray(input_epochs.copy(), info, tmin=0.0, baseline=None, verbose=False)
    epochs_mne.filter(
        l_freq=float(high_pass_hz),
        h_freq=None,
        method="iir",
        iir_params={"order": int(iir_order), "ftype": "butter"},
        verbose=False,
    )
    filtered_epochs = epochs_mne.get_data()
    if filtered_epochs.shape != input_epochs.shape:
        raise RuntimeError("High-pass filtering changed data shape unexpectedly.")
    if not np.all(np.isfinite(filtered_epochs)):
        raise RuntimeError("High-pass filtering produced non-finite values.")
    return filtered_epochs


def save_epoch_data_fif(
    epoch_data: np.ndarray,
    channel_names: list[str],
    sampling_rate_hz: float,
    tmin_s: float,
    output_path: str | Path,
) -> dict[str, float | int]:
    """Save 3D epoch data to FIF and return saved timing/shape details."""
    import mne

    input_epochs = np.asarray(epoch_data, dtype=float)
    if input_epochs.ndim != 3:
        raise ValueError("epoch_data must have shape (n_epochs, n_channels, n_samples).")
    if len(channel_names) != input_epochs.shape[1]:
        raise ValueError("channel_names length must match epoch_data channel axis.")
    if sampling_rate_hz <= 0:
        raise ValueError("sampling_rate_hz must be > 0.")

    info = mne.create_info(channel_names, float(sampling_rate_hz), ch_types=["eeg"] * len(channel_names))
    epochs = mne.EpochsArray(input_epochs, info, tmin=float(tmin_s), baseline=None, verbose=False)
    montage = mne.channels.make_standard_montage("standard_1020")
    epochs.set_montage(montage, on_missing="ignore", verbose=False)
    epochs.save(Path(output_path), overwrite=True, verbose=False)

    return {
        "n_epochs": int(input_epochs.shape[0]),
        "n_channels": int(input_epochs.shape[1]),
        "n_samples": int(input_epochs.shape[2]),
        "tmin_s": float(epochs.tmin),
        "tmax_s": float(epochs.tmax),
    }


def build_analysis_summary_lines(summary_items: dict[str, object]) -> list[str]:
    """Build deterministic summary lines from ordered key-value items."""
    summary_lines: list[str] = []
    for key, value in summary_items.items():
        if isinstance(value, float):
            summary_lines.append(f"{key}={value:.6f}")
        else:
            summary_lines.append(f"{key}={value}")
    return summary_lines


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


def make_baseline_pseudo_onsets(
    total_samples: int,
    sampling_rate_hz: float,
    spacing_s: float = 10.0,
    start_s: float = 2.0,
    stop_margin_s: float = 1.0,
    target_count: int | None = None,
) -> np.ndarray:
    """Create evenly spaced pseudo-onsets for baseline recordings."""
    if total_samples <= 0:
        raise ValueError("total_samples must be > 0.")
    if spacing_s <= 0:
        raise ValueError("spacing_s must be > 0.")

    start_sample = int(round(start_s * sampling_rate_hz))
    stop_sample = int(round(total_samples - stop_margin_s * sampling_rate_hz))
    step_samples = int(round(spacing_s * sampling_rate_hz))
    if stop_sample <= start_sample:
        raise ValueError("Baseline pseudo-onset bounds are invalid.")

    pseudo_onsets = np.arange(start_sample, stop_sample, step_samples, dtype=int)
    if pseudo_onsets.size == 0:
        raise ValueError("No baseline pseudo-onsets created.")

    if target_count is not None:
        if target_count <= 0:
            raise ValueError("target_count must be > 0.")
        if pseudo_onsets.size < target_count:
            raise ValueError("Not enough baseline pseudo-onsets for requested target_count.")
        pseudo_onsets = pseudo_onsets[:target_count]
    return pseudo_onsets


def run_ica_pass1_manual(
    epochs_mne: Any,
    n_components: float | int = 0.99,
    random_state: int = 42,
    method: str = "fastica",
) -> Any:
    """Fit ICA pass #1 and return ICA object for manual component selection."""
    import mne

    ica = mne.preprocessing.ICA(
        n_components=n_components,
        random_state=random_state,
        method=method,
        max_iter="auto",
    )
    ica.fit(epochs_mne, verbose=False)
    return ica


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


def compute_plv_phase(analytic_a: np.ndarray, analytic_b: np.ndarray) -> float:
    """Phase-locking value computed from two analytic (complex) signals."""
    phase_difference = np.angle(analytic_a) - np.angle(analytic_b)
    return float(np.abs(np.mean(np.exp(1j * phase_difference))))


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
                plv_values.append(
                    compute_plv_phase(
                        analytic_a=hilbert(eeg_band),
                        analytic_b=hilbert(gt_band),
                    )
                )
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


def classify_recovery_latency_ms(recovery_latency_ms: float) -> str:
    """Classify recovery latency for quick reporting."""
    if recovery_latency_ms <= 50.0:
        return "ideal"
    if recovery_latency_ms <= 150.0:
        return "acceptable"
    return "too_late"


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


def attach_scalar_to_metrics_rows(
    metrics_rows: list[dict[str, float | str]],
    field_name: str,
    scalar_value: float,
) -> list[dict[str, float | str]]:
    """Add one scalar field to every metrics row."""
    for row in metrics_rows:
        row[field_name] = float(scalar_value)
    return metrics_rows


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


def compute_snr10_db(signal_1d: np.ndarray, sampling_rate_hz: float) -> float:
    """10 Hz SNR estimate: signal band 9-11 Hz vs noise bands 3-8 and 12-22 Hz."""
    vector = np.asarray(signal_1d, dtype=float).ravel()
    frequencies_hz, psd_values = welch(vector, fs=sampling_rate_hz, nperseg=min(4096, vector.size))

    def _band_power(low_hz: float, high_hz: float) -> float:
        in_band = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
        return float(np.trapz(psd_values[in_band], frequencies_hz[in_band])) if np.any(in_band) else 0.0

    signal_power = _band_power(9.0, 11.0)
    noise_power = _band_power(3.0, 8.0) + _band_power(12.0, 22.0)
    return float(10.0 * np.log10((signal_power + 1e-30) / (noise_power + 1e-30)))


    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    raw_reference_signal = raw_stim.copy().pick([reference_channel]).get_data()[0]
    preprocessed_reference_signal = np.asarray(preprocessed_reference_signal, dtype=float).ravel()
    if raw_reference_signal.shape != preprocessed_reference_signal.shape:
        raise ValueError("Raw and preprocessed reference signals must have the same shape.")

    # Time-domain quick check: shape (n_times,) displayed for a short window.
    start_index = max(0, int(round(time_window_s[0] * sampling_rate_hz)))
    stop_index = min(raw_reference_signal.size, int(round(time_window_s[1] * sampling_rate_hz)))
    if stop_index <= start_index:
        raise ValueError("Invalid time window for quick-check plot.")
    time_seconds = np.arange(start_index, stop_index, dtype=float) / sampling_rate_hz

    time_figure_path = output_path / "quickcheck_time_raw_vs_preprocessed.png"
    fig_time, axis_time = plt.subplots(figsize=(13, 4), constrained_layout=True)
    axis_time.plot(time_seconds, raw_reference_signal[start_index:stop_index] * 1e6, lw=0.8, label="Raw reference")
    axis_time.plot(
        time_seconds,
        preprocessed_reference_signal[start_index:stop_index] * 1e6,
        lw=0.8,
        label="Preprocessed reference",
    )
    axis_time.set_title(f"Quick Check Time Domain ({reference_channel})")
    axis_time.set_xlabel("Time (s)")
    axis_time.set_ylabel("Amplitude (uV)")
    axis_time.grid(alpha=0.2)
    axis_time.legend(loc="upper right")
    fig_time.savefig(time_figure_path, dpi=200)
    plt.close(fig_time)

    # Spectral quick check: PSD raw vs preprocessed over full recording.
    raw_frequency_hz, raw_psd = welch(raw_reference_signal, fs=sampling_rate_hz, nperseg=min(4096, raw_reference_signal.size))
    preprocessed_frequency_hz, preprocessed_psd = welch(
        preprocessed_reference_signal, fs=sampling_rate_hz, nperseg=min(4096, preprocessed_reference_signal.size)
    )
    psd_figure_path = output_path / "quickcheck_psd_raw_vs_preprocessed.png"
    fig_psd, axis_psd = plt.subplots(figsize=(10, 4), constrained_layout=True)
    axis_psd.semilogy(raw_frequency_hz, raw_psd, label="Raw reference")
    axis_psd.semilogy(preprocessed_frequency_hz, preprocessed_psd, label="Preprocessed reference")
    axis_psd.set_xlim(0.0, 45.0)
    axis_psd.set_xlabel("Frequency (Hz)")
    axis_psd.set_ylabel("PSD")
    axis_psd.set_title(f"Quick Check PSD ({reference_channel})")
    axis_psd.grid(alpha=0.2)
    axis_psd.legend(loc="upper right")
    fig_psd.savefig(psd_figure_path, dpi=200)
    plt.close(fig_psd)

    return {"time_plot_path": str(time_figure_path), "psd_plot_path": str(psd_figure_path)}


def plot_timecourse_raw_hpf_ica(
    raw_eeg: Any,
    raw_hpf: Any,
    raw_ica: Any,
    sampling_rate_hz: float,
    channel_name: str,
    channel_index: int,
    t0_seconds: float,
    t1_seconds: float,
    output_path: str | Path,
) -> None:
    """QC plot: continuous raw vs HPF vs ICA-clean for one channel."""
    n_times = int(raw_eeg.n_times)
    i0 = max(0, int(round(t0_seconds * sampling_rate_hz)))
    i1 = min(n_times, int(round(t1_seconds * sampling_rate_hz)))
    if i1 <= i0:
        raise ValueError(f"Invalid time window: {(t0_seconds, t1_seconds)} s")

    time_seconds = np.arange(i0, i1, dtype=float) / sampling_rate_hz

    fig, axis = plt.subplots(figsize=(12, 4), constrained_layout=True)
    axis.plot(time_seconds, raw_eeg.get_data()[channel_index, i0:i1] * 1e6, lw=0.8, alpha=0.8, label="Raw")
    axis.plot(time_seconds, raw_hpf.get_data()[channel_index, i0:i1] * 1e6, lw=1.0, label="HPF")
    axis.plot(time_seconds, raw_ica.get_data()[channel_index, i0:i1] * 1e6, lw=1.1, label="ICA-clean")
    axis.set_title(f"{channel_name}: raw vs HPF vs ICA ({t0_seconds:.0f}-{t1_seconds:.0f} s)")
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Amplitude (uV)")
    axis.grid(alpha=0.2)
    axis.legend(loc="upper right")
    fig.savefig(Path(output_path), dpi=220)
    plt.show()


def plot_epoch_step_subplots(
    step_epoch_data: dict[str, np.ndarray],
    step_time_axes_seconds: dict[str, np.ndarray],
    channel_index: int,
    channel_name: str,
    output_path: str | Path,
) -> None:
    """Plot one subplot per processing step (independent x/y scaling)."""
    step_names = list(step_epoch_data.keys())
    if not step_names:
        raise ValueError("step_epoch_data is empty.")
    fig, axes = plt.subplots(len(step_names), 1, figsize=(12, 2.4 * len(step_names)), constrained_layout=True)
    axes = np.atleast_1d(axes)
    for axis, step_name in zip(axes, step_names):
        step_data = np.asarray(step_epoch_data[step_name], dtype=float)
        step_time = np.asarray(step_time_axes_seconds[step_name], dtype=float).ravel()
        if step_data.ndim != 3 or step_data.shape[-1] != step_time.size:
            raise ValueError(f"Invalid shape/time axis for step '{step_name}'.")
        step_trace_uv = step_data[:, channel_index, :].mean(axis=0) * 1e6
        axis.plot(step_time, step_trace_uv, lw=1.0, color="steelblue")
        axis.set_title(f"{step_name} ({channel_name})")
        axis.set_xlabel("Time (s)")
        axis.set_ylabel("uV")
        axis.grid(alpha=0.2)
    fig.savefig(Path(output_path), dpi=220)
    plt.show()
