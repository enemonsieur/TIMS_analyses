# SKRIPT: Readable Analysis Script Standard (TIMS Repo)

This guide defines how to write analysis scripts that are easy to read, easy to modify, and grounded in existing TIMS code.

## 1) Scope and line budget

- One script = one narrow analysis goal.
- The script can generate multiple outputs, but all outputs must serve the same single goal.
- Exploratory scripts can be `100-150` lines when readability benefits from explicit steps.
- Do not change pipeline invariants without explicit sign-off (event IDs, epoch windows, preprocessing rules).

## 2) Hard exploratory script contract

- Default shape is linear top-to-bottom code: `constants -> load -> analyze -> save`.
- No local `def` blocks unless unavoidable.
- "Unavoidable" means one of:
  - the block is reused in this same file at least twice
  - the block is more than 10 lines and hurts scanability if kept inline
  - the block has edge-case handling that is clearer as one named unit
- If it is reusable across scripts, put it in `preprocessing.py`, `plot_helpers.py`, or `util.py` instead of local helpers.

## 3) SKRIPT acronym (TIMS version)

- `S` Single purpose: one narrow question/goal.
- `K` Keep constants at top: all tunable values in one block.
- `R` Reuse existing TIMS code first: search `preprocessing.py`, `plot_helpers.py`, `util.py`, and prior scripts.
- `I` Inline when tiny: if logic is 2-5 lines and used once, keep it inline.
- `P` Promote repeated logic: move reused or heavy logic into core modules.
- `T` Track outputs clearly: deterministic filenames, explicit output directory, concise status prints.

## 4) Preferred script skeleton

```python
"""One-line purpose."""
from pathlib import Path
import ...
import preprocessing
import plot_helpers

# constants
STIM_VHDR_PATH = Path(r"...")
BASELINE_VHDR_PATH = Path(r"...")
OUTPUT_DIRECTORY = Path(r"...")
...

# load
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
raw = ...

# analyze
...

# save/report
fig.savefig(OUTPUT_DIRECTORY / "figure_name.png", dpi=200)
print("Saved", OUTPUT_DIRECTORY / "figure_name.png")
```

Section order:
1. docstring
2. imports
3. constants
4. load/prepare
5. analysis
6. save/report

## 5) Reuse hierarchy (mandatory)

Before writing new logic, check in this order:

1. `preprocessing.py`
2. `plot_helpers.py`
3. `util.py`
4. Closest existing analysis script in repo root

If functionality exists, call it directly.
If it does not exist and is reusable, add it to a core module (do not copy/paste algorithms across scripts).

## 6) Readability and comments

- Use descriptive names: `stim_onsets_samples`, `epoch_time_seconds`, `postpulse_window_s`.
- Avoid opaque names unless standard (`sfreq`, `fig`, `ax` are fine).
- Add comments for complicated or non-obvious blocks.
- Do not comment obvious line-by-line mechanics.
- Write comments as "why this step exists" and "what assumption is being used".
- Keep one way to do one task; remove dead branches and duplicate paths.
- Prioritize easy modification over clever abstraction.
- Hard-code a value only when it is stable for that script or used once in a very local block.
- If a value might need adjustment, keep it somewhere easy to find and modify instead of burying it inside a long helper.

## 7) Paths, outputs, and data conventions

- Use explicit Windows-style paths via `Path(r"...")`.
- No fallback paths, no auto-discovery, no interactive prompts.
- Always define and create `output_directory` explicitly with `mkdir(parents=True, exist_ok=True)`.
- Keep processing in Volts; convert to microvolts (`* 1e6`) only for plotting/reporting.
- Keep array-shape expectations explicit where useful.

## 8) Inline vs helper rule

Keep inline when all are true:
- 2-5 lines
- used once
- obvious and local

Move to helper/core when any are true:
- copied into a second script
- more than 8-10 lines and conceptually one unit
- has edge-case handling
- makes the main script harder to scan
- but do not hide core scientific logic in a long or obscure helper just because it is possible to do so

## 9) Forbidden patterns

- Mixed analyses in one file (multiple unrelated goals).
- Hidden defaults spread across the file.
- Interactive prompts in deterministic analysis scripts.
- Silent `try/except` that hides errors.
- Re-implementing logic that already exists in `preprocessing.py`, `plot_helpers.py`, or `util.py`.
- Over-functionalizing tiny one-off logic into many small local functions.
- Hiding key analysis choices inside long helper functions without first reading and understanding what they do.
- Calling a large reusable helper as a black box when the scientific logic should be visible in the script.
- Ambiguous variable names (`data2`, `tmp3`, `x1`) outside loop indices.
- Dead code paths and commented-out legacy branches left in final scripts.

## 10) Output and reproducibility checklist

Before finalizing a script:

- Goal is narrow and clearly stated in the docstring.
- Constants are easy to find and edit.
- Existing core functions were reused where possible.
- Outputs are explicit and deterministic.
- Script runs end-to-end with current paths.
- No duplicated algorithm blocks that belong in core helpers.
- Test the script step by step while building it: validate loading, onset/event logic, epoch shapes, and output saving in sequence instead of writing the whole script first and debugging everything at once.
- Large helpers used by the script were explored first, so no important analysis decision is hidden by accident.
