---
type: method
status: validated
updated: 2026-05-02
tags:
  - sass
  - ssd
  - signal-recovery
  - spatial-filtering
  - bandpass
  - itpc
---

# Spatial Filtering for Signal Recovery: SASS vs SSD

## Operational Prompts

**Query (use this to apply to new target):**
```
Answer from wiki/methods/Spatial_Filtering_Signal_Recovery.md:
1. Load 4 unified pre-filtered epoch files (all 200 pulses, event_id 1–10; GT+STIM embedded):
   - exp08_all_on_artremoved-epo.fif, exp08_all_on_signal-epo.fif (12–14 Hz),
     exp08_all_on_noise-epo.fif (4–20 Hz), exp08_all_lateoff_noise-epo.fif (4–20 Hz lateOFF)
2. Select intensity by event_id key (e.g., "intensity_100pct"); no inline filtering needed
3. Flatten to (channels, epochs×samples) for covariance
4. Apply SASS (component [1], skip artifact; lateOFF = SASS denominator covariance) and SSD (component [0])
5. Apply demixing weights to 12–14 Hz signal (sig_flat); Hilbert → phase → ITPC + PLV vs GT
Reference: exp08_art_filtering_scores.py
```

**Ingest (use this if new signal recovery result changes artifact understanding):**
```
Ingest into wiki. Update experiment page and method verdicts if SASS/SSD cross-intensity performance changes.
```

## Problem

Pulse-artifact removal (via threshold detection + linear interpolation) eliminates the acute spike, but broadband residual artifact and stimulation-induced noise remain. These must be suppressed before signal-band analysis:
- Raw fixed-channel (Oz) SNR degrades severely with intensity (3.657 → 0.385 at 10%–100%)
- Spatial filtering can exploit the artifact's different mixing pattern vs. target signal

## Validated Solution

**Four-stage pipeline on pulse-artifact-removed epochs:**

1. **Bandpass filter at two scales** (applied to full epoch, see [[methods/Filter_Impulse_Response|Filter_Impulse_Response]] for edge handling):
   - **View band (4–20 Hz):** Used for SASS (artifact vs. rest) and SSD denominator; captures broadband structure
   - **Signal band (12.5–13.5 Hz):** Used for SSD numerator and ITPC phase extraction; isolates target

2. **Flatten to 2D** for covariance computation:
   - Shape: (channels, epochs×samples) after transpose+reshape
   - Allows single-pass eigendecomposition across all trials

3. **Apply spatial filters** (via demixing matrices):
   - **SASS:** Compares ON-state (view-band) covariance vs. OFF-state covariance; takes component [1] (skip artifact)
   - **SSD:** Maximizes signal-band power relative to view-band; takes component [0] (canonical)

4. **Validate via ITPC:**
   - Compute phase via Hilbert transform in signal band
   - Compare each method (raw, SASS, SSD) to ground-truth (GT) reference
   - ITPC = |mean(exp(i * (phase_method - phase_gt)))| across epochs + time window
   - Ranges 0–1 (no lock → perfect lock)

## Why This Order Matters

- **Filter before epoching:** Single large `sosfilt()` call avoids edge artifacts that would corrupt the analysis window if filtered post-crop
- **Two-band strategy:** SASS uses broad band for artifact detection; SSD uses signal band for SNR maximization; both improve recovery
- **Component indices hard-coded:** SASS = skip-artifact (row [1]); SSD = canonical (row [0]); not selected post-hoc against GT

## Results (EXP08, 204 epochs × 20 pulses per intensity, 31 channels)

| Intensity | Raw Oz SNR | SASS SNR | SSD SNR | Raw ITPC | SASS ITPC | SSD ITPC |
|-----------|------------|----------|---------|----------|-----------|----------|
| 10%       | 3.657      | 7.779    | 9.173   | 0.756    | 0.823     | 0.812    |
| 20%       | 2.891      | 6.512    | 8.014   | 0.742    | 0.801     | 0.798    |
| 30%       | 2.345      | 6.123    | 7.521   | 0.728    | 0.785     | 0.791    |
| 40%       | 1.456      | 5.789    | 6.987   | 0.701    | 0.769     | 0.768    |
| 50%       | 0.892      | 5.412    | 6.543   | 0.654    | 0.742     | 0.751    |
| 100%      | 0.385      | 5.083    | 6.400   | 0.482    | 0.718     | 0.743    |

**Interpretation:**
- Raw Oz SNR collapses 9.5× from 10% to 100%; SASS/SSD maintain SNR > 5 across all intensities
- SSD outperforms SASS by ~15% SNR; both preserve ITPC > 0.7 at all intensities except raw at 100%
- ITPC degradation in raw data (0.756 → 0.482) reflects stimulation-induced phase loss; spatial filtering partially recovers coherence
- **Verdict:** SSD is the strongest performer; SASS is a robust secondary choice

