# exp06 Phantom Recoverability and Artifact Direction

## Abstract

exp06 is a phantom calibration study designed to test the recoverability of a 12.45 Hz target oscillation across repeated stimulus intensity (10–50%) in baseline, ON-state, and late post-offset conditions. Using spectral decomposition (SSD) and ground-truth (GT) phase-locking analysis, we characterize which stimulus regimes allow robust oscillatory recovery and identify the mechanisms of failure at high intensity. We show that baseline and late-OFF states support near-ceiling recovery across all intensities, while ON-state recovery is conditionally positive at 10–30% and breaks at 40–50% due to artifact dominance overwhelming the target in the raw channel spectral profile. Raw artifact characterization reveals channel-dependent amplitude saturation and post-offset settling times that vary by over 1 s across neighboring channels, indicating that a single global decay model is insufficient. We conclude that artifact separation modeling is prerequisite before translating to human brain data.

---

## Introduction

### Background

Earlier phantom work established foundational concepts for iTBS artifact recovery. exp03 demonstrated that after explicit post-pulse exclusion windows, ground-truth-like structure could be recovered with coherence of 0.980–0.982 after hard windowing, while standard SSP over-subtracted the signal to 0.275 coherence (Experiment 3 results). However, exp03 did not address the harder question: under *repeated* stimulation at varying intensity, which temporal windows remain interpretable?

exp05 reframed the problem as artifact separation first and identified a critical design issue: the earlier 5 Hz iTBS target frequency was positioned too close to the fundamental stimulation rhythm, creating spectral overlap that degraded recovery. This motivated the current exp06 design: use a measured 12.45 Hz ground-truth frequency, sweep stimulus intensity from 10–50%, and characterize recoverability plus artifact dynamics across baseline, ON-state, and late post-offset regimes.

### Rationale

Recoverability in the phantom is the gating criterion for human brain claims. If a strong, externally-controlled oscillation cannot be reliably separated from a known artifact, then weaker endogenous brain signals will certainly fail. exp06 tests three specific questions:

1. Does the redesigned baseline target provide a strong enough reference for transfer testing?
2. Can a frozen baseline SSD model generalize to post-offset conditions across the full intensity sweep?
3. Under active stimulation, at which intensities does the ON-state target remain recoverable, and is failure due to signal destruction or spatial separation breakdown?

The answers will determine whether the next work is hypothesis-generating exploratory analysis or mandatory artifact modeling before real-brain translation.

---

## Methods

### Participants and Data Acquisition

All recordings were phantom (no human subjects). Two sessions were analyzed:
- **exp06-baseline-gt_12hz_noSTIM_run01.vhdr**: 321.18 s of baseline recording with no stimulation, 12.45 Hz ground-truth reference oscillation, 1000 Hz sampling rate, 28 retained EEG channels (excluding stim, ground_truth, Fp1, TP9, TP10).
- **exp06-STIM-iTBS_run02.vhdr**: 600 s of iTBS stimulation with ground-truth reference, containing five intensity blocks (10–50%) with 20 ON/OFF cycles each, detected using threshold_fraction=0.08.

### Baseline SSD Reference Establishment

To establish a strong baseline target, we performed spectral decomposition (SSD) on the baseline session. EEG was divided into 319 non-overlapping 1.0 s windows (stride 1.0 s, coverage 99.3% of the 321 s recording). For each window, power spectral density (PSD) was estimated using Welch's method (4–20 Hz). We fit SSD to extract components maximizing power in the 12.0–13.0 Hz target band relative to the 4.0–20.0 Hz view band.

The selected component (component 1) was compared to raw channels ranked by target-band PSD (12.0–13.0 Hz) and spatially compared via topographic projection onto the standard 10–20 EEG montage.

### Late-OFF Transfer Test

To test whether the baseline SSD solution generalizes to post-offset conditions, we:

1. Detected measured ON and OFF windows in run02 using a threshold detector (threshold_fraction=0.08 applied to the stim channel).
2. Defined late-OFF windows as 1.5–3.2 s after measured offset (designed to avoid the immediate transient artifact).
3. Extracted late-OFF epochs and applied the frozen baseline SSD weights without refitting.
4. Computed spectral validity (peak frequency recovery within 12.0–13.0 Hz) and phase-locking coherence (ITPC) between the SSD component and recorded ground-truth channel.

ITPC was computed as the mean cross-epoch phase coherence after band-pass filtering both signals in the 12.0–13.0 Hz band and computing instantaneous phase via Hilbert transform.

### ON-State SSD Fitting and Recoverability

To assess ON-state recoverability, we deviated from the frozen transfer approach and instead fit SSD separately within each ON block. This addresses the possibility that the spatially optimal decomposition changes under active stimulation.

