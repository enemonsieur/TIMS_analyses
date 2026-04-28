---
name: EXP08 Analysis API Reference
type: reference
status: active
last_updated: 2026-04-23
---

# EXP08 Analysis API Reference

Quick lookup guide for datasets, functions, and variables available in EXP08 analyses.

---

## 1. Available Epoch Files

All epoch files are located in `EXP08/` directory and follow the naming convention:
`exp08_{data_type}_epochs_{intensity}pct_{window}-epo.fif`

### 1.1 EEG Epochs (28 channels)

| File Pattern | Description | Window | Samples | N Epochs |
|---|---|---|---|---|
| `exp08_epochs_*pct_on-epo.fif` | Raw EEG during stimulus | -0.5 to +1.0 s | 1501 | 20 per intensity |
| `exp08_epochs_*pct_lateoff-epo.fif` | Raw EEG, post-stimulus (noise ref) | 1.5 to 3.2 s | 1701 | 20 per intensity |

**Available intensities:** 10%, 20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%, 100%

**Channel names:** `['F3', 'F7', 'FT9', 'FC5', 'FC1', 'C3', 'T7', 'CP5', 'CP1', 'Pz', 'P3', 'P7', 'O1', 'Oz', 'O2', 'P4', 'P8', 'CP6', 'CP2', 'Cz', 'C4', 'T8', 'FT10', 'FC6', 'FC2', 'F4', 'F8', 'Fp2']`

### 1.2 Ground-Truth Epochs (1 channel: GT reference signal)

| File Pattern | Description | Window | Samples | N Epochs |
|---|---|---|---|---|
| `exp08_gt_epochs_*pct_on-epo.fif` | GT signal during stimulus | -0.5 to +1.0 s | 1501 | 20 per intensity |
| `exp08_gt_epochs_*pct_lateoff-epo.fif` | GT signal, post-stimulus | 1.5 to 3.2 s | 1701 | 20 per intensity |

**Channel name:** `['ground_truth']`

### 1.3 Stimulus Epochs (1 channel: stimulus trace)

| File Pattern | Description | Window | Samples | N Epochs |
|---|---|---|---|---|
| `exp08_stim_epochs_*pct_on-epo.fif` | Stimulus voltage during pulse | -0.5 to +1.0 s | 1501 | 20 per intensity |
| `exp08_stim_epochs_*pct_lateoff-epo.fif` | Stimulus voltage, post-pulse | 1.5 to 3.2 s | 1701 | 20 per intensity |

**Channel name:** `['stim']`

**Usage:** Negative control (stimulus should NOT lock-in with GT signal at signal frequencies)

### 1.4 Time Window Definitions

| Window | Pulse Onset | Duration | Samples @ 1kHz | Purpose |
|---|---|---|---|---|
| **ON** | t = 0 | -0.5 to +1.0 s | 1501 | Full stimulus response (pre-post) |
| **ITPC/PLV** | t = 0 | -0.2 to +0.3 s | 501 | Phase-locking analysis (cropped from ON) |
| **late-OFF** | t = 1.5–3.2 s | 1.5 to 3.2 s post-pulse | 1701 | Artifact-free noise reference |

---

## 2. Key Functions from Imported Modules

### 2.1 From `preprocessing` Module

```python
import preprocessing
```

#### SNR Computation
```python
snr = preprocessing.compute_snr_linear(
    data,                    # (n_epochs, n_samples)
    sfreq,                   # sampling rate (Hz)
    signal_band_hz,          # tuple (f_low, f_high)
    view_band_hz             # tuple (f_low, f_high)
)
# Returns: float, linear SNR (signal power / view band power)
```

#### ITPC Timecourse
```python
itpc_curve = preprocessing.compute_itpc_timecourse(
    signal,                  # (n_epochs, n_samples)
    reference,               # (n_epochs, n_samples)
    sfreq,                   # sampling rate (Hz)
    signal_band_hz           # tuple (f_low, f_high)
)
# Returns: (n_samples,) array, ITPC per time point
```

#### Phase-Locking Value (PLV)
```python
plv_metrics = preprocessing.compute_epoch_plv_summary(
    signal,                  # (n_epochs, n_samples)
    reference,               # (n_epochs, n_samples)
    sfreq,                   # sampling rate (Hz)
    signal_band_hz,          # tuple (f_low, f_high)
    target_peak_hz           # peak frequency (Hz)
)
# Returns: dict with keys:
#   'plv': float (0–1, phase locking strength)
#   'phase_samples': (n_epochs,) array (phase angles)
#   'p_value': float (statistical significance)
```

#### Signal Filtering
```python
filtered = preprocessing.filter_signal(
    data,                    # (n_channels, n_samples) or (n_epochs, n_channels, n_samples)
    sfreq,                   # sampling rate (Hz)
    f_low,                   # low cutoff (Hz)
    f_high                   # high cutoff (Hz)
)
# Returns: same shape as input, IIR-filtered
```

