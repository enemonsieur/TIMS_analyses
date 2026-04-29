# SKRIPT: Readable Analysis Script Standard

Use this guide for analysis scripts in this repo. The target is code a human can read once and understand without opening helper internals.

## 1. Before You Write: Validate the Approach First

**Always present the pseudo-code skeleton before writing real code—even if not asked.**

1. Ask `3-7` short questions to clarify:
   - the single goal
   - the windows / conditions
   - the outputs
   - whether the script is exploratory or closer to a final report

2. **Write the pseudo-code high-level sketch inline in the conversation** (not in a document):
   - Show the pipeline overview (visual box drawing)
   - Show the main algorithm steps (numbered sections)
   - Show expected inputs/outputs at each step
   - Keep it brief (5-10 lines of structure)

3. **Ask the user to validate** before proceeding:
   - "Does this approach match what you want?"
   - "Should we change the order / skip any steps?"
   - "Are the outputs what you expected?"

4. **Only after validation:** write the full pseudo-code + real script.

**Why:** A misaligned skeleton catches errors early. If the approach is wrong, you stop before wasting effort on full implementation.

### 1.1 DRIL before trust-sensitive scripts

If the requested script depends on a method that could create the result being
interpreted, do not treat the method as a black box. Propose a DRIL first; see
[`DRIL.md`](DRIL.md).

Use this especially for filtering, smoothing, Hilbert phase, decomposition,
baseline correction, interpolation, fitting, thresholding, joins, and
aggregation. The DRIL should execute one raw input through one transformation
before the script turns the output into evidence.

## 1.5 High-Level Sketch Example (for chat validation)

When proposing a new script, show the skeleton briefly (inline):

```
GOAL: Identify best raw channel via phase locking; compare raw vs. cleaned paths.

PIPELINE:
  1. Load VHDR + extract stim/GT/EEG (250 Hz)
  2. Detect blocks → build ON-window event array
  3. Loop per block: band-pass 12 Hz → Hilbert phase → PLV per channel
  4. Select best channel at 10%, lock for 20–50%
  5. Extract & concatenate cycles, visualize overlays
  
OUTPUT: 
  - summary.txt (PLV per channel × intensity)
  - overlay.png (5-panel figure: channel vs GT)

QUESTIONS:
  - Lock channel, or reselect per intensity?
  - Compare vs. cleaned channels (SASS/SSD) in same script, or separate?
```

**Wait for validation before writing full pseudo-code.**

---

## 2. Core Rules

- One script = one narrow analysis question.
- The first line must say what question the script answers.
- The config block must show the important choices clearly.
- Use explicit `Path(r"...")` paths and an explicit `output_directory`.
- No fallback paths, auto-discovery, or interactive prompts in deterministic scripts.
- Typical script: about `70-150` lines.
- `300+` lines is not acceptable.
- Never compress code just to make the file shorter.
- After the script works, do a second cleanup pass and remove defensive
  scaffolding that is no longer helping readability.

Good:

```python
"""Compare baseline vs stim Cz with one time-window plot and one PSD summary."""
```

Bad:

```python
"""Analysis script."""
```

Second-pass cleanup means:

- remove temporary exploratory prints
- remove extra `if` branches that only guarded earlier uncertainty and are no
  longer needed
- remove `try/except`, warning-catching, fallback logic, or verbose error
  handling when the script is now stable and those branches only make the main
  path harder to follow
- keep checks that still protect a real scientific assumption, file-format
  contract, or a likely failure mode that would otherwise silently corrupt the
  result

The goal is a script whose final version reads like the actual analysis path,
not like a debugging session that happened to work.

## 3. Default Script Shape

Default order:

1. one-line purpose
2. imports
3. config
4. load and prepare
5. analysis
6. save and short report

Inside the analysis body, default to 3 blocks:

1. build windows / events
2. compute the main metric or selection
3. save figures + summary

Use visible section markers with clear hierarchy:

```python
# ============================================================
# 1) LOAD RECORDING
# ============================================================

# 1.1 Read BrainVision file

# keep accepted windows
```

