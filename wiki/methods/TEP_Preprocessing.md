---
type: method
status: validated
updated: 2026-04-28
tags:
  - tep
  - preprocessing
  - decay-removal
  - dc-removal
  - artifact-removal
  - crop-interpolate
---

# TEP Preprocessing: Decay Removal + Bandpass Filtering

## Operational Prompts

**Query (use this to apply to new target):**
```
Answer from wiki/methods/TEP_Preprocessing.md: decay → bandpass 1–80 Hz → crop → average.
Valid ≤40% MSO. Preserves gamma band. Reference: explore_exp08_tep.py.
```

**Ingest (use this if new result changes TEP understanding):**
```
Ingest into wiki. Update experiment page, method pages, and home only if TEP interpretation changed.
```

## Problem

Exponential decay removal alone (fitting `A·exp(-t/τ)+C`) leaves large residual DC offsets (10K+ µV in EXP08, especially at high intensity 50–100%). Explicit DC centering (mean subtraction) is crude and removes all reference; a proper bandpass solves this systematically.

## Validated Solution

**Three-stage processing on full epoch:**

1. **Decay removal**: Fit `A·exp(-t/τ)+C` on full epoch to capture transient
2. **Bandpass filter**: 1–80 Hz on full epoch to remove DC residuals while preserving gamma-band structure
3. **Window extraction**: Crop to PRE/POST windows and average

### Why This Order Matters

- **Decay on full epoch**: `subtract_exponential_decay()` computes evoked average internally — cropping before decay fitting breaks the transient model
- **Filter on full epoch**: 1 Hz kernel (~1 s) fits within full epoch; removes DC residuals. 80 Hz ceiling preserves gamma activity
- **Crop after filter**: Window extraction after both cleanup steps preserves artifact-free baselines

### What NOT to Do

❌ **DC centering via mean subtraction** — removes all reference anchor; results are scaled arbitrarily
❌ **Decay removal on cropped POST window** — evoked average computed from partial data; fit becomes meaningless  
❌ **Filtering cropped windows** — 0.5 Hz kernel too long for 480 ms; causes instability or edge distortion

## Results (EXP08, 20 epochs per intensity)

| Intensity | PRE range | POST range | Assessment |
|-----------|-----------|-----------|------------|
| 10% | 2.41 µV | 2.49 µV | ✓ Clean baseline, minimal decay |
| 20% | 11.03 µV | 3.35 µV | ✓ Clean baseline, small decay artifact |
| 30% | 11.54 µV | 7.28 µV | ✓ Clean baseline, moderate decay |
| 40% | 12.80 µV | 5.03 µV | ✓ Clean baseline, moderate decay |
| 50% | 34.07 µV | 1425.98 µV | ⚠ Baseline acceptable, large POST decay |
| 100% | 185.92 µV | 17392.93 µV | ⚠ Baseline noisy, extreme POST decay |

**Interpretation**: 
- 10–40%: Decay removal + bandpass fully effective; TEP-valid baselines (<15 µV)
- 50–100%: Decay model insufficient at high intensity; baseline degradation and massive POST artifact remain
- **Conclusion**: Valid TEP extraction possible ≤40% intensity; higher intensities require alternative cleanup (robust regression, per-channel decay constants, or multi-exponential model)

## Implementation

```python
HIGHPASS_HZ = 1.0           # remove slow drift and residual DC
LOWPASS_HZ = 80.0           # preserve gamma band while removing HF noise

# Decay removal on full epoch
epochs = preprocessing.subtract_exponential_decay(
    epochs,
    fit_start_s=0.020,
    outlier_threshold_v=0.01,
)

# Bandpass filter on full epoch (removes DC residuals before windowing)
epochs.filter(l_freq=HIGHPASS_HZ, h_freq=LOWPASS_HZ, verbose=False)

# Extract windows for averaging
epochs_pre = epochs.copy().crop(*PRE_WINDOW_S)   # PRE: -0.8 to -0.3 s
epochs_post = epochs.copy().crop(*POST_WINDOW_S) # POST: 0.020 to 0.5 s

evoked_pre = epochs_pre.average()
evoked_post = epochs_post.average()
```

