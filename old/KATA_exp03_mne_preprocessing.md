# Kata: preprocess + explore `exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr` (MNE-only, tiny steps)

Goal: build muscle memory for *raw → filtering → epochs → easy plots*, and understand the **inputs/outputs** of each step (MNE objects, shapes, units).

Constraint: you only write/uncomment **2–3 lines**, run, observe, repeat.

---

## Scaffolding file (start here)

- `kata_exp03_compare_epoching.py` (despite the name, it is now **MNE-only scaffolding** with `###` blocks)

---

## One-time setup (copy-paste into a scratch cell/script)

Use *explicit Windows paths* (repo convention) and an explicit output dir.

```py
from pathlib import Path
import mne

stim_vhdr_path = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_kata_outputs_run03")
output_directory.mkdir(parents=True, exist_ok=True)
```

Also set a “focus channel” for quick sanity checks:

```py
focus_channel = "Cz"
```

---

## Round 1 (15–25 min): load raw + learn MNE “what is inside?”

### Task A — Load as MNE Raw

```py
raw = mne.io.read_raw_brainvision(stim_vhdr_path, preload=True, verbose=False)
print(raw)
print("sfreq:", raw.info["sfreq"])
print("n_times:", raw.n_times, "duration_s:", raw.n_times / raw.info["sfreq"])
print("first 15 ch_names:", raw.ch_names[:15])
```

Questions to answer (write 1 line each in a notes file):
- What is the unit of `raw.get_data()`? (Volts vs µV)
- Which channels are “special” (`stim`, `ground_truth`, `STI*`) and which are EEG?

### Task B — Plot two ways (interactive + saved)

1) Interactive (fast feedback):
- `raw.plot(picks=[focus_channel], duration=10.0, scalings="auto")`
- `raw.compute_psd(fmin=0.1, fmax=60).plot()`

2) Saved (deterministic, good for comparing rounds):
- Save PSD figures via `fig.savefig(...)` (see the `### Step 3` block in `kata_exp03_compare_epoching.py`).

Variation to repeat (same tasks, different constraint):
- Repeat with `preload=False` and note what breaks/changes.

---

## Round 2 (30–45 min): filtering (MNE-only) and what changes

### Task A — Filter using MNE Raw

Make a copy so you can compare:

```py
raw_f = raw.copy()
raw_f.notch_filter(freqs=[50.0], notch_widths=2.0, verbose=False)
raw_f.filter(l_freq=1.0, h_freq=45.0, verbose=False)
```

Now compare PSD before/after and save both figures (see `kata_exp03_compare_epoching.py`).

Variation ladder (repeat the same tasks, only change ONE thing each time):
- 0.5–45 vs 1–45 Hz
- notch Q: 20 vs 30 vs 50
- apply filter before vs after picking channels

---

## Round 3 (20–40 min): epoching without pulse detection (fixed length)

### Task A — Fixed-length epochs (easy)

```py
events = mne.make_fixed_length_events(raw_f, duration=2.0)
epochs = mne.Epochs(raw_f, events, tmin=0.0, tmax=2.0, baseline=None, preload=True, verbose=False)
epochs.average().plot(picks=[focus_channel])
```

Variation:
- Change `duration` (2.0 → 1.0 → 0.5) and watch how the average changes.

---

## Round 4 (optional, 20–45 min): epoching from annotations (if present)

Some BrainVision files contain markers as `raw.annotations`. If so, you can build events without any custom peak detection.

```py
print(raw.annotations)
events, event_id = mne.events_from_annotations(raw)
print(event_id)
```

Then pick one `event_id` key and do:
- `epochs = mne.Epochs(raw_f, events, event_id={...}, tmin=..., tmax=..., baseline=None, preload=True, verbose=False)`

---

## Round 5 (optional, 30–60 min): compare to repo scripts (still MNE-only)

Take `main_analysis_exp03.py` as the ground-truth pipeline, but practice explaining each step by *printing shapes and saving one QC plot per stage*.

Minimum drill:
- Run `plot_exp03_timecourse_mne.py` and confirm you understand the two outputs (raw continuous view and cleaned-epoch mean view).

Extension:
- Run `plot_stim_10_30s.py` and try changing only the filter band.

---

## “Done” criteria (every round)

- You can state: **object type**, **shape**, **units**, and **time axis** for:
- `raw.get_data()` and `epochs.get_data()`
- You have 2–4 saved PNGs in your kata output directory that let you compare rounds quickly.