Good script flow:

```python
# ============================================================
# CONFIG
# ============================================================
...

# ============================================================
# 1) LOAD RECORDING
# ============================================================
...

# ============================================================
# 2) BUILD WINDOWS
# ============================================================
...

# ============================================================
# 3) COMPUTE METRIC
# ============================================================
...

# ============================================================
# 4) SAVE OUTPUTS
# ============================================================
...
```

Bad script flow:

```python
# load
...
# some plots
...
# more loading
...
# selection
...
# another unrelated figure
```

### Config variables

Each variable or group of related variables in the config block should have a short inline or above comment explaining its purpose. One line is enough. These are structural comments — they guide the eye, not explain the code.

Good:

```python
VIEW_START_S = 2.0      # skip startup transients
VIEW_DURATION_S = 20.0  # enough to spot unstable channels
VIEW_BAND_HZ = (1.0, 40.0)  # view filter; keeps drifts and broadband visible
EXCLUDED_CHANNELS = {"TP9", "Fp1"}  # pre-judged artifact-heavy channels
```

Bad:

```python
VIEW_START_S = 2.0
VIEW_DURATION_S = 20.0
VIEW_BAND_HZ = (1.0, 40.0)
EXCLUDED_CHANNELS = {"TP9", "Fp1"}
```

### Plot preparation

Keep plot-preparation code (unit conversions, masks, derived display variables) near the plot that uses them, not in the analysis block. If it is only needed for a figure, it belongs in or just before that figure's block.

### Sub-section markers

Within a block, use a lightweight sub-header when a new logical step begins. Use a lighter form than the major section banners, and use a plain local guide comment when numbering would feel heavier than the code needs.

```python
# 2.3 Spectral summary
psd_spectrum = raw_view.compute_psd(fmin=0.5, fmax=40.0, verbose=False)

# keep valid windows
valid_mask = window_starts + window_size <= block_offsets
```

This keeps long blocks readable without splitting them into separate top-level sections.

### Canonical pipeline template

Before implementing the final script, write a skeleton that is mostly pseudo-code plus comments. This is the structure to validate first. Skip imports in this template. Keep only:

- the one-line question
- the config block
- a **data flow diagram** showing the transformation path
- actual function names you expect to use
- short local comments around non-obvious transformations
- plots at the end, marked as parameter validation or final reporting

This skeleton is structural pseudo-code, not near-final executable code.
It may name real functions, but it should not expand into detailed implementation
unless that detail is needed to explain the data flow or the scientific choice.

Rules for this skeleton:

- **Start with a data flow diagram** (lines showing transformations with arrows and boxes)
- **Use subsection markers to create visual hierarchy:**
  - `# ════════════════════` = major section (1, 2, 3...). Single blank line above, readers see these as waypoints
  - `# ══ 1.1 Substep ══` = logical substep within a section. Grouped without blank lines; belong to parent
  - Skip `# 1.1.1` level; instead, use an inline comment before the code block if needed
- **Only mark representation changes** (seconds → samples, continuous → events, channel space → component space) with an arrow comment: `# → type and shape, what it's used for`
- **Comment only non-obvious steps**. Obvious boilerplate (imports, directory creation, standard MNE loads) gets no comment
- **If you read only the subsection headers and arrow comments, you should still recover the pipeline**
- **For helper calls: one short comment on what it hides and what it returns**, not a detailed explanation. The reader should trust that `apply_saved_ssd(...)` does what its name says
- **Do not separate "INPUT / OPERATION / OUTPUT" as explicit labels**; instead, show them naturally:
  - Input enters the function call
  - Comment with `→ type` shows what comes back
  - Next function uses that output
- Keep helper calls visible; do not hide the core comparison, selection rule, or recovery metric inside one opaque helper

Helper examples:

- Good:
  - keep `build_late_off_events(...)` when late-OFF timing validity is non-trivial and already validated
  - keep direct GT slicing inline when it is only a few obvious lines