#### Event Array Construction
```python
events = preprocessing.build_event_array(event_samples)
# event_samples: (n_events,) array of sample indices
# Returns: (n_events, 3) array compatible with MNE Epochs
```

### 2.2 From `sass` Module

```python
import sass
```

#### SASS (Spatial Artifact Suppression via Subtraction)
```python
cleaned = sass.sass(
    data,                    # (n_channels, n_samples) concatenated
    cov_signal,              # (n_channels, n_channels) covariance with artifact
    cov_noise                # (n_channels, n_channels) covariance without artifact
)
# Returns: (n_channels, n_samples) cleaned data
# Method: data − scaling_factor × (cov_signal^{-1} @ cov_noise @ data)
```

### 2.3 From `plot_helpers` Module

```python
import plot_helpers
```

#### Phase Histogram Grid
```python
plot_helpers.save_phase_histogram_grid(
    phase_grid_rows,         # list of lists of dicts (see structure below)
    output_path,             # Path object
    title,                   # figure title
    n_columns                # number of columns in grid
)
# phase_grid_rows structure:
# [
#   [
#     {"title": str, "phases": array, "plv": float, "p_value": float, "color": str},
#     ...
#   ]
# ]
```

#### PLV Method Summary Figure
```python
plot_helpers.save_plv_method_summary_figure(
    x_values,                # (n_intensities,) intensity percentages
    event_counts,            # (n_intensities,) number of epochs per intensity
    method_series,           # list of dicts (see structure below)
    output_path,             # Path object
    title                    # figure title
)
# method_series structure:
# [
#   {"label": str, "values": array, "color": str, "linewidth": float},
#   ...
# ]
```

---

## 3. Key Configuration Variables

### 3.1 Frequency Bands

| Variable | Range | Purpose |
|---|---|---|
| **Signal band** | 12.5–13.5 Hz | Ground-truth signal frequency band (0.5 Hz width centered at 13 Hz) |
| **View band** | 4–20 Hz | Broadband reference for SNR/SSD baseline |

**Usage:** Always use these bands consistently across analyses. Signal band is for computing SNR and ITPC; view band is for covariance baseline.

### 3.2 Intensity Levels

```python
INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]
```

**Usage:** Always iterate over these in order. Use labels for figure titles/legends; use pct values (10, 20, ..., 100) to construct filenames.

### 3.3 SSD Configuration

```python
N_SSD_COMPONENTS = 6  # number of components to extract via eigendecomposition
```

**Usage:** Higher components are ranked by SNR; typically select top 1–3.

---

## 4. Common Analysis Patterns

### 4.1 Load All Epochs for One Analysis

```python
from pathlib import Path
import mne
import numpy as np

EPOCH_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]

epochs_on_all = {}
epochs_lateoff_all = {}
gt_on_all = {}

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)
    
    epochs_on_path = EPOCH_DIR / f"exp08_epochs_{intensity_pct}pct_on-epo.fif"
    epochs_on = mne.read_epochs(str(epochs_on_path), preload=True, verbose=False)
    epochs_on_all[intensity_pct] = epochs_on
    
    epochs_lateoff_path = EPOCH_DIR / f"exp08_epochs_{intensity_pct}pct_lateoff-epo.fif"
    epochs_lateoff = mne.read_epochs(str(epochs_lateoff_path), preload=True, verbose=False)
    epochs_lateoff_all[intensity_pct] = epochs_lateoff
    
    gt_on_path = EPOCH_DIR / f"exp08_gt_epochs_{intensity_pct}pct_on-epo.fif"
    gt_on = mne.read_epochs(str(gt_on_path), preload=True, verbose=False)
    gt_on_all[intensity_pct] = gt_on

sfreq = float(epochs_on.info["sfreq"])  # 1000 Hz
```

### 4.2 Crop Epochs to Shorter Window (e.g., ITPC analysis)

```python
ITPC_WINDOW_S = (-0.2, 0.3)

# Crop stimulus epochs to match EEG window
stim_epochs.crop(tmin=ITPC_WINDOW_S[0], tmax=ITPC_WINDOW_S[1])

# Or crop during loading
epochs_cropped = epochs_on.copy().crop(tmin=ITPC_WINDOW_S[0], tmax=ITPC_WINDOW_S[1])
```

### 4.3 Extract Data from Epochs

```python
# All epochs, all channels, all samples → (n_epochs, n_channels, n_samples)
data = epochs_on.get_data()

# Single channel
data_single_ch = epochs_on.get_data()[:, ch_idx, :]  # (n_epochs, n_samples)

# Specific channels by name
data_subset = epochs_on.copy().pick(["Cz", "C3", "C4"]).get_data()
```

### 4.4 Compute Covariance Matrices (for SASS/SSD)

```python
# Concatenate all epochs into (n_channels, n_total_samples)
n_epochs, n_channels, n_samples = on_data.shape
on_concat = on_data.transpose(1, 0, 2).reshape(n_channels, -1)

# Compute covariance
cov = np.cov(on_concat)  # (n_channels, n_channels)
```

