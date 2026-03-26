# MEMO: Characterizing TIMS Dose-Response Through Micro-Experiments

## What TIMS Is and What We Are Doing

TIMS (Temporal Interference Magnetic Stimulation) uses two coils driven at slightly offset frequencies. The two fields superpose inside the brain, producing a beat frequency at depth -- for example, 10 Hz -- while each individual coil operates at a frequency too high to stimulate on its own. The result is focal deep stimulation without the surface side effects of traditional TMS.

The hardware is real and programmable. The `pytims` Python API (`arbitrary_signal_protocol.py`, `ctbs_like_v1_amp5hz_mod50hz_triplets.py`) allows us to define arbitrary amplitude envelopes, modulation waveforms, burst patterns, and ON/OFF gating cycles, then compile them into `.tims` protocol files. We can design any waveform we want and run it.

**The goal is to characterize how TIMS interacts with the brain in a dose-response manner.** We do this through many small, targeted micro-experiments, each testing one specific question. Ultimately, we want to use TIMS as a TMS-like tool -- deliver precisely controlled stimulation and measure the neural response via EEG.

---

## Experiment Log

| Exp | Date | Subject | Protocol | Key Finding | Status |
|-----|------|---------|----------|-------------|--------|
| exp02 | Feb 2025 | Phantom | 10 Hz pulsed, ~10 s IOI | PLV = 0.25 at onset (p = 0.005). SSD eigenvalues all < 1. No amplitude boost. | Done |
| exp03 | Feb 2025 | Phantom | 10 Hz pulsed, 1 Hz rate | Dual-center blockzero works. Filter-only and TESA-ICA fail. | Done |
| exp04 | Feb 2025 | **Real person** (sub01) | 50 Hz modulated pulse | TEP visible after exponential decay removal. Pre/stim/post design works. | Done |
| exp05 | Mar 20 2025 | Phantom | cTBS (5 Hz bursts, 50 Hz triplets, 2s ON / 3s OFF) | 30% is cleaner than 100% across channels. Recorded GT peaks near 7.1 Hz, so the old 10 Hz SSD was mis-targeted. Baseline-transfer SSD remains weak overall. See MEMO_exp05_analysis.md. | Done |

---

## What We Know (Hard Findings)

**1. Artifact window depends on intensity.** The user discovered that artifact windows only appear when stimulation intensity exceeds approximately 30%. Below that, the artifact is negligible. exp05 is designed to verify this with a direct 30% vs 100% comparison on the same phantom.

**2. The dual-center blockzero pipeline works.** Tested on exp03 phantom data. Steps: demean pre-segment from pre-center, demean post-segment from post-center, zero-fill the artifact window [-1.0 s, +0.030 s], crop to [0.08, 1.0 s], highpass at 0.5 Hz. This is the validated artifact removal approach.

**3. Filter-only and TESA-ICA both fail.** Proven by the scripts in `evidence/` (`show_filter_only_failure_exp03.py`, `show_tesa_ica_failure_exp03.py`). Filtering alone cannot remove the broadband artifact. ICA does not converge on a clean separation.

**4. SSD eigenvalues are all below 1.** In exp02 (phantom), the best SSD component had eigenvalue 0.53. This means the 10 Hz ground truth signal never dominates over the noise bands, even in a phantom with no biological noise. SSD can still extract useful components, but they are weak.

**5. No amplitude boost from TI stimulation.** Envelope ratio post-pulse = 0.94 in exp02. The TI beat frequency does not increase 10 Hz power. The observed effect is phase concentration, not amplitude enhancement.

**6. Exponential decay removal works for TEPs.** In exp04 (real person), fitting `amplitude * exp(-t/tau) + offset` per channel and subtracting it from all epochs successfully removes the slow post-pulse drift. TEPs become visible in the triptych (pre/stim/post comparison).

---

## PLV = 0.25: What It Actually Means

In exp02, we measured PLV = 0.25 at pulse onset across 83 trials, with Rayleigh test p = 0.005. The user asked: "does this mean the phases change similarly 25% of the time?" No. Here is what it means.

**What PLV measures.** For each trial, extract the phase of the 10 Hz signal at the moment the pulse arrives. Plot each trial's phase as a point on the unit circle. PLV is the length of the *mean resultant vector* of all those points:

    PLV = |mean(exp(i * phi_k))|     where phi_k = phase at onset on trial k

- **PLV = 0** means the phases are scattered uniformly around the circle. No preferred direction. No relationship between stimulation and phase.
- **PLV = 1** means every trial has the exact same phase at onset. Perfect phase-locking.
- **PLV = 0.25** means the phases cluster mildly around a preferred direction, but with substantial spread. Think of a compass needle that drifts toward north but wobbles a lot. There is a tendency, but it is weak.