- Bad:
  - hide epoch slicing, filtering, and GT-locking inside one script-specific helper
  - call a helper only because it already exists in `preprocessing.py`

Template:

```python
"""Question this script answers."""

# ============================================================
# CONFIG
# ============================================================
stim_path = Path(r"...")  # stimulation recording
weights_path = Path(r"...")  # saved SSD weights
output_dir = Path(r"...")  # explicit output location
output_dir.mkdir(parents=True, exist_ok=True)

on_window_s = (0.3, 1.5)  # accepted ON segment
signal_band_hz = (12.0, 13.0)  # target rhythm band
view_band_hz = (4.0, 20.0)  # PSD display band
stim_threshold = 0.08  # weak-block recovery


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW (before pseudo-code, visualize the workflow)
# ════════════════════════════════════════════════════════════════════════════
#
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║               RAW VHDR → TIMING → WINDOWS → METRICS                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# VHDR Recording (22 EEG + stim + GT, 250 Hz, ~120 s)
# ├─ Extract: stim timing trace + GT reference
# │
# ├─ Detect: stimulus blocks via stim_trace edge detection
# │  └─ OUTPUT: (n_blocks,) sample indices [onset, offset]
# │
# ├─ Window: shift into ON segment (0.3–1.5 s post-stimulus)
# │  └─ OUTPUT: (n_events, 3) MNE-style event array
# │
# ├─ Epoch: fixed-length windows per event, apply SSD filter
# │  └─ OUTPUT: (n_epochs, 22, n_samples) raw, (n_epochs, n_comp, n_samples) SSD
# │
# ├─ Loop per block: band-pass 12 Hz → Hilbert phase → PLV per channel
# │  └─ OUTPUT: plv_by_intensity[intensity][channel] = [plv_per_cycle]
# │
# ├─ Select: best channel at 10%, lock for 20%–50% (prevents spatial drift confusion)
# │
# └─ Visualize: overlays (channel vs GT) + summary table per intensity
#
#
# EXPECTED BEHAVIOR:
# - 10–20%: PLV near 1.0 (excellent sync, minimal artifact)
# - 30%:    PLV ~0.93 (slight artifact contamination)
# - 40–50%: PLV 0.70–0.85 (strong artifact, path-dependent recovery)


# ════════════════════════════════════════════════════════════════════════════
# 1) LOAD & PREPARE
# ════════════════════════════════════════════════════════════════════════════

# ══ 1.1 Read recording ══
raw = mne.io.read_raw_brainvision(str(stim_path), preload=True, verbose=False)
# → MNE Raw: (22 EEG, stim, GT) @ 250 Hz, ~120 s
sfreq = float(raw.info["sfreq"])

# ══ 1.2 Extract timing & reference traces ══
stim_trace = raw.copy().pick(["stim"]).get_data()[0]      # (n_samples,) voltage on stim
gt_trace = raw.copy().pick(["ground_truth"]).get_data()[0]  # (n_samples,) recorded GT signal
# These drive: block detection (stim) and phase reference (GT)

# ══ 1.3 Load SSD weights (pre-trained spatial filter) ══
ssd_artifact = load_saved_weights(weights_path)
eeg_names = ssd_artifact["channel_names"]          # list of EEG channel names
ssd_filter = ssd_artifact["selected_filter"]       # (n_ch, n_comp) pre-trained weights
# → No retraining; fixed linear combinations applied to each epoch


# ════════════════════════════════════════════════════════════════════════════
# 2) DETECT STIMULUS BLOCKS & BUILD WINDOWS
# ════════════════════════════════════════════════════════════════════════════

# ══ 2.1 Find block onsets and offsets ══
block_onsets, block_offsets = detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=stim_threshold
)
# → (n_blocks,) sample indices where stim pulses start/end
# First block is weaker; threshold parameter accounts for this

# ══ 2.2 Convert time window to sample counts ══
# Seconds → samples. Needed for array slicing below.
window_len = on_window_s[1] - on_window_s[0]              # 1.2 s
window_size = int(round(window_len * sfreq))              # 1.2 s × 250 Hz = 300 samples
start_shift = int(round(on_window_s[0] * sfreq))          # 0.3 s × 250 Hz = 75 samples

# ══ 2.3 Shift block onsets into physiological ON window ══
# Add offset (0.3 s) to move from stim pulse edge to meaningful recording window
window_onsets = block_onsets + start_shift                # candidate starts in samples
# → (n_blocks,) sample indices

# Keep only complete windows (those that fit entirely inside blocks)
window_keep = window_onsets + window_size <= block_offsets  # boolean mask
event_samples = window_onsets[window_keep]                  # filtered start indices
events_on = build_event_array(event_samples)                # → MNE-style (n_events, 3)


# ════════════════════════════════════════════════════════════════════════════
# 3) EPOCH DATA & APPLY SSD
# ════════════════════════════════════════════════════════════════════════════

# ══ 3.1 Build epochs and project saved SSD filter ══
# Helper: bands raw (view_band), builds epochs, applies pre-trained SSD spatial
# weights to each. Transformation: (n_epochs, 22, n_samples) → (n_epochs, n_comp, n_samples)
epochs_view, ssd_epochs = apply_saved_ssd(
    raw.copy().pick(eeg_names),
    events_on,
    ssd_filter,
    view_band_hz,
    window_len,
)
# → epochs_view: (n_epochs, 22, 300) raw EEG, view-band filtered @ 4–20 Hz
# → ssd_epochs: (n_epochs, n_comp, 300) SSD components, view-band filtered

# ══ 3.2 Extract reference signals for comparison ══
raw_epochs = epochs_view.copy().pick(["O2"]).get_data()[:, 0, :]
# → (n_epochs, 300) raw O2 channel epochs
gt_epochs = extract_event_windows(gt_trace, events_on[:, 0], window_size)
# → (n_epochs, 300) GT reference epochs (recorded ground truth signal)


# ════════════════════════════════════════════════════════════════════════════
# 4) COMPUTE PHASE LOCKING & PSD
# ════════════════════════════════════════════════════════════════════════════

# ══ 4.1 Compute PLV (phase locking value) ══
# Band-pass raw & GT to target (12 Hz), compute instantaneous phase via Hilbert
# transform, then measure phase consistency: PLV = |mean(exp(i*phase_diff))|.
# PLV ∈ [0, 1]: 1 = perfect sync, 0 = no consistent phase relation.
raw_metrics = compute_band_metrics(raw_epochs, gt_epochs, sfreq, signal_band_hz)
# → dict: 'plv' (scalar 0–1, higher = better recovery)
#         'epoch_scores' (per-epoch PLV values for variability check)

# ══ 4.2 Compute power spectrum (artifact detection) ══
# Mean Welch PSD across all epochs in view band (4–20 Hz).
# Peak at 12 Hz indicates signal present; broadband elevation indicates artifact.
psd_freqs, raw_psd = compute_mean_psd(raw_epochs, sfreq, view_band_hz)
# → psd_freqs: (n_freqs,) frequency axis in Hz
# → raw_psd: (n_freqs,) power in µV²/Hz
```

