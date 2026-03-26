# TIMS — Dose-Response EEG/TEP Pipeline

Transcranial magnetic stimulation (TMS) with integrated EEG: phantom pilot data (exp03, 10 Hz stim, 1 000 Hz sampling, ground-truth channel).

---

## Workspace Layout

```
Root
├── main_analysis_exp03.py          Foundation pipeline (steps 1–4)
├── postclean_denoise_validate_exp03.py  ICA / SSP / SOUND branch comparison
├── ica_qc_exp03.py                 ICA component diagnostics
├── compare_stim_baseline_exp03.py  Stim vs baseline (temporal + PSD + ITPC)
├── final_postpulse_fixed_channels_exp03.py  Fixed-channel post-pulse epoching
├── find_best_channels_exp03.py     Channel ranking utility
├── plot_exp03_timecourse_mne.py    Visualisation: ERP time course
├── plot_stim_10_30s.py             Visualisation: raw stim segments
├── preprocessing.py                Core functions (16 kept, complex logic only)
├── plot_helpers.py                 Visualisation functions (18 functions)
├── environment/                    Conda environment YMLs
├── exp03_pulse_centered_analysis_run03/   Main pipeline outputs
├── exp03_postpulse_fixed_channels/        Fixed-channels outputs
├── evidence/            A/B/C pipeline comparisons & failure evidence
├── old/                 Archived scripts (exp02, Experiment_1, learning)
├── simulation/          SimNIBS coil models, head models
├── hardware/            Stimulation parameter GUI
├── TIMS_data_sync/      Raw BrainVision recordings
└── tims-main/           Repository clone
```

---

## Pipeline Recipes (copy-paste inline code)

These are the transparent building blocks. Steps 1–4 are meant to be **visible inline code** in your scripts, not hidden behind function calls.

### Step 1 — Load & Channel Selection

```python
import mne, numpy as np
from pathlib import Path

raw = mne.io.read_raw_brainvision(str(vhdr_path), preload=True, verbose=False)
sfreq = float(raw.info["sfreq"])

# Identify special channels by name
stim_marker = raw.copy().pick(["stim"]).get_data()[0]
ground_truth = raw.copy().pick(["ground_truth"]).get_data()[0]

# Pick EEG channels (exclude stim/ground_truth)
eeg_channels = [ch for ch in raw.ch_names if ch not in {"stim", "ground_truth"}]
raw_eeg = raw.copy().pick(eeg_channels)
```

Optional: use `pick_good_eeg_channels_from_baseline()` from preprocessing.py to reject flat channels against a baseline recording.

### Step 2 — Pulse Detection

**Option A — Robust (from stim channel):**
```python
from preprocessing import detect_stim_onsets
onsets_samples, median_ioi_s, _, _ = detect_stim_onsets(stim_marker, sfreq)
```

**Option B — Simple (from EEG channel):**
```python
from scipy.signal import hilbert, find_peaks
envelope = np.abs(hilbert(eeg_channel_data))
min_distance = int(0.08 * sfreq)  # 80 ms refractory
peaks, _ = find_peaks(envelope, height=np.median(envelope) * 5, distance=min_distance)
```

**Timing shifts:** `onsets_shifted = onsets + int(shift_ms / 1000 * sfreq)`

### Step 3a — Pseudo-Onsets (for baseline recording)

```python
spacing_samples = int(spacing_s * sfreq)
pseudo_onsets = np.arange(start_sample, total_samples - margin, spacing_samples)
```

### Step 3b — Epoching

**Single channel:**
```python
i0, i1 = int(win_start_s * sfreq), int(win_end_s * sfreq)
n_samples = i1 - i0
epochs = np.array([signal[onset + i0 : onset + i0 + n_samples]
                    for onset in onsets
                    if onset + i0 >= 0 and onset + i0 + n_samples <= len(signal)])
time_axis = np.arange(n_samples) / sfreq + win_start_s
```

**Multi-channel (using MNE Epochs):**
```python
events = np.c_[onsets, np.zeros_like(onsets), np.ones_like(onsets)].astype(int)
epochs_mne = mne.Epochs(raw_eeg, events, event_id=1,
                        tmin=win_start_s, tmax=win_end_s,
                        baseline=None, preload=True, verbose=False)
```

### Step 4 — Artifact Removal (Approach A: dual-center blockzero + crop)

This is the working approach. Each line is visible and auditable:

