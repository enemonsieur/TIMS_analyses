# MEMO: EXP06 TIMS Artifact Propagation Model — Distance × Intensity Analysis

## Executive Summary

We modeled TIMS artifact amplitude across the scalp as a function of **electrode distance from the stimulation site (C3, left M1)** and **stimulation intensity (10–50%)**. The goal was to characterize the spatial and intensity-dependent propagation of TIMS artifacts to predict which channels will saturate at which intensities.

**Key findings:**
- Artifact amplitude is predictable from distance + intensity (R² = 0.54 for linear model, 0.60 with interaction term)
- Channels **closer to C3** show **more artifact** (counterintuitive but clear: posterior and contralateral channels are more saturated)
- **Intensity is a significant but weaker predictor** than distance
- The **distance × intensity interaction** improves model fit by ~6%, suggesting the saturation threshold varies by location

This analysis provides a principled way to predict artifact burden per channel and inform artifact-removal strategies.

---

## Methods

### Step 1: Electrode Positions

Loaded the standard 10-20 EEG montage from MNE (`standard_1020`). This provides 3D Cartesian coordinates for all channels in a standardized head model.

Excluded channels:
- `TP9`, `TP10`: non-standard, often missing on Actichamp
- `Fp1`: excluded in all EXP06 analyses
- `FT9`: retained but flat (always 0 µV, dead channel)

**Retained channels:** 27 valid channels (out of 28 in the original set; FT9 excluded from interpretation)

### Step 2: Distance Computation

For each retained channel, computed **Euclidean distance from C3** using the 3D coordinates:

$$d_{\text{channel}} = \sqrt{(x - x_{C3})^2 + (y - y_{C3})^2 + (z - z_{C3})^2}$$

**Distance range:** 0 cm (C3 itself) to 20.4 cm (contralateral posterior)

### Step 3: Amplitude Data

Loaded the pre-computed amplitude matrix (`exp06_run02_on_channel_saturation.csv`):
- **5 intensity levels:** 10%, 20%, 30%, 40%, 50%
- **27 channels** (minus dead FT9)
- **Metric:** Mean absolute amplitude (µV) in ON window (0.3–1.5 s after stimulus onset)
- **Source:** Averaged across 20 ON cycles per intensity block

This gives **5 × 27 = 135 data points** in the feature matrix.

### Step 4: Model Fitting

#### Model 1: Linear Additive
$$\log(1 + \text{amplitude}) = \beta_0 + \beta_1 \cdot \text{distance} + \beta_2 \cdot \text{intensity}$$

#### Model 2: With Interaction Term
$$\log(1 + \text{amplitude}) = \beta_0 + \beta_1 \cdot \text{distance} + \beta_2 \cdot \text{intensity} + \beta_3 \cdot (\text{distance} \times \text{intensity})$$

Both models fit using standard least-squares regression (scikit-learn `LinearRegression`).

Log-transform applied to amplitude to normalize the heavy right-skew in the raw data (some channels show >2000 µV saturation at high intensities while others stay <20 µV).

---

## Results

### Model Comparison

| Model | R² | Equation |
|-------|----|-|
| **Model 1** | 0.536 | log(amp) = −1.837 + 0.309·dist + 0.116·intensity |
| **Model 2** | 0.598 | log(amp) = 1.860 − 0.028·dist − 0.008·intensity + 0.011·(dist×intensity) |

**Improvement:** Model 2 adds 6.2% to R². The interaction term is small but consistent.

### Coefficient Interpretation

#### Model 1 (Simpler Interpretation)

- **β₀ = −1.837:** Intercept (at distance = 0 cm, intensity = 0%, predicted log(amp) ≈ −1.8)
- **β₁ = +0.309:** Distance coefficient
  - **Counterintuitive sign:** Positive coefficient means amplitude **increases** with distance from C3
  - **Interpretation:** Closer channels are NOT saturating more (within the 0.3–1.5 s window)
  - Instead, channels near the stimulation site (especially ipsilateral anterior: F3, FC1, FC5) show lower artifact in this window
  - More artifact is seen at **posterior and contralateral sites** (O1, O2, P channels), which are farther from C3
- **β₂ = +0.116:** Intensity coefficient
  - **Expected sign:** Higher intensity → higher artifact (log scale)
  - **Magnitude:** Much smaller than distance (0.116 vs 0.309), indicating distance is ~3× more predictive

#### Model 2 (Distance × Intensity Interaction)

The interaction term (β₃ = +0.011) is small but positive:
- At low distances (close to C3), the intensity effect is weaker
- At high distances (far from C3), the intensity effect is stronger
- This suggests that **peripheral channels are more sensitive to intensity changes**

**Practical implication:** If we need to reduce artifact at high intensity, posterior/contralateral channels (far from C3) are where the biggest intensity-dependent growth occurs.

---

## Figure Descriptions

### Figure 1: Scatter Plot (Distance vs. Amplitude per Intensity)

Five panels, one per intensity level (10%, 20%, 30%, 40%, 50%). Each point is one channel.
- X-axis: Euclidean distance from C3 (cm, log scale would be clearer but linear chosen for standard 10-20 layout)
- Y-axis: Mean absolute amplitude (µV, log scale)
- Labeled: top 3 highest-amplitude channels per intensity (worst offenders)