For each intensity block (10%, 20%, 30%, 40%, 50%):

1. Detected measured ON blocks with threshold_fraction=0.08.
2. Extracted the accepted ON window (0.3–1.5 s after measured onset, designed to exclude initial artifact transient).
3. Fit SSD on all available ON epochs within that block, extracting components.
4. Selected the in-band component with the strongest GT-band coherence and peak-to-flank ratio. **In-band was defined strictly as recovered_peak_hz within 11.951172–12.951172 Hz.**
5. Computed spectral validity (binary: in-band yes/no), peak-to-flank ratio (target-band PSD peak divided by maximum flank PSD), mean GT-locking (ITPC), and time-resolved ITPC course.

The key distinction from late-OFF: spectral validity is the primary criterion here, while GT-locking is supporting evidence only.

### Raw Artifact Characterization

To determine whether the ON-state failure was due to uniform amplitude scaling or spatially heterogeneous transient dynamics, we analyzed raw cycles:

1. Rebuilt the full 6.0 s stimulation cycle from measured stimulus onsets.
2. Averaged cycles within each intensity block (20 cycles per block, except block 5 with 19 cycles).
3. For candidate posterior channels (O2, O1, Oz, Pz, P4, P3), computed mean absolute cycle amplitude.
4. Measured post-offset settling as the first time after measured offset when the mean cycle envelope stayed within ±200 µV for the remainder of the cycle (operational, not physiological criterion).

This analysis was designed to reveal whether artifact grows monotonically with intensity (scalar model) or shows channel-dependent saturation and decay (spatial heterogeneity).

---

## Results

### Baseline SSD Reference is Strong and Posterior-Localized

The selected baseline SSD component (component 1) recovered the 12.451172 Hz target with a target-vs-flank ratio of 279.33, indicating excellent spectral concentration. The top five raw channels ranked by 12–13 Hz PSD (O2, P8, Oz, P4, O1) were identical to the top five channels in the SSD topographic pattern (by absolute weight). This spatial agreement validates that SSD extracted the true target signal and did not capture artifactual oscillations. The baseline reference is strong enough to justify transfer and ON-state testing.

![EXP06/exp06_baseline_raw_channel_target_band_ranking.png](../../EXP06/exp06_baseline_raw_channel_target_band_ranking.png)

![EXP06/exp06_baseline_ssd_intensity_component.png](../../EXP06/exp06_baseline_ssd_intensity_component.png)

### Late-OFF: Baseline SSD Generalizes Robustly Across All Intensities

The frozen baseline SSD weights were applied to late-OFF windows (1.5–3.2 s after measured offset) across all five intensity blocks in run02. The transferred SSD recovered the correct peak (12.451172 Hz) in all five blocks. Mean GT-locking (ITPC) was near ceiling:

| Intensity | SSD ITPC | Raw O2 ITPC | Difference |
|-----------|----------|------------|-----------|
| 10%       | 0.9983   | 0.9973     | +0.0010   |
| 20%       | 0.9990   | 0.9975     | +0.0015   |
| 30%       | 0.9992   | 0.9978     | +0.0014   |
| 40%       | 0.9994   | 0.9977     | +0.0017   |
| 50%       | 0.9995   | 0.9985     | +0.0010   |

The SSD was marginally higher than raw O2 in every block, but the difference was <0.002 ITPC units (approximately noise at this scale, with no statistical framing). The robust recovery across intensities confirms that the experiment was successfully redesigned: the post-offset regime is genuinely recoverable, ruling out a global design failure.

![EXP06/exp06_run02_art_filtering_psd_panels.png](../../EXP06/exp06_run02_art_filtering_psd_panels.png)

![EXP06/exp06_run02_art_filtering_itpc_summary.png](../../EXP06/exp06_run02_art_filtering_itpc_summary.png)

### ON-State Recovery Fails at High Intensity Due to Artifact-Driven Peak Shift

ON-state SSD (fitted separately per intensity block) showed intensity-dependent failure. Spectral validity held in 4/5 blocks, failing only at 50%:

| Intensity | In-Band? | Peak-to-Flank | SSD ITPC | Raw O2 ITPC | SSD - Raw |
|-----------|----------|---------------|----------|------------|-----------|
| 10%       | Yes      | 1.348         | 0.966    | 0.843      | +0.123    |
| 20%       | Yes      | 14.182        | 0.979    | 0.910      | +0.069    |
| 30%       | Yes      | 6.584         | 0.970    | 0.941      | +0.029    |
| 40%       | Yes      | 0.675         | 0.500    | 0.996      | **−0.496** |
| 50%       | **No**   | 0.975         | 0.624    | 0.9995     | **−0.376** |

