# Pass 1 Review

Target script: `evidence/skript_probe_pass1.py`

## Findings

1. `evidence/skript_probe_pass1.py:24-29`
   The script hard-codes the analysis channel, continuous window, PSD epoch length, and filter band without explaining why those choices fit this dataset or question. `SKRIPT.md` said to comment non-obvious hard-coded values, but that instruction was still too easy to skip.

2. `evidence/skript_probe_pass1.py:62-68`
   The script checks that `VIEW_WINDOW_S` is positive, but it does not assert that the full window fits both recordings before slicing. This is a real failure mode: the comparison could silently truncate and still produce a figure.

3. `evidence/skript_probe_pass1.py:13-14`
   The script needed a repo-root `sys.path` insertion because it lives under `evidence/`. `SKRIPT.md` did not tell the writer how to import shared helpers from subfolders, so the rule had to be inferred.

## What Worked

- The goal stayed narrow.
- The script was readable top-to-bottom.
- It reused `preprocessing.filter_signal()` instead of re-implementing filtering.
- It created an explicit output directory and produced deterministic outputs.
- It included sanity-check prints and ran successfully with the Windows Python + `mne` environment.

## Pass 2 Doc Changes

- Added the explicit subfolder-helper import rule.
- Tightened the comments section so hard-coded channels, windows, bands, and thresholds need a short reason.
- Tightened validation so slice bounds must be checked before slicing.