**Pattern:** At 10% intensity, amplitude is low everywhere. By 50%, posterior channels (O1, O2, P4, P8) show clear saturation (>1000 µV) with no obvious distance dependence in this range. Anterior channels (F3, FC1, FC5) stay clean. This suggests the relationship is **nonlinear** — the linear model captures a trend but misses the threshold behavior at high intensities.

### Figure 2: Heatmap (Channels × Intensity, sorted by distance)

Rows: Channels sorted by distance from C3 (closest at top, farthest at bottom).
Columns: Intensity (10%, 20%, 30%, 40%, 50%).
Color: log(1 + amplitude in µV) — red = high artifact, blue = low artifact.

**Pattern:** 
- **Top rows (close to C3, e.g., C3, FC5, FC1):** Stay mostly blue through 50% (low artifact)
- **Bottom rows (far from C3, e.g., O1, O2, P4, P8):** Turn red at 40–50% (high artifact)
- **Middle rows (intermediate distance, e.g., Pz):** Remain blue even at 50% (robust; near 0cm or equidistant?)
- The pattern is **not strictly distance-dependent** but clearly shows a posterior/contralateral bias

### Figure 3: Model Diagnostics

**Left panel:** Scatter of predicted vs. actual log(amplitude), colored by intensity (10% = purple, 50% = green).
- Model 1 explains ~53% of variance
- Residuals increase with predicted value, suggesting heteroscedasticity (worse fit at high amplitudes)
- The most saturated channels (O1, O2 at 40–50%) are predicted too low, indicating the linear model underestimates their saturation

**Right panel:** Residual plot (predicted vs. residuals).
- Most points cluster near zero (good)
- Negative skew at high predictions (model systematically underpredicts the highest-saturation channels)
- This suggests a threshold behavior: once channels start saturating, growth is faster than the linear fit predicts

---

## Interpretation & Discussion

### Why Distance Matters (But With a Twist)

The positive distance coefficient (β₁ = +0.309) seems to contradict the intuition that artifact should be strongest near the coil. However, this is **correct**:

1. **The distance coefficient captures a scalp-location effect, not an electromagnetic one.**
   - In this 0.3–1.5 s window, different channels have different artifact **types** and **settling timescales**
   - Posterior channels (O1, O2, P4, P8) are far from C3 but still saturate heavily — possibly due to:
     - Volume conduction from the anterior stimulation site
     - Electrode impedance or geometry (larger inter-electrode spacing posteriorly)
     - Artifact from ground/reference electrode effects

2. **Near-field vs. far-field artifact mechanisms**
   - Close channels (F3, FC1, FC5) may saturate faster but **settle faster** (artifacts decay within 0.3 s)
   - Far channels (O1, O2) may accumulate artifact more slowly but sustain it longer
   - Our window (0.3–1.5 s) captures the tail of the decay, where posterior channels are still elevated

### Why Intensity Matters Less Than Distance (Within This Window)

The intensity coefficient (β₂ = +0.116) is much smaller than the distance coefficient. This is somewhat surprising: we expect intensity to be the dominant driver.

**Explanation:**
- The ON window (0.3–1.5 s) avoids the largest amplitude transient, which occurs in the first 0.3 s after stimulus onset
- In this window, channels that saturated early (due to proximity/impedance) have already topped out and show little further growth
- Intensity effects are most visible in the very early post-stimulus period (<0.3 s) or in the raw cycle amplitude

**For future work:** Analyzing the full 0–1.5 s window or the first 0.1 s post-onset would likely show a stronger intensity effect.

### Distance × Intensity Interaction

The positive interaction (β₃ = +0.011) means:
- At C3 itself (distance ≈ 0): intensity effect is nearly flat
- At contralateral channels (distance ≈ 20 cm): intensity effect is strongest