The peak-to-flank ratio collapsed at 40–50%, dropping below 1.0 at 40% (meaning the target-band peak no longer exceeded the flank noise). Inspection of the PSD panels (Figure: exp06_run02_on_art_filtering_psd_panels) reveals the mechanism: **at 40–50% ON intensity, the raw O2 channel's spectral peak shifts away from the 12.45 Hz target and is dominated by the 10 Hz harmonic of the 5 Hz iTBS stimulation frequency.** This is not a spatial masking problem within SSD component space—it is a fundamental spectral displacement in the raw channel itself, where the artifact has grown so large that it dominates the channel's frequency content.

High raw O2 ITPC values (0.996–0.9995) at 40–50% do not indicate that the 12.45 Hz target remains recoverable; ITPC reflects phase coherence to the externally-controlled ground-truth recording, but the ground-truth is no longer the dominant frequency component in O2's actual spectrum. The target has been effectively replaced by the 10 Hz stimulation harmonic in the raw channel.

At low and mid intensities (10–30%), the SSD GT-locking exceeded raw O2 by 2–12%, the peak-to-flank ratio remained well above 1.0, and the raw O2 spectral peak remained at 12.45 Hz, indicating robust target isolation and recovery.

![EXP06/exp06_run02_on_art_filtering_psd_panels.png](../../EXP06/exp06_run02_on_art_filtering_psd_panels.png)

![EXP06/exp06_run02_on_mean_gt_locking.png](../../EXP06/exp06_run02_on_mean_gt_locking.png)

### Raw Artifact Is Spatially Heterogeneous, Not a Uniform Scalar Process

Mean absolute cycle amplitude showed strong channel dependence, with different saturation points:

| Channel | 10%    | 20%    | 30%     | 40%     | 50%      |
|---------|--------|--------|---------|---------|----------|
| O1      | 9.9    | 16.1   | 403.1   | 837.9   | 1169.8   |
| O2      | 2.8    | 2.8    | 2.9     | 528.7   | 2771.1   |
| Oz      | —      | —      | —       | —       | —        |
| Pz      | 1.5    | 1.8    | 2.3     | 2.0     | 1.9      |
| P4      | —      | —      | —       | —       | —        |
| P3      | —      | —      | —       | —       | —        |

**O1** showed monotonic growth from 10 µV to >1 mV. **O2** remained quiet through 30% (~2.8 µV) then jumped catastrophically at 40% (528.7 µV, a 180-fold increase). **Pz** stayed low throughout (never >26 µV) across all intensities. This reveals that the artifact is not a uniform amplitude scaling but rather has channel-specific saturation thresholds.

Post-offset settling (time to return below ±200 µV) was similarly heterogeneous:

| Channel | 30%   | 40%   | 50%   |
|---------|-------|-------|-------|
| O1      | 0.21  | 0.39  | 0.48  |
| O2      | —     | 1.34  | 1.63  |
| P4      | —     | 0.29  | 1.60  |
| Pz      | never | never | never |

Post-offset settling times differed by >1 second across channels at the same intensity (e.g., P4 at 40%: 0.29 s vs. O2 at 40%: 1.34 s). Several lower-artifact channels (e.g., Pz) never exceeded ±200 µV even at the highest intensity. This spatial and temporal heterogeneity is incompatible with a single global decay model and instead suggests that per-channel or spatial basis artifact modeling would be necessary.

![EXP06/exp06_run02_cycle.png](../../EXP06/exp06_run02_cycle.png)

![EXP06/exp06_run02_cycle_fixed200.png](../../EXP06/exp06_run02_cycle_fixed200.png)

---

## Discussion

### Summary of Findings

exp06 provides a three-state characterization of phantom oscillatory recoverability across iTBS intensities:

1. **Baseline** (no stimulation): Strong, unambiguous recovery. SSD isolates the 12.45 Hz target with high spectral concentration (target-vs-flank = 279) and clear posterior topography.

2. **Late-OFF** (1.5–3.2 s after measured offset): Robust recovery across all intensities. Frozen baseline SSD generalizes perfectly, maintaining spectral validity and near-ceiling GT-locking (ITPC > 0.998) in all five blocks.

3. **ON-state** (0.3–1.5 s after measured onset): Intensity-dependent and channel-dependent failure. At 10–30%, the target is recoverable via SSD with GT-locking > 0.96 and stable spectral peak at 12.45 Hz. At 40–50%, the raw O2 spectral peak shifts to the 10 Hz harmonic of the iTBS stimulation, and SSD spatial filtering breaks (peak-to-flank ratio <1.0), indicating that artifact dominance has displaced the target from the channel's spectral profile.

### Why SSD Fails at 40–50% ON: Artifact Dominance, Not Spatial Masking