```python
times = epochs_mne.times
data = epochs_mne.get_data(copy=True)  # (n_epochs, n_channels, n_samples) in Volts

# Masks
artifact_mask = (times >= -1.000) & (times <= 0.030)
pre_center = (times >= -1.25) & (times <= -1.05)
post_center = (times >= 0.05) & (times <= 0.30)
pre_seg = times < -1.000
post_seg = times > 0.030

# Dual-center demean + blockzero
data[:, :, pre_seg]  -= data[:, :, pre_center].mean(axis=-1, keepdims=True)
data[:, :, post_seg] -= data[:, :, post_center].mean(axis=-1, keepdims=True)
data[:, :, artifact_mask] = 0.0

# Wrap back into MNE
epochs_clean = mne.EpochsArray(data, epochs_mne.info.copy(),
                                tmin=float(times[0]), baseline=None, verbose=False)

# Crop to post-pulse window + highpass
epochs_final = epochs_clean.copy().crop(tmin=0.08, tmax=1.00)
epochs_final.filter(l_freq=0.5, h_freq=None, method="iir",
                    iir_params={"order": 4, "ftype": "butter"}, verbose=False)
```

Alternative: `remove_and_interpolate_pulse_window()` for interpolation-based approaches, or `replace_block_with_zero_after_dual_center()` when you need the centering metadata dict.

### Step 5 — Saving

```python
epochs_final.save(output_path, overwrite=True, verbose=False)
```

---

## Analysis Branches (Step 5+)

These use functions from `preprocessing.py` and `plot_helpers.py` — genuinely complex logic.

| Branch | Script | Key Functions |
|--------|--------|---------------|
| **TEP waveforms** | `main_analysis_exp03.py` | MNE `.average().plot()` |
| **Spectral power** | `compare_stim_baseline_exp03.py` | `compute_snr10_db()` |
| **PLV / ITPC** | `compare_stim_baseline_exp03.py`, `plot_helpers.py` | `plv_itpc()`, `plot_plv()`, `plot_itpc()` |
| **Coherence** | `postclean_denoise_validate_exp03.py` | `compute_coherence_band()` |
| **Artifact QC** | `main_analysis_exp03.py` | `compute_derivative_metric()`, `find_return_to_baseline_time()` |
| **Recovery metrics** | `main_analysis_exp03.py` | `compute_stage_ground_truth_metrics()`, `compute_recovery_latency_from_stage()` |
| **Denoising comparison** | `postclean_denoise_validate_exp03.py` | ICA / SSP / SOUND branches |
| **ICA diagnostics** | `ica_qc_exp03.py` | `mne.preprocessing.ICA` inline |
| **Channel ranking** | `find_best_channels_exp03.py` | `compute_window_bias_per_channel()` |
| **Dose-response** | *(future)* | TEP amplitude × intensity, power × intensity |

### Inline PLV (one-liner)

```python
from scipy.signal import hilbert
phase_diff = np.angle(hilbert(signal_a)) - np.angle(hilbert(signal_b))
plv = float(np.abs(np.mean(np.exp(1j * phase_diff))))
```

---

## Functions in `preprocessing.py` (16 kept)

| Function | Lines | Purpose |
|----------|-------|---------|
| `filter_signal` | ~28 | Butterworth bandpass/lowpass/highpass via sosfiltfilt |
| `pick_good_eeg_channels_from_baseline` | ~54 | Reject flat channels from baseline recording |
| `detect_stim_onsets` | ~89 | Multi-stage adaptive peak detection on stim channel |
| `remove_and_interpolate_pulse_window` | ~50 | Replace pulse window with cubic interpolation |
| `crop_epochs_time_window` | ~57 | Crop epoch array to time window, return new time axis |
| `replace_block_with_zero_after_dual_center` | ~36 | Dual-center demean + blockzero (returns centering metadata) |
| `compute_derivative_metric` | ~36 | Gradient magnitude aggregation per epoch |
| `find_return_to_baseline_time` | ~57 | Find time when signal returns to baseline envelope |
| `compute_window_bias_per_channel` | ~38 | Per-channel median bias in a time window |
| `compute_coherence_band` | ~21 | scipy.signal.coherence + band extraction |
| `compute_stage_ground_truth_metrics` | ~67 | Full metrics row: coherence, PLV, correlation, bias, SNR |
| `did_ground_truth_recover` | ~20 | Check metric thresholds across multiple fields |
| `build_stage_overlay_inputs_uv` | ~23 | Extract + scale EEG/GT traces for overlay plots |
| `compute_recovery_latency_from_stage` | ~34 | Derivative + baseline search for recovery timing |
| `save_metrics_rows_csv` | ~15 | Write list[dict] → CSV |
| `compute_snr10_db` | ~18 | Signal band vs total power via Welch PSD |

---

## Data Conventions

- **Input format:** BrainVision `.vhdr` (+ `.eeg` / `.vmrk`)
- **Units:** Process in Volts; multiply by `1e6` only for plots/display (µV)
- **Epoch shapes:** `(n_epochs, n_samples)` for single-channel, `(n_epochs, n_channels, n_samples)` for multi-channel
- **Sampling rate:** Always stored as `sfreq = float(raw.info["sfreq"])` in Hz
