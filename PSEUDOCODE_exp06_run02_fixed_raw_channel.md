# Pseudocode: New Script to Find Fixed Raw Channel at 10%

## Script Name
`explore_exp06_best_raw_channel_fixed.py`

## Purpose
Find the single best raw EEG channel at 10% intensity (based on PLV to GT) and output its metadata so that `analyze_exp06_run02_on_raw_sass_ssd_plv.py` can reuse it at all other intensities (20%, 30%, 40%, 50%).

---

## High-Level Pseudocode

### 1) LOAD DATA
```
Load run02 recording (exp06-STIM-iTBS_run02.vhdr)
Extract:
    - raw_eeg (multichannel, after excluding stim, GT, excluded channels)
    - gt_trace (ground-truth 12.45 Hz reference)
    - stim_trace (stimulus timing)
sfreq = sampling frequency
```

### 2) DETECT STIMULUS BLOCKS
```
Call preprocessing.detect_stim_blocks(stim_trace, sfreq, threshold=0.08)
    → block_onsets_samples, block_offsets_samples (all 100 blocks)

Extract 10% intensity block indices:
    block_indices_10pct = 0:20  (first 20 ON cycles = 10% intensity)
```

### 3) EXTRACT 10% ON WINDOWS
```
FOR each block in 10% intensity (block_indices 0–19):
    on_start = block_onset + 0.3 s (shift into interior)
    on_end = block_onset + 1.5 s
    
    Extract:
        on_raw_epochs[cycle_idx] = raw_eeg[:, on_start:on_end]
        on_gt_epochs[cycle_idx] = gt_trace[on_start:on_end]

Result:
    on_raw_epochs: (20 cycles, n_channels, on_window_samples)
    on_gt_epochs: (20 cycles, on_window_samples)
```

### 4) COMPUTE PLV FOR EACH CHANNEL AT 10%
```
FOR each raw EEG channel:
    ch_data = on_raw_epochs[:, ch_idx, :]  # (20 cycles, samples)
    
    Call preprocessing.compute_epoch_plv_summary(
        ch_data,
        on_gt_epochs,
        sfreq,
        SIGNAL_BAND_HZ = (11.95, 12.95),
        TARGET_CENTER_HZ = 12.451172
    )
    → metrics = {plv, p_value, mean_gt_locking, phase_samples}
    
    Compute peak frequency via PSD:
        ch_signal = bandpass(ch_data, 4–20 Hz, sfreq)
        ch_psd = mean(|FFT(ch_signal)|^2, axis=0)
        ch_peak_hz = frequency of max PSD bin
    
    Store: channel_plv_info[ch_name] = {
        plv,
        p_value,
        mean_gt_locking,
        phase_samples,
        peak_hz
    }
```

### 5) SELECT BEST CHANNEL AT 10%
```
best_ch = argmax(plv) across all channels
best_ch_info = channel_plv_info[best_ch]

Output:
    REFERENCE_RAW_CHANNEL = best_ch
    REFERENCE_PLV_AT_10PCT = best_ch_info.plv
    REFERENCE_PEAK_HZ = best_ch_info.peak_hz
```

### 6) EXTRACT AND VISUALIZE BEST CHANNEL ACROSS ALL INTENSITIES
```
FOR each intensity block (10%, 20%, ..., 50%):
    FOR each ON cycle in that intensity:
        Extract timecourse of REFERENCE_RAW_CHANNEL at that cycle
        Extract GT timecourse at that cycle
        Bandpass both to signal band
        
    Concatenate all cycles for that intensity
        → intensity_ch_timecourse, intensity_gt_timecourse

Plot 5-panel figure (one per intensity):
    Panel i:
        x-axis: time (0 to ~24 s for 20 concatenated 1.2 s cycles)
        y-axis: amplitude (µV)
        
        Plot GT in black (thick, reference)
        Plot REFERENCE_RAW_CHANNEL in intensity color (thin)
        Title: "{intensity}: {REFERENCE_RAW_CHANNEL} vs GT"
        Legend: show PLV from that intensity
```

### 7) COMPUTE PLV FOR BEST CHANNEL AT ALL INTENSITIES
```
FOR each intensity:
    on_raw_epochs[intensity] = extract ON windows for this intensity
    on_gt_epochs[intensity] = extract GT windows for this intensity
    
    ch_idx = index of REFERENCE_RAW_CHANNEL
    ch_data = on_raw_epochs[intensity][:, ch_idx, :]
    
    Call preprocessing.compute_epoch_plv_summary(...)
        → intensity_plv_info[intensity]
    
    Compute peak frequency:
        → intensity_peak_hz[intensity]
```