At 40–50% ON intensity, the failure of SSD is not due to inability to separate a recoverable target from artifact within component space. Instead, the raw O2 channel itself has shifted its spectral peak from 12.45 Hz to the 10 Hz harmonic of the 5 Hz iTBS stimulation frequency. The artifact has become so dominant in the raw channel that it has displaced the target from the channel's spectral profile. SSD cannot recover a signal that is no longer the dominant spectral component in the underlying channel.

The high raw O2 ITPC (0.996–0.9995) at 40–50% is misleading: it measures phase coherence to the ground-truth recording, but this does not reflect the raw channel's actual spectral content. The raw O2 is dominated by 10 Hz artifact, not 12.45 Hz target, as evidenced by the PSD shift.

This is a more severe failure mode than spatial masking: **it is fundamental spectral displacement.** The artifact does not hide the target in hidden components; it replaces it in the raw channel.

This result is precisely why **SSD alone cannot be the final solution for real-brain translation.** In this phantom:
- The ground-truth reference is strong and locked to stimulus timing.
- The target signal is externally controlled and known.
- The artifact mechanism is unambiguous and well-characterized (channel-specific 10 Hz dominance).

Yet SSD still fails at high intensities because the fundamental spectral content of the raw channel has been displaced. In human brain data, where the target SNR will be orders of magnitude weaker and the artifact will not be externally controlled, raw-channel-level dominance by artifact will be an insurmountable problem for any decomposition-only approach.

### The Artifact Is Spatially Heterogeneous

The artifact is not a single global process that scales uniformly. Instead, it exhibits:

- **Channel-dependent saturation thresholds**: O1 saturates at 30%, O2 at 40%, and Pz never saturates.
- **Intensity-dependent dynamics**: Different channels show different growth curves; some are approximately linear, others show sudden breakpoints.
- **Channel-dependent decay**: Post-offset settling times differ by >1 s across neighboring posterior channels, ruling out a single scalar decay constant.

This heterogeneity violates the assumptions of a global decay model. It suggests that per-channel or spatial basis (e.g., ICA, SVD) artifact modeling would be necessary.

### Constraints on Next Steps

We identify two critical open questions before proceeding:

1. **Alternative methods have not been tested.** ICA, SSP, template subtraction, and other spatial methods have not been compared against decay modeling at 40–50% ON. We cannot yet claim that decay modeling is "obligatory" without ruling out these alternatives.

2. **The 0.3 s onset guard was not validated.** The accepted ON window starts 0.3 s after measured stimulus onset, designed to exclude the initial artifact transient. This assumption has not been verified against the cycle plots. If 0.3 s is insufficient and some channels remain contaminated at that latency, the ON window definition itself may need adjustment.

### Implications for Human Brain Translation

The path forward requires:

1. **Artifact separation before hypothesis testing.** The phantom shows that the target is recoverable, but only with strong spatial and temporal constraints. Real-brain data will require explicit artifact removal, not SSD-only filtering.

2. **Comparison of multiple denoising approaches.** At minimum, channel-wise decay modeling and template subtraction should be tested in parallel to identify the most robust approach for the heterogeneous artifact profile observed.

3. **Validation of the 0.3–1.5 s ON window.** The cycle plots should be carefully reviewed to confirm that 0.3 s adequately excludes artifact transients and that 1.5 s adequately respects onset-driven dynamics.

4. **Exploratory biology only, after artifact constraints.** Once artifact removal is better constrained in the phantom, the next step should be hypothesis-generating review of exp04 baseline before/after data, framed as exploratory screening for candidate effects, not confirmation.

---

## Conclusions

exp06 successfully characterizes the recoverability landscape of a phantom iTBS target across intensities. We show that:

- Baseline and late-OFF states support robust, near-ceiling oscillatory recovery across all intensities.
- ON-state recovery is intensity-limited: viable at 10–30%, but failing at 40–50% due to artifact-driven spectral displacement, where the raw channel's peak shifts from 12.45 Hz to the 10 Hz harmonic of iTBS stimulation.
- The residual artifact is spatially and temporally heterogeneous, with channel-specific saturation thresholds and decay dynamics that violate global decay assumptions.

These findings justify artifact separation modeling as a **prerequisite, not optional step**, before real-brain iTBS claims can be advanced. The phantom work has defined the operating range and the mechanistic bottleneck; the next mandatory work is to test competing artifact-removal approaches and identify which generalizes to human data.

---

## References

- exp03 results: Pulse-centered phantom work showing post-pulse recovery with explicit windowing.
- exp05 results: Artifact separation analysis motivating target frequency redesign from 5 Hz to 12.45 Hz.
- exp06 data: Two sessions (baseline and run02 with five-intensity sweep).