Use this template as a drafting tool. The final script can be shorter than this skeleton, but it should still read in the same order: each output becomes the next input.

### Comment Strategy in Template Skeleton

**Four comment levels, brief and purposeful:**

**Level 1: Pipeline overview** (before code)
- Box drawing showing major steps and data flow direction
- Readers see the workflow before diving into code
- Includes what each step does and why

**Level 2: Major section headers** (`# ════ 1) LOAD & PREPARE ════`)
- Broad algorithm phases
- One blank line above
- Readers navigate code by these waypoints

**Level 3: Substep labels** (`# ══ 1.1 Read recording ══`)
- Logical substeps within section
- Grouped without blank lines; belongs to parent
- One phrase only

**Level 4: Inline comments (3 types):**

a) **Arrow comments** (`# →`) — show data shape/type at decision points:
```python
block_onsets, block_offsets = detect_stim_blocks(...)
# → (n_blocks,) sample indices where stim pulses start/end
```

b) **Explanatory comments** (1–3 sentences) — appear before complex transformations to explain the logic:
```python
# Seconds → samples. Needed for array slicing below.
window_size = int(round(window_len * sfreq))
```

c) **Guiding comments** (5–10 words) — appear inline on non-obvious operations:
```python
# Add offset (0.3 s) to move from stim pulse edge to meaningful recording window
window_onsets = block_onsets + start_shift
```