## Known Limitations & Open Questions

- **Intensity ceiling**: Exponential decay model breaks down >40% MSO; POST baseline shows saturation and large residuals (1.4K–17K µV)
- **Per-channel decay constants**: Current implementation uses single τ per channel; may need intensity-dependent or spatial fit
- **Channel quality**: Bad channels (P7, F4, P3 flagged in EXP06/07) still problematic at high intensity — may need per-electrode model
- **Multi-exponential model**: Single exponential may be insufficient; consider A1·exp(-t/τ1) + A2·exp(-t/τ2) + C for future work

## Relevant Experiments

- [[experiments/EXP08|EXP08]] — Validated 10–40% intensity range; 50–100% shows limitations

## Pulse Artifact Removal (Crop+Interpolate)

**CRITICAL**: Filtering during the pulse artifact window is invalid because the bandpass filter rings for 2+ s post-pulse, spreading the artifact across the entire analysis window and corrupting ITPC/PLV metrics. Single-pulse TMS experiments require artifact removal **before any filtering**.

**EXP08 run01 correction (2026-05-02):** The valid single-pulse artifact-removal source is raw `exp08-STIM-pulse_run01_10-100.vhdr`. Outputs are 4 unified epoch files with GT+STIM embedded: `exp08_all_on_artremoved-epo.fif`, `exp08_all_on_signal-epo.fif`, `exp08_all_on_noise-epo.fif`, `exp08_all_lateoff_noise-epo.fif`. Do not use `exp08t_*_artremoved`; those belong to triplet run02.

### Method: Dual-Threshold find_peaks + Linear Interpolation

For each scheduled run01 pulse and EEG channel:

1. **Build run01 pulse schedule**: 200 pulse centers from sample 20530 at 5.0 s spacing (10 intensities × 20 pulses).
2. **Compute pre-pulse baseline statistics** (−100 to −10 ms): mean and std per channel.
3. **Measure first-20ms spike** (0 to +20 ms): max absolute amplitude relative to baseline mean.
4. **Compute dual threshold** per channel: `max(5 × baseline_SD, 2% × first-20ms_peak)`.
5. **Detect artifact recovery** from +20 to +200 ms using `scipy.signal.find_peaks(height=threshold)`; record last detected peak above threshold.
6. **Interpolate artifact**: replace −25 ms → last_peak with linear interpolation between start and end values (continues baseline trend).
7. **Filter three copies** of cleaned raw: 1 Hz HP (artremoved), 12–14 Hz (signal), 4–20 Hz (noise/lateOFF).
8. **Epoch into 4 unified FIF files** with GT+STIM embedded, event_id 1–10 per intensity.

### Results (EXP08 run01, 20 pulses x 28 channels per intensity)

All 10 single-pulse intensities were regenerated from raw run01. Current summaries are written to `exp08_run01_pulse_artifact_summary.txt`; the acute removal window is -10 to +20 ms for nearly all channels, with one 20% pulse/channel extending to +29 ms.

| Intensity | Mean end ms | Std | Min | Max | Mean threshold uV |
|-----------|------------:|----:|----:|----:|------------------:|
| 10% | 20.0 | 0.0 | 20 | 20 | 10.8 |
| 20% | 20.0 | 0.4 | 20 | 29 | 32.0 |
| 30% | 20.0 | 0.0 | 20 | 20 | 83.0 |
| 40% | 20.0 | 0.0 | 20 | 20 | 157.3 |
| 50% | 20.0 | 0.0 | 20 | 20 | 320.9 |
| 60% | 20.0 | 0.0 | 20 | 20 | 519.5 |
| 70% | 20.0 | 0.0 | 20 | 20 | 712.9 |
| 80% | 20.0 | 0.0 | 20 | 20 | 875.9 |
| 90% | 20.0 | 0.0 | 20 | 20 | 1005.9 |
| 100% | 20.0 | 0.0 | 20 | 20 | 1132.1 |

100% Oz acute-window validation: raw abs max 93,340.8 uV -> cleaned abs max 6,781.2 uV. The visible pulse spike is removed in `exp08_pulse_artremoved_qc.png` and `exp08_artremoved_dataviz.png`.

