---
type: method
status: exploratory
updated: 2026-04-26
tags:
  - artifact
  - validation
  - ground-truth
  - novel-approaches
---

# Artifact Removal Validation: Proving Artifacts Are Actually Removed

## Exploration Prompt

**How can we rigorously demonstrate that a cleanup method removes or suppresses artifact, rather than just hiding or spreading it?**

This is not about a specific technique (ICA, SASS, SSD, etc.). Instead, frame the question broadly:

- What properties must a "removed" artifact have (vs. merely attenuated, shifted, or invisible)?
- How do you detect when a method trades artifact for a different problem (e.g., filters out signal along with artifact)?
- What role does ground-truth play in validation when ground-truth itself can be disrupted by stimulation?
- Which metrics prove removal independently of the method's assumptions?
- Can a single metric ever be sufficient, or must validation always be multi-faceted?

## What It Measures

A validation framework that distinguishes genuine artifact suppression from artifact masking, relocation, or exchange.

## Where It Helped

- [[experiments/EXP08|EXP08]] baseline ITPC (0.76 pre-stimulation) vs. stimulated ITPC (0.25–0.48 even in quiet OFF-windows) revealed that **high SNR ≠ clean phase**. SSD improves power but degrades coherence—prompting the question: *what exactly did it remove?*
- [[experiments/EXP06|EXP06]] showed that [[methods/SNR|SNR]] and [[methods/PLV|PLV]] sometimes contradict. A validation framework would determine which contradiction signals a real cleanup failure vs. a metric mismatch.
- Ground-truth comparisons in phantom experiments create a rare opportunity to validate against known signal structure—but [[experiments/EXP08|EXP08]] shows stimulation disrupts GT itself, so naive GT comparison is insufficient.

## Known Failure Modes

- **Invisibility ≠ Removal**: A method can suppress artifact amplitude while preserving artifact structure in orthogonal subspaces. Broad-frequency metrics miss this.
- **Signal-artifact trade-off**: Methods like SSD can suppress noise while also removing weak biological signals or phase information (seen in EXP08 ITPC degradation).
- **Metric confusion**: High SNR + low ITPC (EXP08) or high PLV + low SNR (EXP06) suggests metrics prioritize different artifact properties. No single metric validates removal across all interpretations.
- **Ground-truth limitations**: In phantom experiments with stimulation, the GT reference itself is disrupted by magnetic/electrical fields (EXP08 baseline 0.76 → stimulated 0.25), making naive GT-comparison invalid.
- **Dimensionality hiding**: Artifact removed from principal components can persist in residual subspaces, undetectable in averaged or low-rank summaries.
- **Statistical independence ≠ functional independence**: Two components can be uncorrelated while still sharing common artifact drivers (e.g., both affected by same field inhomogeneity).

## TIMS Verdict

**Artifact removal validation is currently ad-hoc.** Each method is judged against a different criterion (SNR, PLV, ITPC, topography consistency). TIMS needs a multi-layer validation framework that:

1. **Specifies what "removed" means** in context (suppressed amplitude? phase restored? frequency integrity?)
2. **Tests across multiple independent metrics** (spectral, temporal, spatial, coherence-based)
3. **Validates against ground-truth where possible**, but acknowledges GT disruption under stimulation
4. **Exposes trade-offs explicitly** (what is gained, what is lost?)

## Open Questions

### Foundational
- What are the necessary and sufficient conditions for artifact to be considered "removed" (vs. masked, shifted, or traded)?
- Can removal ever be validated with a single metric, or is multi-metric validation mandatory?
- How do you distinguish artifact suppression from biological signal suppression?

### Validation Specifics
- **Ground-truth paradox (EXP08):** GT baselines are high (ITPC=0.76), but stimulation drops them 3× (ITPC=0.25–0.48) in quiet OFF-windows. Is this GT disruption, frequency shift, or reference mismatch? How should GT comparison be corrected?
- **Metric divergence (EXP06, EXP08):** When SNR and PLV/ITPC disagree, what explains the divergence? Which is closer to ground truth?
- **Spatial validation:** Should artifact removal be validated in sensor space, component space, or both? Can sensor-space validation miss component-level residuals?
- **Frequency-domain validation:** How should validated removal be characterized across frequency bands? EXP08 preserves gamma (1–80 Hz), but is artifact removal uniform across 1–30 Hz vs. 30–80 Hz?
- **Temporal stability:** Should validated removal show consistent artifact suppression across time (within-epoch), intensity (cross-intensity), or both?

### Real-Brain Challenges
- In real-brain data ([[experiments/EXP04|EXP04]]), biological and artifact sources are entangled. How do you validate removal without ground-truth?
- Can phantom-validated cleanup methods (EXP08) transfer to real-brain contexts without new validation?
- What role should resting-state or response-structure consistency play in real-brain artifact validation?

### Novel Approaches
- **Could multi-scale artifact modeling (distance × intensity × channel × frequency) provide independent validation?** (See [[methods/Artifact_Modeling|artifact modeling]] for related work.)
- **Does artifact removal need to be frequency-adaptive?** (Different cleanup strategies for theta vs. gamma vs. broadband artifact?)
- **Could complementary modalities (EEG + simulated field maps + phantom measurements) cross-validate removal?**
- **Should removal validation include prediction tasks?** (E.g., "after cleanup, can a linear model predict post-artifact timecourse from pre-artifact structure?" Poor prediction = good removal?)

## Relevant Experiments

- [[experiments/EXP08|EXP08]] — Ground-truth comparison reveals baseline ITPC=0.76 but stimulated ITPC=0.25–0.48; SSD improves SNR but degrades ITPC (trade-off exposed)
- [[experiments/EXP06|EXP06]] — SNR vs. PLV divergence signals method-dependent artifact interpretation
- [[experiments/EXP04|EXP04]] — Real-brain context where ground-truth is unavailable; validation must rely on consistency and biological plausibility

## Relevant Papers

- [Rogasch et al. (2017), guidelines for artifact removal in TMS-EEG](https://doi.org/10.1016/j.clinph.2016.12.008)
- [Vernet et al. (2014), TMS-evoked potentials artifact characteristics](https://doi.org/10.1007/s13311-014-0313-z)
- [Julkunen et al. (2017), topographic artifact validation in TMS-EEG](https://doi.org/10.3109/17483107.2016.1170201)
- [ter Braack et al. (2015), artifact causes and separation in TMS-EEG](https://doi.org/10.1016/j.neuroimage.2015.02.065)
- [Virtanen et al. (2018), magnetic field modeling for phantom validation](https://doi.org/10.1016/j.neuroimage.2018.03.006)
