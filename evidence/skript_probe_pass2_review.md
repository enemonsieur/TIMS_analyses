# Pass 2 Review

Target script: `evidence/skript_probe_pass2.py`

## Findings

1. `evidence/skript_probe_pass2.py:25-29`
   The config block still leaves most interpretation-driving constants unexplained. `WINDOW_START_S`, `VIEW_WINDOW_S`, `PSD_EPOCH_DURATION_S`, `PSD_RANGE_HZ`, and `FILTER_RANGE_HZ` are all real analysis choices, but only the channel choice is commented later. The doc needed to say more clearly that config-level scientific constants need their reason where they are defined or first used.

2. `evidence/skript_probe_pass2.py:33-34`
   The script still emits repeated BrainVision warnings on every run. They do not break the result, but they make the runtime noisy and bury the real sanity-check prints. `SKRIPT.md` did not yet say that avoidable warning noise should be cleaned up or explicitly acknowledged.

## What Improved

- Slice bounds are now checked before slicing.
- The script is still narrow, linear, and readable.
- Shared helper reuse is still correct.
- Outputs are explicit and deterministic.

## Pass 3 Doc Changes

- Added a stronger rule that config constants driving interpretation need a local reason comment.
- Added runtime cleanliness to the validation checklist so avoidable warnings are part of the script review.
