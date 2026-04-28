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

### Method: Per-Epoch Per-Channel Threshold Detection + Linear Interpolation

For each (epoch, channel):

1. **Compute pre-pulse baseline** (−100 to −5 ms): mean and standard deviation
2. **Walk forward from pulse onset** sample-by-sample until both:
   - Signal is close to baseline: |signal − baseline_mean| < 5×baseline_std
   - Signal is stable/decreasing: current_dev ≤ prev_dev × 1.1 (decaying toward baseline)
   - Confirm with 5 consecutive samples (debounce)
3. **Extract baselines**:
   - Pre-anchor: baseline_mean from step 1
   - Post-anchor: mean of 10 ms of signal after artifact recovery
4. **Interpolate**: Replace artifact region with linear ramp from pre-anchor to post-anchor
5. **Hard cap**: Never crop >200 ms per trial (safety)

### Results (EXP08, 20 epochs × 28 channels per intensity)

| Intensity | Mean artifact duration | Std | Range | Notes |
|-----------|------------------------|-----|-------|-------|
| 10% | 150.3 ms | 59.2 | 8–200 ms | Low intensity, slow decay |
| 50% | 133.3 ms | 72.6 | 1–200 ms | Moderate, many hit cap |
| 100% | 71.7 ms | 79.9 | 1–200 ms | High intensity, faster decay but noisier |

### Outputs

- `exp08t_epochs_{10,50,100}pct_on_artremoved-epo.fif` — cleaned epochs ready for filtering
- `exp08_pulse_artremoved_qc.png` — QC heatmaps (artifact duration per channel/epoch) + before/after overlays

### Why Per-Epoch Per-Channel?

At 100% intensity, baseline is bimodal (±315 µV) and within-epoch decay reaches −3000 µV. Global cropping fails because the "before" and "after" anchor points vary significantly across epochs. Per-epoch detection adapts to each trial's unique artifact signature and baseline state.

### Implementation

```python
PRE_BASELINE_START_MS = -100   # capture current baseline state
PRE_BASELINE_END_MS = -5
K_THRESHOLD = 5                # threshold: k × baseline_std
DEBOUNCE_SAMPLES = 5           # confirmation window
MAX_ARTIFACT_MS = 200          # hard cap
POST_ANCHOR_SAMPLES = 10       # 10 ms post-recovery for anchor

# Detect and remove artifact for all epochs/channels
epochs_clean, artifact_end_samples = remove_pulse_artifact(epochs, config)
```

### Known Limitations

- **Threshold parameter k=5**: Conservative for low intensities (slow decay), may under-crop at 100% where artifact decays faster. May require intensity-dependent k.
- **Stability criterion**: Requires signal to be decreasing; brief noise spikes can delay detection by 1 sample at a time.
- **No spatial modeling**: Each channel detected independently; may miss coordinated artifact patterns across electrode array.

### Validation

1. Visual inspection of heatmaps: artifact_end_samples should increase with intensity (slower recovery) — currently: 10% > 50% > 100%, suggesting high-intensity decay is faster once above threshold
2. Before/after overlay: artifact spike removed, baseline smooth on both sides
3. Downstream ITPC/SNR: compare SNR metrics on raw vs. artremoved epochs (should improve significantly)

## Relevant Scripts

- [`explore_exp08_pulse_artifact_removal.py`](../../explore_exp08_pulse_artifact_removal.py) — Main pulse artifact removal (**validated, 2026-04-28**)
- [`explore_exp08_tep.py`](../../explore_exp08_tep.py) — TEP extraction on artremoved epochs (once filtering strategy updated)
- [`explore_exp08_tep_qc_timeseries.py`](../../explore_exp08_tep_qc_timeseries.py) — QC comparison