**What NOT to do:**
```python
# Read the VHDR file from disk. This loads the raw EEG data along with
# stim and GT traces. We suppress warnings about missing channel positions.
raw = mne.io.read_raw_brainvision(str(stim_path), preload=True, verbose=False)
# This returns an MNE Raw object which we will use in the next step
# to extract the stim and GT traces for timing purposes.
```

**Better:**
```python
# ══ 1.1 Read recording ══
raw = mne.io.read_raw_brainvision(str(stim_path), preload=True, verbose=False)
# → MNE Raw: (22 EEG, stim, GT) @ 250 Hz, ~120 s
sfreq = float(raw.info["sfreq"])
```

**Readers should be able to:**
- Skim the pipeline overview and understand what the script does
- Scan section headers (`# ══ ...`) and recover the full analysis flow
- Read inline comments on complex lines and understand why that step exists
- Trust function names; don't need explanatory prose around them
- Jump to any section and understand what data enters and leaves

## 4. MNE First, Helpers Second

Choose in this order:

1. native MNE/object methods
2. short inline code when it stays obvious
3. repo helpers only when MNE is insufficient, the logic is reused, or the helper clearly improves readability

Do not call a repo helper just because it exists.

If the analysis is still exploratory, prefer native MNE inspection and plotting before custom plotting code.
Write custom plotting only after the basic signal behavior is already understood and the script question is stable.

Prefer MNE-native code for:

- loading: `mne.io.read_raw_brainvision(...)`
- filtering: `raw.filter(...)`, `raw.notch_filter(...)`
- epoching: `mne.make_fixed_length_epochs(...)`, `mne.Epochs(...)`
- PSD: `raw.compute_psd(...)`, `epochs.compute_psd(...)`, `mne.time_frequency.psd_array_welch(...)`
- simple channel picking and cropping: `pick(...)`, `drop_channels(...)`, `crop(...)`

Good:

```python
raw_cz = raw.copy().pick(["Cz"])
raw_cz.filter(0.5, 40.0, verbose=False)
signal_uv = raw_cz.get_data()[0] * 1e6
```

Bad:

```python
signal_uv = preprocessing.filter_signal(raw.copy().pick(["Cz"]).get_data()[0], sfreq, 0.5, 40.0) * 1e6
```

Use a repo helper when:

- the logic is reused across scripts
- the logic is non-trivial and already validated
- the helper removes noise without hiding the scientific choice

If a helper affects interpretation, add one short comment that says:

- what it does
- why it is safe here
- what scientific choice it hides

If you cannot explain the helper call in one short comment, the script is too black-boxed.
If a helper performs a representation change, the structure comment should name that change in plain language.

Good:

```python
# Reuse the existing stim-block detector because the pulse-train structure is
# non-trivial and already validated elsewhere in the repo.
block_onsets, block_offsets = preprocessing.detect_stim_blocks(stim_marker, sfreq)
```

Bad:

```python
events = preprocessing.some_complex_step(raw)
```

## 5. Splitting Rule

If the script is doing more than one real thing, stop and propose a split to the user.

Do not silently keep growing the script.

Typical “real things”:

- build and validate windows or events
- score or select channels/components
- produce report-ready figures
- run a second distinct analysis branch

If a file is trying to do two or more of these as separate goals, ask the user whether to split it.

## 6. Naming Rule

Use long names for config constants and scientific choices.
In the analysis body, default to names that are short, readable, and locally clear.

Default pattern:

- `2` words in the body
- `1` word rarely
- `3` words only when needed
- almost never `4+` words in the body