### 4.5 Rank Channels/Components by SNR

```python
best_snr = -np.inf
best_ch = None
best_data = None

for ch_idx, ch_name in enumerate(channel_names):
    ch_data = data[:, ch_idx, :]
    snr = preprocessing.compute_snr_linear(ch_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
    
    if snr > best_snr:
        best_snr = snr
        best_ch = ch_name
        best_data = ch_data
```

### 4.6 Apply SSD (Eigendecomposition)

```python
from scipy import linalg

# Flatten epochs for covariance
on_data_flat = on_data.transpose(1, 0, 2).reshape(n_channels, -1)

# Filter to signal and view bands
on_signal = preprocessing.filter_signal(on_data_flat, sfreq, 12.5, 13.5)
on_view = preprocessing.filter_signal(on_data_flat, sfreq, 4.0, 20.0)

# Covariances
cov_signal = np.cov(on_signal)
cov_view = np.cov(on_view)

# Eigendecompose
evals, evecs = linalg.eig(cov_signal, cov_view)
idx = np.argsort(np.real(evals))[::-1]
W = evecs[:, idx].T[:N_SSD_COMPONENTS]  # (N_SSD_COMPONENTS, n_channels)

# Apply to data
components = W @ on_data_flat  # (N_SSD_COMPONENTS, n_samples_total)
```

---

## 5. Validation & Analysis Checklist

When analyzing EXP08 data:

- [ ] **Load correct window:** Use ON for stimulus response, late-OFF for noise baseline
- [ ] **Frequency band:** Always use 12.5–13.5 Hz signal band with 4–20 Hz view band
- [ ] **Data shape:** Verify (n_epochs=20, n_channels, n_samples) after loading
- [ ] **Sampling rate:** Confirm 1000 Hz throughout
- [ ] **GT signal:** Use as reference; GT vs. stim should show LOW phase-locking (negative control)
- [ ] **Channel consistency:** Use same channel/component across all intensities for ranking curves
- [ ] **SNR metric:** Linear ratio (signal power / view band power), not dB
- [ ] **ITPC range:** Expect 0–1; mean ITPC >0.8 indicates strong phase-locking to GT

---

## 6. Output Naming Convention

When saving new analyses, follow this pattern:

```
exp08_{analysis}_{descriptor}_{optional_intensity}.png
exp08_{analysis}_summary.txt
```

**Examples:**
- `exp08_timecourse_100pct_overlay.png` (timecourse at 100% intensity)
- `exp08_art_filtering_itpc_summary.png` (ITPC comparison across methods)
- `exp08_dose_response_snr.png` (SNR vs. intensity)
- `exp08_my_analysis_summary.txt` (analysis report)

---

## 7. Reference Scripts

| Script | Purpose | Key Outputs |
|---|---|---|
| `explore_exp08_pulses.py` | Extract epochs from raw data | `exp08_*_epochs_*pct_*.fif` (all epoch files) |
| `explore_exp08_art_filtering.py` | Compare Raw/SASS/SSD spatial filters | ITPC/PLV timecourse, phase grids, SNR curves |
| `explore_exp08_timecourse_100pct.py` | Visualize mean timecourse @ 100% | 5-channel overlay with stimulus |
| `explore_exp08_dose_response_curve.py` | SNR vs. intensity | Dose-response curve |
| `explore_exp08_on_state_by_intensity.py` | Channel ranking per intensity | Best channels for each method |
| `explore_exp08_psd_by_method.py` | Power spectral density comparison | PSD per method vs. intensity |

---

## 8. Quick Start: New Analysis Template

```python
"""Brief description of analysis."""

from pathlib import Path
import mne
import numpy as np
import preprocessing

# ============================================================
# CONFIG
# ============================================================

EPOCH_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIR = EPOCH_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]

SIGNAL_BAND_HZ = (12.5, 13.5)
VIEW_BAND_HZ = (4.0, 20.0)

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
# [Copy from script docstring or reference above]

# ============================================================
# LOAD & ANALYZE
# ============================================================

results_by_intensity = []
for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)
    
    # Load
    epochs_path = EPOCH_DIR / f"exp08_epochs_{intensity_pct}pct_on-epo.fif"
    epochs = mne.read_epochs(str(epochs_path), preload=True, verbose=False)
    sfreq = float(epochs.info["sfreq"])
    
    # Analyze
    data = epochs.get_data()  # (20, 28, 1501)
    
    # ... your analysis ...
    
    results_by_intensity.append(...)

# ============================================================
# SAVE & REPORT
# ============================================================

# Save figure, manifest, etc.
```

---

## Notes

- All epochs extracted @ 1000 Hz with 20 trials per intensity
- Ground-truth frequency is 13 Hz (updated from 12 Hz in earlier experiments)
- Stimulus epochs are provided as negative control (should NOT correlate with GT at signal band)
- ITPC window (-0.2 to +0.3 s) is a subset of ON window (-0.5 to +1.0 s); crop when needed
