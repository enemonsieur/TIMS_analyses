# Memo 5.3: Should the Next Experiment Change the Ground Truth While Sweeping cTBS Intensity?

## Context

### Latest Shared Information
- Latest relevant memo: `MEMO_exp05_5_2_ctbs_recovery.md`
- Inherited from that memo:
  - the cTBS protocol itself is the normal `5 Hz` burst rhythm with `50 Hz` triplets
  - the recorded ground-truth signal in exp05 is near `7.08 Hz`
  - the current baseline-first SSD recovery path does not robustly recover the intended `~7 Hz` signal
  - stimulated data repeatedly show a wrong mode near `~5.13 Hz`, which is too close to the cTBS rhythm to be comfortable
- New relative to that memo:
  - the next experimental decision is whether to keep the current `7 Hz` ground truth or move it farther away from the cTBS stimulation rhythm
  - the same next experiment could also sweep cTBS intensity at `10-20-30-40-50%` using `.tims`

### Goal
- Decide whether the next experiment should use a programmable `.tims` protocol with cTBS intensities `10-20-30-40-50%`.
- Decide whether the ground truth should remain at `7 Hz` or be changed to better avoid cTBS-related artifact contamination.

### New Information
- The current exp05 problem is not just that recovery is weak. The recovered wrong mode sits near `5.13 Hz`, which overlaps too much with the fixed `5 Hz` cTBS rhythm.
- That makes the ground-truth choice an artifact-separation decision first, and only secondarily a signal-strength decision.

## Constraint

### Key Constraints
- Constraint 1: `artifact` The cTBS rhythm is fixed at `5 Hz`, so any recovered component near `5 Hz` is hard to interpret as clean ground-truth recovery.
- Constraint 2: `signal` The current `7 Hz` ground truth is not being robustly recovered with the present analysis path.
- Constraint 3: `method` The next experiment can vary intensity and ground truth, but the cTBS rhythm itself should stay fixed so the effect of ground-truth choice remains interpretable.

### Decision Space
- Current input state:
  - cTBS rhythm is fixed by protocol at `5 Hz`
  - current ground truth is `~7 Hz`
  - the next protocol can be programmed in `.tims` with multiple intensities
- Target output state:
  - a next experiment where the target rhythm is more clearly separable from cTBS artifact while still allowing a practical recovery test
- What blocks the path from input to output:
  - persistent contamination near the stimulation rhythm
  - weak and ambiguous recovery of the current `7 Hz` target
  - the risk of choosing a new ground-truth frequency that still sits too close to the stimulation artifact structure

### Actions Implemented

#### Action 1: Recovery-based artifact check
- Question: What does Memo 5.2 imply about the current `7 Hz` ground-truth choice?
- Input: `MEMO_exp05_5_2_ctbs_recovery.md`
- Transformation: reinterpret the failed recovery result in terms of spectral separation from cTBS artifact
- Output: decision anchor for the next ground-truth choice
- Key parameters / assumptions: GT `7.08 Hz`, fixed cTBS rhythm `5 Hz`, fallback mode `5.13 Hz`, no valid in-band SSD component in the stricter pass
- Figure: none
- Result: the stimulated recordings repeatedly emphasize a mode near the cTBS rhythm instead of the intended `7 Hz` target
- Local interpretation: the current design is not giving enough separation between the target we want to recover and the artifact structure we want to avoid

#### Action 2: Protocol feasibility check
- Question: Can the next experiment change intensity and ground truth while keeping the cTBS artifact source fixed?
- Input: `ctbs_like_v1_amp5hz_mod50hz_triplets.py`
- Transformation: inspect whether the protocol logic already supports keeping the normal cTBS structure while changing the rest of the design
- Output: feasibility claim for the next protocol step
- Key parameters / assumptions: cTBS stays `5 Hz` with `50 Hz` triplets and `2 s ON / 3 s OFF`; intensity is programmable through `.tims`
- Figure: none
- Result: the next experiment can sweep intensity while preserving the exact same cTBS rhythm
- Local interpretation: this makes it possible to test whether changing only the ground-truth frequency improves artifact separation

## Trade-Off

### General Interpretation / Discussion
- The next experiment should move to a programmable `.tims` intensity sweep at `10-20-30-40-50%`.
- The cTBS rhythm should remain fixed at the normal `5 Hz`.
- The key decision is the ground truth. The reason to change it is to avoid the artifact of the cTBS stimulation, not to change the cTBS protocol itself.
- Keeping ground truth at `7 Hz` keeps some separation from `5 Hz`, but exp05 shows that the recovered wrong mode still collapses toward the stimulation rhythm. That means the practical separation is not strong enough.
- A better next test is to move the ground truth farther away from `5 Hz`, not closer to it. A target such as `10 Hz` is cleaner because it increases spectral distance from the cTBS artifact source while leaving the cTBS pattern unchanged.
- Ground-truth frequencies near `5 Hz` should be avoided because they would make any recovery claim much harder to defend.

### Options / Next Actions
- Option 1: Keep ground truth at `7 Hz` and sweep intensity `10-20-30-40-50%`.
  - Trade-off: preserves continuity with exp05, but does not directly address the artifact-separation problem exposed by the `~5.13 Hz` fallback mode.
- Option 2: Change ground truth to `10 Hz` and sweep intensity `10-20-30-40-50%` while keeping cTBS at `5 Hz`.
  - Trade-off: gives cleaner separation from the cTBS artifact structure, but is no longer a strict continuation of the current `7 Hz` target.
- Option 3: Change ground truth closer to `5 Hz`.
  - Trade-off: worst choice for artifact interpretation and should be rejected.

## Decision

### Decision Needed
- Use a `.tims` cTBS intensity sweep in the next experiment, keep the cTBS rhythm fixed at `5 Hz`, and decide whether artifact avoidance is important enough to move the ground truth farther away from `5 Hz`.

### Precise Questions for Review
1. Do we agree that the primary reason to change the ground truth is to avoid cTBS stimulation artifact, not to modify the cTBS rhythm itself?
2. If yes, should the next experiment move the ground truth from `7 Hz` to `10 Hz` while keeping cTBS fixed at `5 Hz`?
3. Do we agree to reject any next design that puts the ground truth too close to `5 Hz`?