A good name should usually reveal:

- the object's role
- the representation or unit when that matters for interpretation or indexing

If the name alone still leaves the type, shape, dimension, or role unclear,
add a short local comment at the assignment site. Naming should do as much work
as possible; comments finish the job when the name alone would still confuse a
first-time reader.

Good:

```python
LATE_OFF_START_S = 1.5
late_off_starts = ...
sfreq = float(raw.info["sfreq"])
window_size = int(round(window_len * sfreq))
event_samples = window_onsets[window_keep]
```

Bad:

```python
late_off_window_start_samples_after_measured_offset = ...
tmp = ...
sampling_rate_in_hertz_float = float(raw.info["sfreq"])
data = ...
mask = ...
```

Conventional short names are still acceptable when they are obvious in context:

```python
sfreq = float(raw.info["sfreq"])
raw = mne.io.read_raw_brainvision(...)
fig, ax = plt.subplots()
psd = raw.compute_psd(...)
```

Do not use a short name when it hides what the object contains.
Do not use a long name when a shorter one would still reveal role and representation.

## 7. Comments

Comment:

- why a step exists
- why a channel, window, band, or threshold was chosen
- what assumption gates a decision
- what a helper hides
- how one representation becomes the next when the flow would otherwise feel abrupt

In this repo, comments should guide the eye, not narrate the code.

### Default: keep comments short

Most comments should be short and visual:

- one line
- one idea
- easy to scan

Use longer, more precise comments **only** when something is genuinely critical, confusing, or scientifically load-bearing. A two-line comment on a standard filter call is over-commented.

Tie-break rule:

- keep comments short by default
- but do not skip a short local comment when an input object, helper output, or representation change would otherwise be unclear

Good:

```python
raw_view.filter(1.0, 40.0, verbose=False)  # view band; keeps drifts visible
```

Bad:

```python
# Use a light 1-40 Hz view filter for bad-channel inspection so slow drifts and
# broadband noise stay visible without leaving the traces dominated by DC offset.
raw_view.filter(1.0, 40.0, verbose=False)
```

### Structure comments (strx.)

Add a short structure comment before any step that is not immediately obvious — even inside a block. These are navigation aids, not prose. Usually they are `3-10` words. One line is enough.

Good:

```python
# 2.3 Build valid windows
raw_view = raw.copy().pick(eeg_channels)
raw_view.notch_filter(freqs=[50.0], verbose=False)
raw_view.filter(1.0, 40.0, verbose=False)
raw_view.crop(tmin=VIEW_START_S, tmax=view_stop_s)

# EEG -> uV for plotting
view_data_uv = raw_view.get_data() * 1e6
```

Bad (no structure comments, reader has to figure it out):

```python
raw_view = raw.copy().pick(eeg_channels)
raw_view.notch_filter(freqs=[50.0], verbose=False)
raw_view.filter(1.0, 40.0, verbose=False)
raw_view.crop(tmin=VIEW_START_S, tmax=view_stop_s)
view_data_uv = raw_view.get_data() * 1e6
```

Structure comments can be numbered or plain:

```python
# 3.1 Shift into ON segment
window_onsets = block_onsets + start_shift

# keep complete windows
window_keep = window_onsets + window_size <= block_offsets
```

### First-time reader test

Read the structure comments, explanatory comments, and key object comments without the code. A first-time reader should still recover the pipeline without needing local shorthand.

Those comments together should:

- name a real transformation or representation
- avoid unexplained repo shorthand
- use plain language when code identifiers are domain-specific
- make the important inputs readable where they enter
- make the important returned objects readable where they are assigned

Too vague on their own:

- `GT`
- `reference`
- `view`
- `trace`
- `fit`
- `EEG-only`

Bad:

```python
# raw -> GT trace
# EEG-only raw -> event array
# Score every component
```

Good:

```python
# raw -> recorded reference channel
# retained EEG -> fixed-window events
# Compute coherence and peak scores
```

### Explanatory comments before key transformations