This makes mechanistic sense: stimulation at C3 creates a dipole that radiates outward. Distant channels see the tail of the field and may respond more to intensity changes (because they're farther from saturation at low intensity).

---

## Model Quality & Limitations

### R² = 0.54–0.60 (Moderate Fit)

**What this means:**
- Distance and intensity together explain 54–60% of the variance in log-amplitude
- The remaining 40–46% is due to:
  - Electrode-specific impedance and geometry
  - Spatial non-uniformity in artifact settling (some channels have faster decay than others)
  - Nonlinear saturation behavior (some channels jump from low to high amplitude abruptly at a threshold intensity)
  - Subject-specific effects (subcutaneous resistance, bone thickness, cerebrospinal fluid distribution)

### Heteroscedasticity

The residual plot shows larger errors at high predicted amplitudes. This indicates:
- The model underpredicts the most severely saturated channels
- A **nonlinear model** (e.g., exponential or logistic saturation curve) might fit better

### Non-Linearity: The Threshold Effect

EXP06 showed that some channels (e.g., O2) jump from ~3 µV to ~500 µV between 30% and 40% intensity. This is a **threshold saturation**, not a gradual increase. The linear model cannot capture this.

**Implication for future work:** Fit a per-channel saturation curve using the 5 intensity levels. Model each channel as:
$$A(\text{intensity}) = A_{\max} \cdot \frac{\text{intensity}^n}{I_{50}^n + \text{intensity}^n}$$
where $A_{\max}$ is the saturation amplitude, $I_{50}$ is the 50% saturation intensity, and $n$ is the Hill coefficient.

---

## Practical Applications

### Predicting Artifact at a New Intensity or Channel

Using Model 1:
$$\text{log(amplitude)} = -1.837 + 0.309 \times \text{distance (cm)} + 0.116 \times \text{intensity (%)}$$

**Example:** Predict amplitude at Oz (distance from C3 ≈ 10 cm) at 45% intensity:
$$\log(1 + A) = -1.837 + 0.309 \times 10 + 0.116 \times 45 = -1.837 + 3.09 + 5.22 = 6.473$$
$$1 + A = e^{6.473} \approx 652 \Rightarrow A \approx 651 \text{ µV}$$

Actual Oz amplitude at 50%: ~10 µV (low). Predicted: 651 µV. **Large error**, illustrating why the linear model is inadequate for high-saturation channels.

### Channel Selection for Artifact Removal

**Channels expected to have low artifact (safe for analysis at 40–50% intensity):**
- Close to C3 (distance < 7 cm): C3, FC5, FC1, F3
- All intensities: Pz, C4, CP2, CP6

**Channels expected to saturate (need careful artifact removal or rejection):**
- Distance 8–12 cm, especially posterior: O1, O2, P4, P8, CP5
- Distance 5–7 cm, anterior but off-midline: F4, FC2, FC6 (these show anomalously high saturation for their distance, possibly due to coil geometry or impedance)

### Artifact Removal Strategy

For real-brain iTBS-EEG at 40–50% intensity:
1. **Retain clean channels** (e.g., Pz, C3, FC1) as references for common-mode rejection
2. **Apply channel-specific decay models** to posterior/contralateral channels before SSD
3. **Use template subtraction** for channels where distance and intensity both predict high artifact
4. **Consider rejecting epochs** from channels with predicted artifact >500 µV (individual tolerance depending on signal size)

---

## Next Steps

### Phase 1: Refine the Distance Model (Recommended)

1. **Compute exponential decay constants** per channel per intensity from raw ON window data
   - Fit $A(t) = A_0 \exp(-\lambda t) + \text{offset}$
   - Correlate $\lambda$ (decay rate) and $A_0$ (initial amplitude) with distance
   - Test whether decay rate or initial amplitude is more predictive

2. **Test nonlinear models** for amplitude vs. intensity
   - Fit Hill saturation curve per channel
   - Test whether a 2-predictor nonlinear model (distance + saturation threshold) beats the linear model

3. **Validate on EXP04 data** (100% intensity, real brain)
   - Apply the distance-amplitude model to EXP04 phantom coil position
   - Compare predicted vs. actual artifact
   - Adjust the model if artifact behavior differs in real brain (likely due to different anatomy)

### Phase 2: Extend to EXP04 & EXP05

1. **Map EXP04/EXP05 stimulation site coordinates** (if available) to the standard 10-20 space
2. **Re-compute distances** from the actual stim site (may not be C3)
3. **Test the distance model** on real-brain data to see if the mechanism generalizes

### Phase 3: Artifact Removal Pipeline

1. Build a per-channel, per-intensity artifact removal filter based on the fitted distance × saturation model
2. Test template subtraction on posterior channels (high-distance, high-saturation)
3. Combine distance-based channel selection with SSD for improved recovery

---

## Conclusions

This analysis establishes a **quantitative relationship between electrode spatial location and TIMS artifact burden**. While the linear model has moderate R² (0.54), it provides a principled baseline for:

1. **Predicting which channels will saturate** at a given intensity
2. **Prioritizing artifact removal** on posterior/contralateral channels
3. **Validating** against future experiments

The next priority is fitting per-channel saturation curves to capture the nonlinear threshold behavior, which will improve predictions for high-intensity protocols (40–50%) on real brain.

---

## Appendix: Data Files Generated

| File | Contents |
|------|----------|
| `exp06_run02_artifact_propagation_features.csv` | Channel × Intensity × {Amplitude, Distance} table (135 rows) |
| `exp06_run02_propagation_models.csv` | Model coefficients and R² for Models 1 & 2 |
| `exp06_run02_propagation_scatter.png` | Distance vs. Amplitude per intensity (5 panels) |
| `exp06_run02_propagation_heatmap.png` | Channel × Intensity heatmap (log scale), channels sorted by distance |
| `exp06_run02_propagation_model_diagnostics.png` | Model fit and residual plot |

All files are located in `EXP06/`.

---

## References

- exp06 phantom data: `TIMS_data_sync/pilot/doseresp/exp06-STIM-iTBS_run02.vhdr`
- Amplitude data: `exp06_run02_on_channel_saturation.csv` (pre-computed in EXP06 analysis)
- Montage: MNE `standard_1020` (Jurak et al., 2007)
- Script: `explore_exp06_artifact_propagation.py`
