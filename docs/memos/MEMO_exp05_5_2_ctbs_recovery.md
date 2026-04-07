# Memo 5.2: Exploring Recovering the Signal from cTBS

## Context

### Latest Shared Information
- Latest relevant memo: `MEMO_exp05_analysis.md`
- Inherited from that memo:
  - exp05 `ground_truth` is centered near `7.08 Hz`, not `10 Hz`
  - correct timing must come from the recorded `stim` channel
  - the earlier baseline-first SSD pass could produce an in-band baseline component, but transfer to stimulated runs drifted toward `~5.1 Hz`
- New relative to that memo:
  - this memo tests a stricter exploratory pass with `FC1` fixed as the scout channel
  - the signal band is narrowed to `GT peak ± 0.5 Hz`
  - the transfer comparison is simplified to baseline vs `30%` only
  - this stricter pass does not find any in-band baseline SSD component and falls back to all components

### Goal
- Check whether a simpler, narrower, FC1-centered SSD pass can recover the recorded cTBS signal strongly enough to support later ON/OFF extraction.
- Characterize whether the limiting problem is still transfer instability, or whether the baseline signal itself is already too weak for reliable recovery.

### New Information
- The measured GT peak remains stable at `7.080078 Hz`.
- With signal band `6.580078-7.580078 Hz`, no baseline SSD component peaks inside the target band.
- The selected fallback component peaks at `5.126953 Hz` in both baseline and `30%` late-OFF.
- `30%` late-OFF coherence and PLV increase sharply relative to baseline, but they do so on the wrong spectral mode.

## Constraint

### Key Constraints
- Constraint 1: `signal` The baseline target signal is weak enough that a narrow-band SSD search may return no valid in-band component.
- Constraint 2: `metric` Coherence and PLV can rise even when the selected component is spectrally wrong, so phase metrics alone are not sufficient.
- Constraint 3: `method` Late-OFF windows must stay inside real measured OFF gaps, which limits usable epoch duration and reduces training data quality.

### Decision Space
- Current input state:
  - baseline GT recording and `30%` cTBS recording are available
  - the target frequency is known from the recorded GT channel
  - exploratory figures and numeric summaries were generated in `EXP_05/explore_fc1_baseline_ssd/`
- Target output state:
  - a defensible claim that the cTBS signal can or cannot be recovered with the current SSD setup
  - a clear direction for the next recovery attempt
- What blocks the path from input to output:
  - weak baseline signal
  - no in-band SSD component under the stricter narrow-band criterion
  - elevated phase metrics on a component that remains centered at `~5.13 Hz`
- Which assumptions are currently load-bearing:
  - `FC1` is a reasonable fixed scout channel
  - GT peak measured from baseline is the right anchor for the target band
  - late-OFF windows are the least contaminated place to test transfer

### Actions Implemented

#### Action 1: Characterize the baseline target signal
- Question: Does the baseline recording show a plausible target-band signal in the candidate channels?
- Input:
  - baseline GT recording `exp05-phantom-rs-GT-cTBS-run02.vhdr`
  - candidate channels `FC1`, `P3`, `CP1`, `CP2`
- Transformation:
  - measure the GT peak from the recorded `ground_truth`
  - build `5 s` fixed-length baseline epochs
  - compute PSD and band-passed temporal views for the candidate channels
- Output:
  - baseline channel scout
- Key parameters / assumptions:
  - measured GT peak `7.080078 Hz`
  - signal band `6.580078-7.580078 Hz`
  - PSD view `5-15 Hz`
- Figure:
  - `EXP_05/explore_fc1_baseline_ssd/fig1_baseline_channel_scout.png`
- Result:
  - the target reference is present in the GT channel, but the scalp channels do not show a strong enough narrow-band expression to guarantee an in-band SSD component
- Local interpretation:
  - the signal characterization step already suggests that the baseline signal is near the edge of recoverability under the stricter band choice

![Figure 1: baseline channel scout](EXP_05/explore_fc1_baseline_ssd/fig1_baseline_channel_scout.png)

#### Action 2: Validate the usable timing windows
- Question: Are the `30%` ON and late-OFF windows valid under measured cTBS timing?
- Input:
  - `30%` recording `exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr`
  - recorded `stim` channel
- Transformation:
  - detect ON blocks from the raw `stim` channel
  - construct `30%` mid-ON and late-OFF windows
  - inspect the windows against the measured timing trace
- Output:
  - timing sanity figure
- Key parameters / assumptions:
  - `30%` mid-ON events: `63`
  - `30%` late-OFF events: `62`
  - late-OFF window must remain fully inside the next true OFF gap
- Figure:
  - `EXP_05/explore_fc1_baseline_ssd/fig2_timing_sanity.png`
