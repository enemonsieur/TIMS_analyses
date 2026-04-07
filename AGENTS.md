## TIMS analysis agent notes (repo root)

These instructions apply to everything under this directory tree.

### Project structure (don’t assume a `src/` package)
- No `src/` directory in this repo.
- Reusable “core” code goes in: `preprocessing.py`, `plot_helpers.py`.

### Data conventions (stable)
- Inputs: BrainVision `*.vhdr` (+ `*.eeg`/`*.vmrk`).
- Framework: MNE (`mne.io.read_raw_brainvision`, `mne.EpochsArray(..., baseline=None, verbose=False)`).
- Shapes:
  - `epoch_signal(...)` -> `(n_epochs, n_samples)` + `time_axis_seconds` length `n_samples`
  - `epoch_multichannel(...)` -> `(n_epochs, n_channels, n_samples)`
- Units: process in Volts; convert to microvolts (`* 1e6`) only for plots/summary numbers.

### Before writing any code
1. Read the relevant standards and latest decision context first.
   - Start with `docs/standards/SKRIPT.md` and the latest relevant memo or `readme.md` entry.
2. Search for reusable logic in the core modules.
   - Prefer `rg -n "keyword" preprocessing.py plot_helpers.py`.
   - Reuse a helper only when it is non-trivial, already validated, and clearer than short MNE-native code.
   - Do not call a helper just because it exists.
3. Read the closest reference script and follow the scientific pattern when the question matches.
   - Match: windows, mask usage, channel picking, filter settings, naming, and I/O style.
   - Do not copy unrelated structure that would make one script answer more than one question.
4. Decide whether to extend an existing script or create a new one.
   - Extend only if the script still answers one narrow question after the change.
   - Otherwise split and create a new script.

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
- Naming rules.
  - Use descriptive names: `stim_onsets_samples`, `epoch_time_seconds`, `main_cut_window_s`.
  - Avoid ambiguous names like `d2`, `tmp`, `x1` unless they are loop indices.
- Naming alone is not enough where scientific choices matter.
  - Add comments for why windows, bands, channels, thresholds, and helper calls are scientifically justified.
- Analysis script size should follow `docs/standards/SKRIPT.md`.
  - Typical target: about `70-150` lines.
  - `300+` lines is not acceptable.
  - If repeated mechanics push a script beyond that range, move those mechanics into `preprocessing.py` or `plot_helpers.py`.

### Analysis script quality rules
Follow `docs/standards/SKRIPT.md` for all analysis script rules (layout, naming, comments, forbidden patterns, checklist).
- If any local rule in this file conflicts with `docs/standards/SKRIPT.md` for analysis-script design, follow `docs/standards/SKRIPT.md`.
- This file should keep repo-specific constraints only: data conventions, paths, output layout, reusable-module placement, and reporting expectations.

### Output directory
- Always write outputs into an explicit `output_directory` created via `mkdir(parents=True, exist_ok=True)`.

### Reporting changes (in the final message)
- Be surgical and specific: “changed X in `file.py:line` to fix Y” (not “fixed a bug”).
- Include a short accounting line:
  - `Lines: <approx added/modified> | Reused: <fn1(), fn2()> | New functions: <names or none> | Output: <dir or file>`

### Answer style rules (high priority)
- Follow `docs/standards/ANSWER.md` for coding-related responses.
- Use that style for explanations, debugging, implementation guidance, and review responses.
- Keep the repo-specific coding and script rules in this file as higher-order implementation constraints.
- Prefer this response pattern by default:
  - answer first
  - explain only what matters
  - show concrete code when relevant
  - end with verification, caveat, or next step
- `docs/standards/ANSWER.md` governs response structure and tone, not code implementation behavior.
- If `docs/standards/ANSWER.md` and `AGENTS.md` ever conflict, follow the repo-specific rules in `AGENTS.md`.
