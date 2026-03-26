## TIMS analysis agent notes (repo root)

These instructions apply to everything under this directory tree.

### Project structure (don’t assume a `src/` package)
- No `src/` directory in this repo.
- Reusable “core” code goes in: `preprocessing.py`, `plot_helpers.py`, `util.py`.

### Data conventions (stable)
- Inputs: BrainVision `*.vhdr` (+ `*.eeg`/`*.vmrk`).
- Framework: MNE (`mne.io.read_raw_brainvision`, `mne.EpochsArray(..., baseline=None, verbose=False)`).
- Shapes:
  - `epoch_signal(...)` -> `(n_epochs, n_samples)` + `time_axis_seconds` length `n_samples`
  - `epoch_multichannel(...)` -> `(n_epochs, n_channels, n_samples)`
- Units: process in Volts; convert to microvolts (`* 1e6`) only for plots/summary numbers.

### Before writing any code
1. Search for an existing function first.
   - Prefer `rg -n "keyword" preprocessing.py plot_helpers.py util.py`.
   - If a function exists, call it. Do not re-implement it in a new script.
2. Read the closest reference script and follow its pattern exactly.
   - Match: epoching/cropping, mask usage, channel picking, filter settings, naming, and I/O style.
3. Modify the closest existing script instead of creating a new one.
   - Add a new file only if there is a clear “new analysis” that cannot fit as a small extension.

### When writing code
- Keep paths single-source and explicit.
  - Use `Path(r"...")` (Windows-style raw strings) for scripts intended to run with Windows Python.
  - No fallback paths, no auto-discovery, no interactive prompts, no silent try/except.
- Keep analysis scripts deterministic.
  - No “click to continue” flows unless the script is explicitly an interactive QC tool (e.g., manual ICA selection).
  - Prefer `verbose=False` on MNE I/O and processing unless debugging.
- Prefer “core module” placement for reusable logic.
  - If it’s used in more than one script, it goes into `preprocessing.py` or `plot_helpers.py`.
  - Helpers added to core should have clear names and explicit units in the signature (e.g., `window_start_s`, `sampling_rate_hz`).
- Naming rules (no comments required to understand the code).
  - Use descriptive names: `stim_onsets_samples`, `epoch_time_seconds`, `main_cut_window_s`.
  - Avoid ambiguous names like `d2`, `tmp`, `x1` unless they are loop indices.
- Code size guardrails (for new code you add).
  - New standalone scripts: hard limit 70 lines; if you exceed, move logic into `preprocessing.py`.
  - New helper functions: hard limit 40-100 lines; split if longer.

### Analysis script quality rules (high priority)
- Prefer readable scripts over generic abstractions.
  - The script must read top-to-bottom as one clear analysis story.
  - Keep the main scientific logic inline if it is specific to this script and helps readability.
  - Do not turn every transformation into a function.
  - Extract a helper only if at least one of these is true:
    - the code is reused or will clearly be reused
    - the code is repetitive plumbing, not the scientific core
    - keeping it inline would make the main script harder to follow
- Required script layout.
  - Use this order unless there is a strong reason not to:
    1. fixed inputs / config
    2. load data
    3. channel selection
    4. event or onset construction
    5. epoch construction
    6. shared preprocessing
    7. averaging / metrics
    8. plotting / saving
    9. short printed summary
- Comments are required and must be surgical.
  - Use section headers for every major block.
  - Add short comments for:
    - why a hard-coded number exists
    - what a non-obvious transformation is doing
    - why a channel or timing choice is being used
  - Do not add filler comments that restate obvious Python syntax.
  - A good comment explains intent, not mechanics.
- Hard-code fixed paradigm values unless there is a real need to vary them.
  - Do not promote every timing constant into a top-level parameter.
  - Keep only true edit points in the config block:
    - input paths
    - output directory
    - fixed bad-channel list
  - Fixed paradigm values may stay inline with a comment if they are stable for that script.
  - Avoid parameter spam.
- Keep repeated MNE construction compact.
  - Repeated `mne.Epochs(...)` calls may be written on one line if the arguments are identical and this improves scanability.
  - Prefer direct, compact construction over verbose multi-line boilerplate when nothing is gained from expansion.
- What belongs in helpers.
  - Reusable event-building logic belongs in `preprocessing.py`.
  - Reusable plotting/layout logic belongs in `plot_helpers.py`.
  - Script-specific onset detection, masking decisions, and one-off cleaning choices stay inline unless reuse is clear.
- Forbidden patterns in final scripts.
  - No notebook leftovers.
  - No large commented-out code blocks.
  - No stray debug calls like `plt.show()` unless the script is explicitly interactive.
  - No unexplained magic numbers.
  - No fallback branches, prompts, or auto-discovery.
  - No dead experimental branches in the final saved script.
- Quality bar before finishing.
  - Check that the script is easy to read top-to-bottom.
  - Check that comments explain all non-obvious hard-coded choices.
  - Check that helper extraction is minimal and justified.
  - Check that syntax compiles.
  - If the task asked for a clean duplicate, leave the original exploratory script untouched.

### Output directory
- Always write outputs into an explicit `output_directory` created via `mkdir(parents=True, exist_ok=True)`.

### Reporting changes (in the final message)
- Be surgical and specific: “changed X in `file.py:line` to fix Y” (not “fixed a bug”).
- Include a short accounting line:
  - `Lines: <approx added/modified> | Reused: <fn1(), fn2()> | New functions: <names or none> | Output: <dir or file>`

### Answer style rules (high priority)
- Follow `ANSWER.md` for coding-related responses.
- Use that style for explanations, debugging, implementation guidance, and review responses.
- Keep the repo-specific coding and script rules in this file as higher-order implementation constraints.
- Prefer this response pattern by default:
  - answer first
  - explain only what matters
  - show concrete code when relevant
  - end with verification, caveat, or next step
- `ANSWER.md` governs response structure and tone, not code implementation behavior.
- If `ANSWER.md` and `AGENTS.md` ever conflict, follow the repo-specific rules in `AGENTS.md`.