- Result:
  - the timing windows are valid and stay inside measured ON/OFF structure
- Local interpretation:
  - the negative recovery result is not explained by invalid epoch placement

![Figure 2: timing sanity](EXP_05/explore_fc1_baseline_ssd/fig2_timing_sanity.png)

#### Action 3: Train baseline-first SSD and inspect transfer
- Question: Does a narrow-band baseline-trained SSD component stay aligned with the GT band in baseline and `30%` late-OFF?
- Input:
  - baseline pseudo-events: `313`
  - `30%` late-OFF events: `62`
  - EEG channels shared by baseline and `30%`
- Transformation:
  - train SSD on baseline pseudo-events
  - project the same filters onto baseline and `30%` late-OFF
  - select components by in-band peak first, then peak ratio, coherence, PLV, lambda
- Output:
  - selected-component transfer summary
- Key parameters / assumptions:
  - components searched: `6`
  - selection mode: `fallback_all_components`
  - selected component: `1`
  - lambda: `0.334864`
- Figure:
  - `EXP_05/explore_fc1_baseline_ssd/fig3_selected_component_summary.png`
- Result:
  - baseline peak frequency: `5.126953 Hz`
  - `30%` late-OFF peak frequency: `5.126953 Hz`
  - baseline coherence: `0.002090`
  - `30%` late-OFF coherence: `0.301090`
  - baseline PLV: `0.022409`
  - `30%` late-OFF PLV: `0.368383`
- Local interpretation:
  - the component is not tracking the measured GT band, even though the phase-based metrics rise in late-OFF

![Figure 3: selected-component summary](EXP_05/explore_fc1_baseline_ssd/fig3_selected_component_summary.png)

#### Action 4: Check time-frequency and phase consistency
- Question: Do the time-frequency and GT-locked phase views rescue the recovery claim?
- Input:
  - selected `30%` mid-ON and late-OFF component epochs
  - matched GT epochs
- Transformation:
  - compute TFR for the selected late-OFF component
  - compute GT-locked ITPC-like phase-consistency curves for ON and late-OFF
- Output:
  - TFR and phase-consistency figure
- Key parameters / assumptions:
  - ITPC epochs: ON `63`, late-OFF `62`
  - same narrow target band used for phase comparison
- Figure:
  - `EXP_05/explore_fc1_baseline_ssd/fig4_tfr_and_phase_consistency.png`
- Result:
  - the component shows structured time-frequency content and phase consistency, but this happens on the same `~5.13 Hz` mode already identified as spectrally wrong
- Local interpretation:
  - these views are useful diagnostics, but they do not overturn the spectral failure

![Figure 4: TFR and phase consistency](EXP_05/explore_fc1_baseline_ssd/fig4_tfr_and_phase_consistency.png)

## Trade-Off

### General Interpretation / Discussion
- This stricter memo adds a cleaner negative result than the previous exp05 SSD memo.
- In `MEMO_exp05_analysis.md`, the main failure mode was transfer drift: an in-band baseline component drifted toward `~5.1 Hz` after transfer.
- In this exploratory pass, the stricter narrow-band criterion exposes an even earlier problem: there is no acceptable in-band baseline component at all.
- That means the central difficulty is not only transfer instability. The baseline itself is too weak for this SSD setup to support a robust `~7 Hz` recovery claim.
- The rise in `30%` late-OFF coherence and PLV is therefore ambiguous. It is numerically real, but because the selected component remains centered at `5.126953 Hz`, those phase metrics are more consistent with residual structured artifact than with recovery of the intended GT signal.

### Options / Next Actions
- Option 1: Treat “no in-band component found” as a hard failure.
  - Why it helps: prevents phase-based metrics from making a wrong component look successful.
  - Trade-off: more runs will end with a negative result and no selected component.
- Option 2: Change the training data rather than the band.
  - Why it helps: a stronger baseline segment may improve the chance of getting a real in-band component.
  - Trade-off: adds another assumption about which baseline window is most representative.
- Option 3: Keep the current baseline windows but change the rejection logic.
  - Why it helps: explicit rejection of the persistent `~5.13 Hz` mode may isolate the actual artifact subspace.
  - Trade-off: requires extra method development before the next recovery test.

## Decision

### Decision Needed
- Decide whether the current cTBS recovery path should be considered a failed recovery attempt or an incomplete method-development step.

### Precise Questions for Review
1. Should we accept the conclusion that the current FC1-centered narrow-band SSD path does not recover the cTBS signal?
2. Should the next iteration treat “no in-band component found” as a hard stop instead of using fallback component selection?
3. Should the next recovery attempt focus first on a different baseline window, or on explicit rejection of the persistent `~5.13 Hz` mode?