Add short explanatory comments before steps that hide a scientific or representational change:

- raw → filtered
- continuous → events/epochs
- channel space → component space
- component epochs → PSD / summary metrics
- seconds → samples when the result is used for slicing or masking

These comments should usually be `1-3` short lines. They do not need rigid labels like `Input / Transformation / Output`. Make those elements visible naturally where they matter.

For an important helper call, the local comments around it should usually make
these things readable in about `3-8` short lines total:

- what important input is entering
- what hidden transformation the helper performs
- what important object or representation comes back
- what the next step will use from that result

Good:

```python
# Seconds -> integer samples for slicing.
window_size = int(round(window_len * sfreq))

# Keep only windows that stay fully inside
# the measured ON block so partial epochs
# do not contaminate the transfer test.
window_keep = window_onsets + window_size <= block_offsets

# This helper builds view-band epochs,
# then projects the saved SSD filter
# onto each accepted ON window.
epochs_view, ssd_epochs = apply_saved_ssd(...)

# raw_epochs -> epoch matrix from raw O2.
# This helper band-passes the epoch pairs,
# compares their analytic phases, and
# returns the locking curve used next.
raw_metrics = compute_band_metrics(...)
```

Bad:

```python
window_size = int(round(window_len * sfreq))
window_keep = window_onsets + window_size <= block_offsets
epochs_view, ssd_epochs = apply_saved_ssd(...)
raw_metrics = compute_band_metrics(...)
```

### Input and output comments

If an important input or returned object is not self-evident from the name
alone, add a short local comment where it appears. This can be an inline
comment on the assignment or a short comment directly above it.

Good:

```python
ssd_artifact = load_saved_weights(weights_path)  # saved SSD metadata dict
ssd_filter = ssd_artifact["selected_filter"]  # saved SSD spatial weights
raw_epochs = epochs_view.copy().pick(["O2"]).get_data()[:, 0, :]  # raw O2 epoch matrix
gt_epochs = extract_event_windows(...)  # GT epoch matrix
event_samples = window_onsets[window_keep]  # accepted start sample array
events_on = build_event_array(event_samples)  # MNE-style event array
```

Bad:

```python
artifact = load_saved_weights(weights_path)
mask = window_onsets + window_size <= block_offsets
events = build_event_array(window_onsets[mask])
metrics = compute_band_metrics(...)
```

### Key parameter choices

When you choose a non-obvious value (fmin, fmax, n_fft, window length), add a short inline comment:

```python
psd = raw_view.compute_psd(fmin=0.5, fmax=40.0, verbose=False)  # 0.5 Hz floor avoids DC; 40 Hz ceiling matches view band
```

### Do not comment boilerplate

Do not add explanatory comments before obvious boilerplate (warning suppression, output directory creation, standard MNE load calls). The code speaks for itself.

Bad:

```python
# Read the baseline recording directly and hide known BrainVision metadata
# warnings so the script output stays focused on the QC result.
with warnings.catch_warnings():
    ...
    raw = mne.io.read_raw_brainvision(...)
```

Good:

```python
with warnings.catch_warnings():
    ...
    raw = mne.io.read_raw_brainvision(...)
```

### Do not comment every assignment or repeat what the code literally says.
### Do not turn the script into prose.

The goal is that a reader can follow the key path quickly and stop only at the
few places where a real decision or hidden transformation needs explanation.

If a script contains real analysis choices and almost no explanatory comments, it is under-commented.

Good:

```python
# 1-second windows match the late-OFF duration used in the stim runs.
epochs = mne.make_fixed_length_epochs(raw, duration=1.0, overlap=0.0, preload=True, verbose=False)
```

Bad:

```python
epochs = mne.make_fixed_length_epochs(raw, duration=5.0, overlap=0.0, preload=True, verbose=False)
```

Comment the difficult choice, not the mechanics:

```python
# Good
# The late-OFF window starts 1.5 s after the measured offset so this analysis
# tests recovery after stimulation, not the stimulation train itself.

# Also good — structure comment
# raw → view band: notch + bandpass + crop

# Bad
# raw -> data
```