### 8) EXPORT METADATA TABLE
```
Create table:
    Intensity | Channel | PLV@10% | PLV@Intensity | Peak Hz | Cycles | Notes
    ----------|---------|---------|---------------|---------|--------|-------
    10%       | BEST_CH | 0.xxxx  | 0.xxxx        | 12.45   | 20     | Reference
    20%       | BEST_CH | 0.xxxx  | 0.yyyy        | 12.50   | 20     | Fixed
    30%       | BEST_CH | 0.xxxx  | 0.zzzz        | 12.48   | 20     | Fixed
    40%       | BEST_CH | 0.xxxx  | 0.wwww        | 12.20   | 20     | Fixed
    50%       | BEST_CH | 0.xxxx  | 0.vvvv        | 12.15   | 20     | Fixed

Save to:
    exp06_run02_fixed_raw_channel_metadata.txt
    
Report:
    - REFERENCE_RAW_CHANNEL = {best_ch}
    - PLV@10% = {best_plv}
    - Peak Hz@10% = {peak_hz}
    - Expected trend: PLV decreases with intensity
```

### 9) EXPORT FIXED CHANNEL REFERENCE FOR DOWNSTREAM USE
```
Save to JSON or pickle:
    {
        "reference_channel_name": "BEST_CH",
        "reference_channel_index": 5,  # (e.g., channel index in raw_eeg)
        "reference_intensity": "10%",
        "reference_plv": 0.xxxx,
        "reference_peak_hz": 12.451,
        "plv_per_intensity": {
            "10%": 0.xxxx,
            "20%": 0.yyyy,
            "30%": 0.zzzz,
            "40%": 0.wwww,
            "50%": 0.vvvv
        },
        "peak_hz_per_intensity": {
            "10%": 12.451,
            "20%": 12.500,
            ...
        }
    }
    
This will be loaded by analyze_exp06_run02_on_raw_sass_ssd_plv.py
to enforce use of the same channel across all intensities.
```

---

## Key Differences from `explore_exp06_best_raw_channel_sync.py`

| Aspect | Old Script | New Script |
|--------|-----------|-----------|
| **Metric** | ITPC (raw Hilbert phase diff) | PLV (preprocessed bandpass, statistical) |
| **Selection** | Best channel per intensity | Best channel at 10% ONLY |
| **Output** | Visualization + summary table | Metadata JSON + visualization + table |
| **Usage** | Exploratory / QC | Input to main analysis script |
| **Per-intensity PLV** | Not computed | Computed for all intensities |

---

## Output Files

1. **`exp06_run02_fixed_raw_channel_metadata.json`**
   - Machine-readable reference for downstream scripts
   - Contains channel name, indices, PLV at all intensities, peak frequencies

2. **`exp06_run02_fixed_raw_channel_summary.txt`**
   - Human-readable table of PLV and peak Hz per intensity
   - Shows expected degradation with dose

3. **`exp06_run02_fixed_raw_channel_overlay.png`**
   - 5-panel figure showing fixed channel aligned with GT at each intensity
   - Visual confirmation that choice is reasonable across dose range

---

## Integration with `analyze_exp06_run02_on_raw_sass_ssd_plv.py`

**At the start of the main analysis script:**
```
# Load fixed channel reference
import json
with open("exp06_run02_fixed_raw_channel_metadata.json") as f:
    fixed_ch_ref = json.load(f)

FIXED_RAW_CHANNEL_NAME = fixed_ch_ref["reference_channel_name"]
```

**In Section 3.4 (Raw Channel Selection):**
```
# OLD (per-intensity re-selection):
FOR each intensity:
    best_ch = argmax(PLV)

# NEW (fixed at 10%):
FOR each intensity:
    ch_idx = raw_eeg.ch_names.index(FIXED_RAW_CHANNEL_NAME)
    on_raw_selected = on_raw_epochs[:, ch_idx, :]
    compute PLV for FIXED_RAW_CHANNEL_NAME
    (no ranking; it's predetermined)
```

This ensures the raw path uses the same electrode across all intensities, isolating the dose effect on that single electrode.