PLV is **not** a percentage. It is not "25% of trials are locked." It is a continuous concentration measure on [0, 1].

**What the Rayleigh test means.** The Rayleigh test asks: "Could this degree of clustering have happened by chance if the phases were truly random?" The test statistic is z = n * PLV^2 = 83 * 0.0625 = 5.19. The p-value of 0.005 means there is only a 0.5% probability that 83 uniformly random phases would produce a PLV this large. The clustering is statistically real.

**But the Rayleigh test does not tell us the cause.** The phase concentration could be:
- Neural entrainment (the brain's oscillation phase-resets to the pulse)
- Electromagnetic artifact (the pulse resets the measured signal's phase)
- Volume conduction from the ground truth channel

This is why the 30% vs 100% comparison matters. If phase concentration tracks intensity, it strengthens the case for a real (artifact or neural) effect. If it persists at 30% where the artifact is negligible, it may be neural.

---

## The cTBS Protocol

**Source:** `ctbs_like_v1_amp5hz_mod50hz_triplets.py`

cTBS (continuous theta-burst stimulation) is a standard TMS protocol known to produce lasting changes in cortical excitability. Our TIMS version mimics its temporal structure:

- **Amplitude envelope:** 5 Hz sinusoid on both coils (A1, A2). This creates the theta-frequency modulation of stimulation intensity.
- **Modulation signal:** 50 Hz triplets -- three brief events at 0, 20, 40 ms within each 200 ms burst period. This is the high-frequency component.
- **Burst gating:** 2 s ON / 3 s OFF. Stimulation runs for 2 seconds, then pauses for 3 seconds.
- **Session duration:** 500 seconds total.

In the EEG, the stim channel will show dense activity during each 2 s ON block (many pulses from the 50 Hz triplets at 5 Hz), then silence for 3 s. The cycle repeats every 5 s.

---

## Decision Space

### What constrains us now

1. **exp05 is unanalyzed.** The 30% vs 100% comparison has not been run. We cannot make intensity-dependent claims until it is done.
2. **Phantom only.** exp05 is phantom data. We can characterize the artifact, but not neural effects. exp04 showed TEPs in a real person, but with a different protocol (50 Hz modulated pulse, not cTBS).
3. **SSD is weak.** Eigenvalues below 1 mean the ground truth signal is not dominant. Recovery metrics (coherence, PLV, SNR) will be modest even in the best case.
4. **The cTBS stim pattern is new.** Previous pipeline code was built for single-pulse paradigms with clear inter-onset intervals. cTBS has dense 50 Hz activity during ON blocks, requiring adapted onset detection logic.

### What we decide after exp05 analysis

- **If 30% produces negligible artifact:** 30% becomes the operating point for EEG-concurrent TIMS. Future human experiments use 30% cTBS with clean EEG.
- **If there is a gradient:** Map it more finely (10%, 20%, 30%, 40%, ...) in the next experiment. The `pytims` API makes this trivial -- change one number in the protocol script.
- **If SSD recovers ground truth at 30% but not 100%:** This confirms that artifact magnitude, not SSD quality, is the limiting factor. The cleaning pipeline is adequate; the stimulation intensity is the variable.
- **If SSD fails at both:** The subspace separation approach needs more work, or the phantom setup does not generate enough ground truth signal for meaningful recovery.

### What comes after

- **Next human experiment:** Apply cTBS at the sub-artifact intensity identified from exp05. Look for TEPs and/or entrainment effects in a real brain.
- **Dose-response curve:** Systematically vary intensity across experiments. One micro-experiment per intensity level. Aggregate into a dose-response function.
- **Waveform variation:** The `pytims` arbitrary signal API means we can test different modulation patterns (not just cTBS). Change the beat frequency, the burst rate, the ON/OFF ratio. Each variation is one micro-experiment.

---

## Pipeline Reference

**Core functions:** `preprocessing.py` (16 functions -- onset detection, filtering, epoching, coherence, SNR, recovery metrics)

**Plotting:** `plot_helpers.py` (18 functions -- PLV polar plots, ITPC time courses, topomaps, spectral summaries, triptych TEP figures)

**SSD:** `plot_helpers.run_ssd()` (line 54) -- GED-based spatial spectral decomposition. NOT MNE's built-in SSD. Uses `scipy.linalg.eig(COV_signal, COV_noise)` to find spatial filters maximizing signal/noise in the 10 Hz band.

**Script standard:** `SKRIPT.md` -- one script = one goal, constants at top, linear top-to-bottom, 70-150 lines, reuse existing functions, no hidden logic.

**Pipeline recipes:** `readme.md` -- step-by-step inline code for loading, onset detection, epoching, artifact removal, saving.