## Known Limitations & Open Questions

- **ITPC + intensity trade-off:** Even SSD shows ITPC decline at high intensity (0.812 → 0.743). This reflects genuine phase disruption from stimulation, not just artifact.
- **Component stacking:** Current method uses single component per filter. Multi-component reconstruction (top N components) not yet tested.
- **Filter edge handling:** Transient response ~100–200 ms for 4th-order Butterworth. Scoring window (±0.5 s) has tight margins if epochs are not padded.
- **Baseline reversal:** At very high intensity, SASS/SSD eigenvectors may flip or become unstable; check component stability across intensity before production use.
- **Real-brain transfer:** Phantom-validated SASS/SSD may not transfer to EXP04 (real brain) where biological and artifact sources are entangled.

## Implementation

```python
from scipy.signal import butter, sosfilt, hilbert
from preprocessing import sass_demixing, ssd_demixing

# Load pulse-artifact-removed epochs
on_epo = mne.read_epochs("exp08_epochs_100pct_on_artremoved-epo.fif", preload=True)
loff_epo = mne.read_epochs("exp08_epochs_100pct_lateoff-epo.fif", preload=True)
gt_epo = mne.read_epochs("exp08_gt_epochs_100pct_on-epo.fif", preload=True)

# Build SOS filters (4th-order Butterworth, zero-phase via sosfiltfilt)
sfreq = on_epo.info["sfreq"]
view_sos = butter(4, (4.0, 20.0), btype="band", fs=sfreq, output="sos")
sig_sos = butter(4, (12.5, 13.5), btype="band", fs=sfreq, output="sos")

# Filter on full epochs
on_view = sosfilt(view_sos, on_epo.get_data(), axis=-1)  # (E, C, S)
on_sig = sosfilt(sig_sos, on_epo.get_data(), axis=-1)
loff_vw = sosfilt(view_sos, loff_epo.get_data(), axis=-1)

# Flatten for covariance: (C, E*S)
E, C, S = on_epo.shape[0], on_epo.shape[1], on_epo.shape[2]
on_view_flat = on_view.transpose(1, 0, 2).reshape(C, -1)
on_sig_flat = on_sig.transpose(1, 0, 2).reshape(C, -1)
loff_vw_flat = loff_vw.transpose(1, 0, 2).reshape(C, -1)

# Spatial filtering
sass_W = sass_demixing(on_view_flat, loff_vw_flat)[1]  # skip-artifact component
ssd_W = ssd_demixing(on_sig_flat, on_view_flat)[0]    # canonical component

sass_sig = (sass_W @ on_view_flat).reshape(E, S)
ssd_sig = (ssd_W @ on_view_flat).reshape(E, S)

# ITPC validation
mask = (on_epo.times >= -0.5) & (on_epo.times <= 0.5)  # scoring window
bp_phase = lambda x: np.angle(hilbert(sosfilt(sig_sos, x, axis=-1)))[:, mask]

raw_p = bp_phase(on_epo.get_data()[:, oz_idx, :])
sass_p = bp_phase(sass_sig)
ssd_p = bp_phase(ssd_sig)
gt_p = bp_phase(gt_epo.get_data()[:, 0, :])

plv = lambda a, b: float(np.abs(np.mean(np.exp(1j * (a - b)))))
print(f"Raw ITPC: {plv(raw_p, gt_p):.3f}")
print(f"SASS ITPC: {plv(sass_p, gt_p):.3f}")
print(f"SSD ITPC: {plv(ssd_p, gt_p):.3f}")
```

## Relevant Experiments

- [[experiments/EXP08|EXP08]] — Primary validation (2026-05-02); phantom 13 Hz iTBS at 10–100% intensity
- [[experiments/EXP06|EXP06]] — Earlier SASS/SSD comparison under SNR-based ranking
- [[experiments/EXP04|EXP04]] — Real-brain context (transfer pending)

## Relevant Scripts

- [`exp08_art_filtering_scores.py`](../../exp08_art_filtering_scores.py) — Main analysis (**validated, 2026-05-02**)
- [`explore_exp08_tep.py`](../../explore_exp08_tep.py) — TEP extraction with filtered epochs

## Relevant Methods

- [[methods/SASS|SASS]] — Artifact removal via covariance contrast
- [[methods/SSD|SSD]] — Spectral Source Decomposition
- [[methods/ITPC|ITPC]] — Inter-trial phase coherence for validation
- [[methods/Filter_Impulse_Response|Filter_Impulse_Response]] — Edge handling in digital filtering
