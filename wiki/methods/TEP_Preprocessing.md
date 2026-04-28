---
type: method
status: validated
updated: 2026-04-23
tags:
  - tep
  - preprocessing
  - decay-removal
  - dc-removal
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

## Relevant Scripts

- [`explore_exp08_tep.py`](../../explore_exp08_tep.py) — Main TEP extraction (**validated**)
- [`explore_exp08_tep_qc_timeseries.py`](../../explore_exp08_tep_qc_timeseries.py) — QC timeseries comparison (working implementation)