## 8. Validation

Do not write the whole script and debug at the end.

After risky steps, check something concrete:

- shape
- event count
- key time window
- slice bounds before slicing
- NaNs or non-finite values
- avoidable warnings or noisy runtime output

Keep useful checks in the final script when they protect a core assumption.

Good:

```python
print(f"Loaded stim: {stim_raw.n_times / stim_raw.info['sfreq']:.1f}s, sfreq={stim_raw.info['sfreq']:.0f} Hz")
assert window_stop_sample <= raw_cz.n_times, "Requested time window exceeds the recording."
print(f"Epoch check: baseline={len(baseline_epochs)} stim={len(stim_epochs)}")
```

Bad:

```python
# write 200 lines
# run once
# debug only after a crash
```

If warnings are predictable and do not matter to the analysis, either suppress them cleanly or explain why they are harmless. Do not leave noisy runtime output by default.

## 9. Forbidden Patterns

- multiple unrelated analyses in one script
- helper calls that hide scientific logic without explanation
- using repo helpers where short MNE-native code is clearer
- packing multiple actions onto one line to save space
- silent `try/except`
- fallback paths or auto-discovery
- dead branches and commented-out legacy code in final scripts

Also avoid:

- config blocks full of unexplained scientific choices
- long analysis bodies with no visible substructure
- naming every body variable like a full sentence
- scripts that answer one question in the docstring and a second question in the figures
- multi-line comments on obvious steps (filter, load, drop channels) — one line or nothing
- plot-prep variables (uV conversions, display masks) mixed into analysis blocks
- missing structure comments on non-obvious transformations inside blocks
- structure comments that rely on unexplained shorthand like `GT`, `reference`, `view`, or `EEG-only`
- pipeline comments overloaded with unnecessary input/output detail
- non-obvious created objects with no short description
- long body-variable names that read like sentences
- important helper calls with no local explanation

Explicit anti-pattern:

```python
data = preprocessing.filter_signal(raw.copy().pick(["Cz"]).get_data()[0], sfreq, 0.5, 40.0) * 1e6
epochs = mne.make_fixed_length_epochs(raw.copy().pick(["Cz"]), duration=5.0, preload=True, verbose=False)
```

Better:

```python
raw_cz = raw.copy().pick(["Cz"])
raw_cz.filter(0.5, 40.0, verbose=False)
signal_uv = raw_cz.get_data()[0] * 1e6

epochs = mne.make_fixed_length_epochs(
    raw.copy().pick(["Cz"]),
    duration=5.0,
    overlap=0.0,
    preload=True,
    verbose=False,
)
```

## 10. Reference

- Use [`explore_exp06_run02_on_art_filtering.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite Berlin/TIMS/explore_exp06_run02_on_art_filtering.py#L1) as the worked example for comment hierarchy, local explanatory comments, and non-obvious object descriptions.
- Use [`skript_gold_mne_old_experiment1.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite Berlin/TIMS/evidence/skript_gold_mne_old_experiment1.py#L1) only as a simple MNE-first example where the analysis stays compact.
- `DATAVIZ_FRAMEWORK.md` is for figure design, not script structure.

## 11. Final Checklist

Before calling a script done, check:

- the question is obvious in the first line
- the config block shows the important choices
- the script could be sketched as a simple workflow drawing without guessing missing steps
- the analysis body reads as 3 blocks
- MNE-native code was used where it is clearer than helpers
- every non-trivial helper call is explained
- structure comments alone let you recover the pipeline
- every structure comment names a real transformation or representation
- explanatory comments make hidden scientific transforms readable locally
- unit or representation changes are marked when they affect slicing, masking, or interpretation
- non-obvious created objects have a short local description
- local abbreviations are translated once into plain language
- helper comments explain the hidden transformation
- the body variable names are readable, mostly 2 words, and not bloated
- the script has concrete runtime checks
- outputs are explicit and deterministic

If any of these fail, revise the script before calling it final.
