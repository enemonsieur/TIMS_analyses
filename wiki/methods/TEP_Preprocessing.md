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

**EXP08 run01 correction (2026-04-28):** The valid single-pulse artifact-removal source is raw `exp08-STIM-pulse_run01_10-100.vhdr`, and the cleaned EEG outputs are `exp08_epochs_{10..100}pct_on_artremoved-epo.fif`. Do not use `exp08t_*_artremoved` for single-pulse work; those files belong to triplet run02 and used the wrong event unit for this question.

### Method: Continuous-Raw Pulse-Level Threshold Detection + Linear Interpolation

For each scheduled run01 pulse and EEG channel:

1. **Build run01 pulse schedule**: 200 pulse centers from sample 20530 at 5.0 s spacing (10 intensities x 20 pulses).
2. **Fit local pre-pulse drift** in continuous Volts data from -100 to -10 ms.
3. **Start interpolation at -10 ms** because the run01 EEG impulse peak is 3 ms before the scheduled pulse sample.
4. **Detect recovery** from +20 to +200 ms using `max(5 x baseline residual std, 2% x pulse peak deviation)`.
5. **Debounce recovery**: require 20 ms of sustained below-threshold signal.
6. **Interpolate**: replace the artifact interval with the local linear drift continuation.
7. **Epoch cleaned raw** into the existing ON windows; STIM/GT reference epoch files remain raw timing references.

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

- `exp08_epochs_{10..100}pct_on_artremoved-epo.fif` — cleaned run01 single-pulse epochs ready for filtering
- `exp08_pulse_artremoved_qc.png` — QC heatmaps (artifact duration per channel/epoch) + before/after overlays
- `exp08_artremoved_dataviz.png` — all-intensity Oz before/after overview
- `exp08_run01_pulse_artifact_summary.txt` — source/config/statistics summary

### Why Pulse-Level Per-Channel?

At 100% intensity, baseline state and residual offsets vary strongly by channel and pulse. Global cropping fails because the "before" and "after" anchor points are not shared across channels. Pulse-level per-channel interpolation adapts to each artifact signature before the triplet-independent run01 epochs are rebuilt.

### Implementation

```python
clean_data_v, durations_ms, thresholds_uv = preprocessing.interpolate_pulse_artifacts_by_threshold(
    raw_eeg.get_data(),
    pulse_samples,
    sampling_rate_hz,
    baseline_window_ms=(-100, -10),
    artifact_start_ms=-10,
    min_artifact_end_ms=20,
    max_artifact_end_ms=200,
    peak_window_ms=(0, 20),
    threshold_sd_multiplier=5.0,
    peak_fraction=0.02,
    debounce_ms=20,
)
```

### Known Limitations

- **Acute artifact only**: This removes the pulse spike window; it does not prove post-pulse physiology or filter-ringing windows are artifact-free.
- **Threshold parameter k=5**: Current run01 results are dominated by the minimum +20 ms end, with one 20% pulse/channel at +29 ms. Revisit only if downstream QC shows residual acute spikes.
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
