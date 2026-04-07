# MEMO Template

## Rules

A memo in this repo is a decision document, not a diary and not a generic report.

Use it to:
- state the goal of the current work
- align with the latest shared information
- identify the key constraints blocking the goal
- document the actions that were actually implemented
- interpret the trade-offs
- end with precise decision questions

### Start from the latest shared information

Every new memo should begin from the latest relevant memo, not from first principles.

Rules:
- Link the latest relevant memo in `Latest Shared Information`.
- State what is inherited from that memo.
- State only the new information needed for the current memo.
- Do not re-explain TIMS, TMS, experiment history, or old background if a previous memo already established it.
- If there is no previous memo for that topic, then include the minimum background needed for the reader to understand the current memo.

### Keep the structure simple

Use only 4 top-level sections:
- `Context`
- `Constraint`
- `Trade-Off`
- `Decision`

### Write method/result blocks, not vague summaries

Inside `Actions Implemented`, each important action should say:
- question
- input
- transformation
- output
- figure
- result
- local interpretation

That means each action block should show how one input was transformed into one output, what parameters or assumptions mattered, what the figure shows, and what the result means.

### Keep constraints selective

Usually list at most 3 key constraints, optionally 4.

Constraint types can include:
- material
- method
- signal
- metric
- assumption
- mechanistic

Not every type needs to appear. Use only the constraint types that actually matter for the memo.

### End with decisions, not generic future work

The last section should make it easy to decide what to do next.

Good endings:
- choose option A, B, or C
- reject the current path
- request one more analysis
- change a method or assumption

Bad ending:
- “more work is needed”

### Do not do this

- Do not repeat old background if the previous memo already covers it.
- Do not dump figures without saying why each figure exists.
- Do not state a result without describing the transformation that produced it.
- Do not hide assumptions.
- Do not mix context, constraints, methods, and discussion into one block of text.

---

## Copy-Paste Skeleton

```md
# [Memo Title]

## Context

### Latest Shared Information
- Latest relevant memo: [link]
- Inherited from that memo:
- New relative to that memo:

### Goal
- What are we trying to achieve now?
- What output or decision do we want from this memo?

### New Information
- What is newly learned here that was not already established?
- Why does this new information matter for the current goal?

## Constraint

### Key Constraints
- Constraint 1: [type] [short statement]
- Constraint 2: [type] [short statement]
- Constraint 3: [type] [short statement]

### Decision Space
- Current input state:
- Target output state:
- What blocks the path from input to output:
- Which assumptions are currently load-bearing:

### Actions Implemented

#### Action 1: [short name]
- Question:
- Input:
- Transformation:
- Output:
- Key parameters / assumptions:
- Figure:
- Result:
- Local interpretation:

#### Action 2: [short name]
- Question:
- Input:
- Transformation:
- Output:
- Key parameters / assumptions:
- Figure:
- Result:
- Local interpretation:

## Trade-Off

### General Interpretation / Discussion
- What do the action-level results mean when considered together?
- Which constraints still dominate?
- What became clearer?
- What is still ambiguous or weak?

### Options / Next Actions
- Option 1:
  - Why it helps:
  - Trade-off:
- Option 2:
  - Why it helps:
  - Trade-off:
- Option 3:
  - Why it helps:
  - Trade-off:

## Decision

### Decision Needed
- What decision needs to be made now?

### Precise Questions for Review
1. [question with a concrete choice]
2. [question with a concrete choice]
3. [question with a concrete choice]
```

---

## Minimal Example Snippet

```md
#### Action 1: Characterize the target signal in baseline
- Question: Is the recorded target signal strong enough to justify SSD recovery?
- Input: baseline GT recording and candidate EEG channels
- Transformation: compute PSD, temporal, and spatial summaries around the measured target band
- Output: a baseline signal characterization figure
- Key parameters / assumptions: target frequency from recorded GT, not assumed from protocol
- Figure: `fig1_baseline_signal_characterization.png`
- Result: the target peak is present, but weak and spatially inconsistent
- Local interpretation: recovery may still be possible, but the weak baseline signal becomes a key signal constraint for all later SSD steps
```

## Minimal Decision Example

```md
### Precise Questions for Review
1. Should we keep the current SSD target band, or narrow it further around the measured GT peak?
2. Should we accept fallback component selection, or treat “no in-band component found” as a hard failure?
3. Should the next iteration spend effort on a different baseline window, or on a different scoring metric?
```