### Outputs

- `exp08_all_on_artremoved-epo.fif` — 1 Hz HP cleaned, all 200 pulses, GT+STIM embedded
- `exp08_all_on_signal-epo.fif` — 12–14 Hz filtered, all 200 pulses
- `exp08_all_on_noise-epo.fif` — 4–20 Hz filtered, all 200 pulses
- `exp08_all_lateoff_noise-epo.fif` — 4–20 Hz filtered, +2 to +4 s lateOFF
- `exp08_pulse_artremoved_qc.png` — QC heatmaps (artifact duration per channel/epoch) + before/after overlays
- `exp08_artremoved_dataviz.png` — all-intensity Oz before/after overview
- `exp08_run01_pulse_artifact_summary.txt` — source/config/statistics summary

### Why Pulse-Level Per-Channel?

At 100% intensity, baseline state and residual offsets vary strongly by channel and pulse. Global cropping fails because the "before" and "after" anchor points are not shared across channels. Pulse-level per-channel interpolation adapts to each artifact signature before the triplet-independent run01 epochs are rebuilt.

### Implementation (inline in exp08_preprocessing.py)

```python
def ms(x): return int(round(x / 1000.0 * sfreq))

clean_data = raw.get_data().copy()
for p_idx, pulse in enumerate(pulse_samples.astype(int)):
    eeg_sig = clean_data[eeg_idx, :]
    bl = eeg_sig[:, pulse + ms(-100) : pulse + ms(-10)]  # baseline window
    bl_mean = bl.mean(axis=1)
    bl_std = bl.std(axis=1)
    first20 = np.abs(eeg_sig[:, pulse : pulse + ms(20)] - bl_mean[:, None])
    search = np.abs(eeg_sig[:, pulse + ms(20) : pulse + ms(200)] - bl_mean[:, None])
    threshold = np.maximum(5.0 * bl_std, 0.02 * first20.max(axis=1))  # dual threshold
    
    art_start = pulse + ms(-25)
    for k, ch in enumerate(eeg_idx):
        peaks, _ = find_peaks(search[k], height=threshold[k])
        art_end = pulse + ms(20) + peaks[-1] if len(peaks) else pulse + ms(20)
        idx = np.arange(art_start, art_end)
        if idx.size:
            clean_data[ch, idx] = np.linspace(clean_data[ch, art_start], clean_data[ch, art_end], idx.size, endpoint=False)
```

### Known Limitations

- **Acute artifact only**: Removes the pulse spike window (−25 ms → last detected peak); does not address post-pulse physiology or filter-ringing contamination.
- **Dual-threshold strategy**: Both components are active (5×SD and 2%×spike); neither is redundant. However, at low intensities (<30%), the 2% component rarely triggers, and most removal is SD-based.
- **Last-peak detection**: Uses `find_peaks` to locate the last peak above threshold in +20 to +200 ms window. If oscillation continues beyond +200 ms (rare at single-pulse), endpoint may be underestimated.
- **No spatial modeling**: Each channel detected independently; may miss coordinated artifact patterns across electrode array.

### Validation

1. Timing: 200 run01 pulses, 20 pulses per intensity, 5.0 s spacing from sample 20530.
2. Before/after overlays: acute pulse spike removed in Oz and worst 100% channel views.
3. Numeric residual check: 100% Oz acute-window abs max 93,340.8 uV raw -> 6,781.2 uV cleaned.
4. Downstream ITPC/SNR/TEP still need rerun from `*_artremoved-epo.fif`; filtered post-pulse windows remain invalid until impulse response is checked.

## Relevant Scripts

- [`explore_exp08_pulse_artifact_removal.py`](../../explore_exp08_pulse_artifact_removal.py) — Main pulse artifact removal (**validated, 2026-04-28**)
- [`explore_exp08_tep.py`](../../explore_exp08_tep.py) — TEP extraction on artremoved epochs (once filtering strategy updated)
- [`explore_exp08_tep_qc_timeseries.py`](../../explore_exp08_tep_qc_timeseries.py) — QC comparison
