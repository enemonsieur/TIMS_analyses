# MEMO: exp06 Run02 ON Artifact Filtering

## Context

### Latest Shared Information
- Latest relevant memo: [`MEMO_exp06_run02_artifact_filtering.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO_exp06_run02_artifact_filtering.md)
- Inherited from that memo:
  - late-OFF transfer is already a positive reference condition for exp06 because the saved baseline SSD stays at the `12.451172 Hz` target and remains near-ceiling GT-locked across the full `10-20-30-40-50%` run02 sweep
  - spectral validity still has to carry the main recoverability claim, with GT-locking used as a support metric rather than as the main proof
  - the run02 timing readout depends on the lowered STIM detector threshold `0.08`, which recovers the weak first block without collapsing the five-block structure
- New relative to that memo:
  - the current ON analysis is no longer a frozen baseline-to-ON transfer test; the SSD is now refit inside each accepted ON block and then ranked against recorded GT
  - under this ON-fitted design, the recovered SSD stays spectrally in-band in `4/5` ON blocks rather than failing in all five
  - ON GT-locking is strong at `10-30%` but collapses sharply at `40-50%`, while late-OFF remains stable and near ceiling

### Goal
- The aim of this memo is to place the run02 ON result back into a coherent exp06 story.
- The earlier ON memo effectively read the experiment as a failure of baseline-to-ON transfer. That is no longer the right question for the current pipeline. We now fit SSD inside each accepted ON block, select the component against recorded GT, and ask a more useful study question: under actual stimulation, at which intensities does the oscillatory target remain recoverable enough to justify further work, and where does the artifact state start to dominate the interpretation?
- The practical goal is therefore not just to report another figure, but to decide whether the ON condition contains a meaningful low-intensity operating range and whether the remaining failures are better understood as a hard limit of recoverability or as the signature of an artifact process that still needs to be modeled explicitly.

### New Information
- The accepted ON interior remains `0.3-1.5 s` after measured onset, inside a median ON duration of `1.922 s`.
- The ON-fitted SSD keeps the recovered peak inside the target band at `10%`, `20%`, `30%`, and `40%`, but not at `50%`.
- Mean SSD GT-locking from the exported ON ITPC curves is:
  - `10%`: `0.966127`
  - `20%`: `0.979165`
  - `30%`: `0.969796`
  - `40%`: `0.500371`
  - `50%`: `0.623798`
- Raw `O2` remains highly GT-locked during ON at `40-50%`, but the ON-fitted SSD loses its advantage there:
  - `40%`: raw `0.995982`, SSD `0.500371`
  - `50%`: raw `0.999522`, SSD `0.623798`
- Late-OFF remains the clean positive reference:
  - recovered peak stays at `12.451172 Hz` in all five blocks
  - SSD mean GT-locking stays near ceiling in all five blocks: `0.998332-0.999526`

## Constraint

### Key Constraints
- Constraint 1: `sequence` ON recoverability must still be judged first by spectral identity, then by GT-locking support.
- Constraint 2: `method` the current ON claim is about block-specific ON-fitted SSD, not about stability of a frozen baseline filter.
- Constraint 3: `mechanistic` the ON state likely contains a short artifact decay / recovery regime that is not yet explicitly modeled, so a single ON summary window may mix cleaner and less stable sub-periods.

### Decision Space
- Current input state:
  - run02 provides five measured ON dose blocks and their matched OFF intervals
  - late-OFF already gives a memo-backed positive reference condition
  - ON analysis now uses per-block SSD fits on accepted ON interiors, with GT-based component ranking
- Target output state:
  - a memo-backed interpretation of what the current ON result does and does not justify for exp06
- What blocks the path from input to output:
  - strong ON GT-locking at low intensity is encouraging, but it drops abruptly at high intensity instead of degrading gradually
  - the current outputs summarize each ON block well, but they do not yet estimate the within-block decay constant, recovery time, or spatial source pattern of the residual artifact
- Which assumptions are currently load-bearing:
  - `threshold_fraction=0.08` is still the correct timing setting for this run
  - `0.3-1.5 s` is a reasonable compromise window: far enough from the onset edge to reduce the largest artifact transient, but still representative of the ON state
  - the measured baseline GT peak `12.451172 Hz` remains the right reference for ON band definition

### Actions Implemented

#### Action 1: Define the measured ON decision window

**Methods**
- Question:
  - Does run02 contain five measurable ON dose blocks with a stable interior segment long enough for an ON-specific SSD fit?
- Input:
  - `exp06-STIM-iTBS_run02.vhdr`
  - recorded `stim` trace
- Transformation:
  - detect ON blocks directly from the measured STIM trace with `threshold_fraction=0.08`
  - keep the known five-block `10-20-30-40-50%` structure with `20` cycles per block
  - shift the accepted ON analysis window to `0.3-1.5 s` after measured onset so the strongest onset-edge artifact is excluded
- Output:
  - `EXP06/exp06_run02_on_timing.png`
- Key parameters / assumptions:
  - detector threshold fraction: `0.08`
  - accepted ON window: `0.3-1.5 s`
  - median ON duration: `1.922 s`
  - cycle count per block: `20`
- Figure:
  - `../../EXP06/exp06_run02_on_timing.png`

**Results**
- All five dose blocks are recovered, and each contributes the full `20` accepted ON windows.
- The ON window is therefore not a sparse or truncated subset; it samples a consistent interior segment from each dose block.

**Local interpretation**
- This timing step matters because it makes the whole ON comparison readable. We are not comparing arbitrary fragments of stimulation blocks or a subset that changes with intensity. We are comparing the same measured interior segment of each dose block, with the same event count, under one explicit timing definition.

#### Action 2: Test whether an ON-fitted SSD remains spectrally valid across intensity

**Methods**
- Question:
  - If SSD is fit inside each accepted ON block rather than transferred from baseline, does the selected component stay tied to the measured GT band?
- Input:
  - retained run02 EEG channels with `stim`, `ground_truth`, and excluded channels removed
  - accepted ON windows from Action 1
  - recorded GT reference peak `12.451172 Hz`
- Transformation:
  - fit SSD separately inside each ON block
  - use a narrow signal band centered on the measured GT peak: `11.951172-12.951172 Hz`
  - rank candidate components against recorded GT using in-band coherence plus peak-to-flank ratio
  - compute matched-epoch peak-normalized PSD summaries in the broader `4-20 Hz` inspection band
- Output:
  - `EXP06/exp06_run02_on_art_filtering_psd_panels.png`
  - `EXP06/exp06_run02_on_art_filtering_summary.txt`
- Key parameters / assumptions:
  - signal band: `11.951172-12.951172 Hz`
  - view band: `4.0-20.0 Hz`
  - `6` SSD components maximum before GT-based ranking
  - ON-specific fit is justified here because the ON state is the object of interest, not transfer stability from baseline
- Figure:
  - `../../EXP06/exp06_run02_on_art_filtering_psd_panels.png`

![run02 ON PSD panels](../../EXP06/exp06_run02_on_art_filtering_psd_panels.png)

**Results**
- The selected ON-fitted SSD is spectrally in-band in `4/5` dose blocks.
- Recovered peak frequencies are:
  - `10%`: `12.695312 Hz`
  - `20%`: `12.695312 Hz`
  - `30%`: `12.695312 Hz`
  - `40%`: `12.695312 Hz`
  - `50%`: `11.718750 Hz`
- The `40%` and `50%` blocks also show weaker component quality scores than `10-30%`, even before GT-locking is interpreted:
  - coherence falls to `0.234314` at `40%` and `0.392378` at `50%`
  - peak ratio falls below `1.0` at `40%` and `50%`

**Local interpretation**
- This is the main reason the earlier negative reading has to be softened. Once the SSD is allowed to adapt to the ON state itself, the target band is no longer lost in every block. At the same time, the component-quality scores show that the higher-intensity ON blocks are not simply weaker versions of the low-intensity case. They look qualitatively less stable, which is important because it shifts the interpretation from "no ON recovery" toward "ON recovery is conditional and breaks at higher intensity."

#### Action 3: Summarize ON GT-locking across the five stimulation levels and contrast it with late-OFF

**Methods**
- Question:
  - Once the ON-fitted component is selected, how much GT-locked phase structure remains across the five ON levels, and how does that compare with the already validated late-OFF reference?
- Input:
  - selected ON-fitted SSD epochs
  - matched GT epochs
  - raw `O2` epochs for comparison in the ON summary
  - exported ON ITPC curves from `EXP06/exp06_run02_on_itpc.npz`
  - late-OFF summary from `EXP06/exp06_run02_art_filtering_summary.txt`
- Transformation:
  - band-pass GT and EEG in the target band
  - compute Hilbert phase and the cross-epoch GT-locking curve
  - reduce each ON curve to one mean GT-locking value for the five-level summary figure
  - compare those ON values with the raw `O2` ON summary and with the late-OFF reference condition
- Output:
  - `EXP06/exp06_run02_on_art_filtering_itpc_summary.png`
  - `EXP06/exp06_run02_on_mean_gt_locking.png`
  - late-OFF reference figure: `EXP06/exp06_run02_art_filtering_itpc_summary.png`
- Key parameters / assumptions:
  - GT-locking is still a support metric, not the primary validity criterion
  - the mean summary is computed directly from the exported ON ITPC curves, so the five-point figure is a reduction of the measured ON time courses rather than a separate metric
- Figure:
  - `../../EXP06/exp06_run02_on_mean_gt_locking.png`

![run02 ON mean GT-locking](../../EXP06/exp06_run02_on_mean_gt_locking.png)

**Results**
- ON-fitted SSD mean GT-locking is very high at low and mid intensities:
  - `10%`: `0.966127`
  - `20%`: `0.979165`
  - `30%`: `0.969796`
- ON-fitted SSD GT-locking drops sharply at higher intensities:
  - `40%`: `0.500371`
  - `50%`: `0.623798`
- Relative to raw `O2`, the ON-fitted SSD is better at `10-30%` but worse at `40-50%`:
  - SSD minus raw `O2`: `+0.123099`, `+0.069493`, `+0.029277`, `-0.495611`, `-0.375724`
- Relative to late-OFF, the ON state is much less stable:
  - late-OFF SSD mean GT-locking remains `0.998332-0.999526` across the whole sweep
  - late-OFF keeps the target peak in all five blocks, while ON fails the band check at `50%`

**Local interpretation**
- Read together, the GT-locking results do not support a simple all-or-none conclusion. The low and mid intensities look genuinely encouraging: the recovered component remains in band and the GT-locking stays high enough to make phase-tracking plausible. The higher intensities behave differently. The drop is too abrupt to read as a smooth monotonic weakening of the same process, and it is more naturally read as evidence that the ON state contains an additional transient or decay regime that our current summary window is still mixing into the measurement. That idea is still a hypothesis, but it fits the shape of the result better than the older "pure failure" interpretation.

## Trade-Off

### General Interpretation / Discussion
- The cleanest way to read the full exp06 result is now as a state-by-intensity story. Late-OFF remains the stable positive reference: the target frequency is preserved, GT-locking is near ceiling, and the baseline-trained transfer still behaves like a valid recoverability result. ON is different. It is no longer fair to describe it as a uniform failure, because the low- and mid-intensity blocks clearly retain useful structure. But it is also not yet a general success, because the behavior changes sharply once the stimulation gets stronger.
- That sharp change is the most informative part of the study. If the ON artifact were simply a steady contamination that scaled smoothly with intensity, the expectation would be a gradual worsening. Instead, the present figures suggest that the ON period contains a short-lived decay or recovery process that intrudes differently across the dose sweep. In other words, the current five-level summary looks less like a smooth loss of signal and more like a mixture of recoverable oscillatory structure plus an unmodeled transient artifact process.
- This is why artifact modeling now becomes central rather than optional. The next step is not merely to improve a figure; it is to estimate and subtract the decay in phantom data well enough that the same model can later be challenged on real brain recordings. If that works, it gives us a principled route toward seeing whether TEP-like structure survives stimulation after artifact removal instead of only asking whether SSD can still follow GT.
- Template subtraction should be kept in the same conversation. TIMS artifacts are stereotyped enough that direct template-based denoising may remove noise that SSD-based recovery alone cannot handle. That does not replace the current SSD result; it complements it by attacking the artifact itself rather than only optimizing signal recovery around it.
- The later return to `exp04` baseline before/after should then be treated as a biological review step, not as a clean confirmatory endpoint. Once the artifact behavior is better constrained, `exp04` becomes the place to ask which apparent brain effects are robust, which are weak but still interesting, and which are more likely false positives created by residual contamination.
- The study therefore points to a clear trade-off. The low-intensity ON range is already promising enough to justify further recovery and denoising work. Stronger claims about real brain responses, however, should wait until the artifact process is modeled explicitly enough to separate decay dynamics from plausible neural signals.

### Options / Next Actions
- Option 1: treat `10-30%` ON as the current positive zone and keep `40-50%` as outside the reliable recoverability range for now.
  - Why it helps:
    - it matches the present figures and keeps the claim conservative
  - Trade-off:
    - it leaves the mechanism of high-intensity failure unresolved
- Option 2: model and remove the ON decay explicitly before applying the approach to real brain data.
  - Why it helps:
    - it directly tests the emerging mechanistic explanation and creates the artifact-removal path needed before looking for TEPs in real data
  - Trade-off:
    - it is a new analysis question and needs time-resolved, possibly channel-wise modeling rather than only block summaries
- Option 3: test template-subtraction denoising as a complementary artifact-removal method.
  - Why it helps:
    - it uses the stereotyped TIMS artifact directly and may remove noise even when GT recovery alone is not sufficient
  - Trade-off:
    - template subtraction still needs validation against over-subtraction and signal loss
- Option 4: review `exp04` baseline before/after with the improved artifact perspective to identify brain effects worth deeper follow-up.
  - Why it helps:
    - it turns the artifact work into a biological screening step and helps decide which weak or noisy effects still deserve exploration
  - Trade-off:
    - that review may surface many tentative or false-positive leads, so it should be framed as hypothesis generation rather than confirmation

## Decision

### Decision Needed
- Update exp06 ON interpretation from a blanket negative transfer story to a more precise study conclusion: ON recovery appears genuinely plausible at low and mid intensity, but the higher-intensity ON state is still entangled with an unmodeled decay / recovery artifact process that has to be addressed before stronger physiological claims are justified.

### Precise Questions for Review
1. Should exp06 now treat `10-30%` ON as the memo-backed positive range for GT-related phase tracking, while keeping `40-50%` outside the claim?
2. Should the next obligatory analysis step be explicit decay modeling and subtraction in phantom data before any real-brain TEP claim is attempted?
3. Should template subtraction be run in parallel with SSD-based recovery as a dedicated TIMS denoising path rather than only as a later backup option?
4. Once the artifact-removal path is clearer, should the next biological review focus on `exp04` baseline before/after as a broad scan for weak but potentially meaningful brain effects?
