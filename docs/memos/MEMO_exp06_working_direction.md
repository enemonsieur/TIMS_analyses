# Memo exp06: SSD Recovery Working Direction

## Context

### Latest Shared Information
- Latest relevant memo: [`MEMO_exp05_5_3_ctbs_intensity_decision.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO_exp05_5_3_ctbs_intensity_decision.md)
- Inherited from that memo:
  - exp05 showed that the earlier target was too close to the fixed stimulation rhythm to support a robust recovery claim
  - the recovery problem should be treated as an artifact-separation problem first, not as a physiology-interpretation problem
  - the next experiment should move the ground truth farther away from the `5 Hz` iTBS rhythm
- New relative to that memo:
  - exp06 should now be treated first as an SSD recoverability test
  - the working path is to reuse the exp05 SSD pipeline as the reference and adapt it to exp06 step by step

### Goal
- Determine whether exp06 supports a defensible baseline-trained SSD recovery path.
- Align today’s work around recoverability first, before artifact interpretation, intensity conclusions, or human TMS-EEG claims.

### New Information
- exp06 was designed to improve spectral separation between the stimulation rhythm and the target rhythm.
- That makes the first exp06 question narrower than the broader project question:
  can the intended target be recovered at all with a strict SSD pipeline?
- The immediate work therefore starts with baseline-only SSD characterization, not with transfer or interpretation.

## Constraint

### Key Constraints
- Constraint 1: `signal` The GT peak must be measured directly from the recorded `ground_truth` channel rather than assumed from the nominal protocol.
- Constraint 2: `method` The first exp06 pass stays limited to SSD recoverability and should not expand into physiology interpretation.
- Constraint 3: `sequence` Timing and transfer should only be analyzed after baseline SSD strength is established.
- Constraint 4: `scope` Human `100%` TMS-EEG interpretation is out of scope for this memo.

### Decision Space
- Current input state:
  - exp05 already established the need for a target farther from the stimulation rhythm
  - exp06 is the next recovery test
  - the exp05 SSD analysis is the nearest reusable reference
- Target output state:
  - a clear working direction for exp06 SSD analysis
  - an explicit first step that can succeed or fail cleanly
- What blocks the path from input to output:
  - jumping too early into intensity comparison or interpretation would mix timing, transfer, and spectral-selection failures
  - using phase metrics before spectral validity would make a wrong component look successful
- Which assumptions are currently load-bearing:
  - exp05 is the correct methodological reference
  - exp06 should be analyzed as a recoverability problem first

### Actions Implemented

#### Action 1: Define the exp06 working scope
- Question:
  - What should exp06 analysis prioritize first?
- Input:
  - `MEMO_exp05_5_3_ctbs_intensity_decision.md`
  - current exp06 SSD planning discussion
- Transformation:
  - reinterpret exp06 as the direct follow-up to the exp05 artifact-separation decision
- Output:
  - a narrowed working scope for exp06
- Key parameters / assumptions:
  - SSD recoverability comes before intensity interpretation
  - no human TMS-EEG framing in this memo
- Figure:
  - none
- Result:
  - exp06 is framed first as a baseline-trained SSD recovery problem
- Local interpretation:
  - this keeps success and failure interpretable

#### Action 2: Fix the analysis sequence
- Question:
  - In what order should exp06 SSD analysis be built?
- Input:
  - exp05 SSD workflow
  - current exp06 planning constraints
- Transformation:
  - split the SSD path into three narrow analysis scripts
- Output:
  - a concrete staged pipeline
- Key parameters / assumptions:
  - each script answers one question only
- Figure:
  - none
- Result:
  - the preferred sequence is:
    1. baseline-only SSD characterization
    2. timing and window validation
    3. baseline-trained transfer across intensities
- Local interpretation:
  - this avoids tuning SSD selection and timing logic at the same time

## Trade-Off

### General Interpretation / Discussion
- Keeping the scope narrow makes failure interpretable.
- If the baseline-only SSD step fails, later transfer results should not be over-read.
- If transfer is tested before baseline strength is established, a negative result would be ambiguous between poor target recovery, poor timing windows, and wrong component selection.
- Jumping directly to intensity comparison, TEP-like windows, or human interpretation would therefore mix multiple failure modes into one branch and weaken the scientific claim.

### Options / Next Actions
- Option 1: Start with baseline-only SSD characterization.
  - Why it helps:
    - gives the cleanest recoverability test
  - Trade-off:
    - does not yet answer the intensity question
- Option 2: Start with timing and transfer immediately.
  - Why it helps:
    - reaches intensity comparisons faster
  - Trade-off:
    - makes failure hard to interpret
- Option 3: Mix SSD recovery with broader interpretation.
  - Why it helps:
    - produces a broader narrative quickly
  - Trade-off:
    - too many moving parts for a defensible first exp06 memo

## Decision

### Decision Needed
- Use exp06 first as an SSD recoverability test and keep the analysis sequence strict.

### Precise Questions for Review
1. Do we agree that today’s exp06 priority is the baseline-only SSD step?
2. Do we agree that spectral validity comes before PLV, TLI, coherence, or other support metrics?
3. Do we agree that later stages should stop being over-interpreted if no in-band baseline SSD component is found?
