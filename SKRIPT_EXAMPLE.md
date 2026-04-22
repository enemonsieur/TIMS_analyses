# SKRIPT Template Example: Complete Real Pseudo-Code

This example shows how to write a script skeleton for analyzing phase locking across stimulus intensities.

---

## Script Purpose

```
Identify best raw EEG channel per stimulus intensity based on phase locking to ground truth,
then compare raw vs. cleaned (SASS/SSD) recovery across intensities.
```

---

## Step 1: Pipeline Overview (Visual)

### Data Flow Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                  VHDR Recording → Channel Selection → Metrics                ║
╚══════════════════════════════════════════════════════════════════════════════╝

VHDR Recording (5 intensities × 20 cycles = 100 blocks)
├─ Extract: stim timing + GT reference + 22 EEG channels (250 Hz, ~120 s)
│
├─ Detect: stimulus blocks via stim_trace edge detection
│  └─ OUTPUT: (n_blocks,) sample indices where stim pulses start/stop
│
├─ Build ON-window events: shift onsets 0.3–1.5 s post-stimulus
│  └─ OUTPUT: (n_events, 3) MNE-style event array (filtered incomplete windows)
│
├─ Epoch: fixed-length 1.2 s windows per event
│  └─ OUTPUT: raw_epochs (n_epochs, 22, 300 samples) @ 4–20 Hz view band
│
├─ Loop per block: Band-pass → 12 Hz, Hilbert phase, compute PLV per channel
│  ├─ Accumulate: plv_by_intensity[intensity][channel] += [plv_value]
│  └─ OUTPUT after loop: mean PLV per channel per intensity
│
├─ Select best channel: argmax(PLV) at 10%, lock for 20%–50%
│  └─ RATIONALE: Locks spatial reference; PLV changes → artifact, not drift
│
└─ Extract filtered time courses (all cycles concatenated per intensity)
   └─ OUTPUT: summary table, figures showing channel vs GT overlay per intensity
```

### Execution Workflow

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         Estimated Runtime & Outputs                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

STEP 1: Load & Detect Blocks
┌────────────────────────────────────────┐
│ Load VHDR (22 EEG + stim + GT)         │
│ Detect 100 stimulus blocks             │
│ Duration: ~1 minute                    │
└────────────────────────────────────────┘
         ↓
STEP 2: Compute PLV Per Channel Per Intensity
┌────────────────────────────────────────┐
│ For each block:                        │
│   - Extract ON-window trace            │
│   - Band-pass to 12 Hz                 │
│   - Compute Hilbert phase              │
│   - Calculate PLV (phase coherence)    │
│ Duration: ~3 minutes                   │
│ OUTPUT: plv_by_intensity_channel       │
└────────────────────────────────────────┘
         ↓
STEP 3: Select Best Channel & Visualize
┌────────────────────────────────────────┐
│ Find best channel at 10% (max PLV)     │
│ Lock it for 20%–50%                    │
│ Extract and plot time courses          │
│ Duration: ~1 minute                    │
│ OUTPUT: summary.txt                    │
│         overlay.png (5 panels)         │
└────────────────────────────────────────┘
         ↓
TOTAL TIME: ~5 minutes
```

### Expected Result Pattern

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PLV vs Stimulation Intensity (Expected)                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

PLV (Phase Locking Value)

1.0 │                 ╔════════════════╗
    │                 ║   GT-STIM      ║  Always ~1.0 (upper bound)
0.95│      ┌──────────╨────────────────║  10%–20%: minimal artifact
    │      │                           │
0.9 │      │ Raw ─────────┐            ║
    │      │              │            │
0.85│      ├─ SASS ──────┐└────────┐   ║  30%: artifact increasing
    │      │             │        │    ║
0.8 │      ├─ SSD ───────┘        │    ║
    │      │                      │    ║
0.75│      │                      │    ║
    │      │                      └──┐ ║  40–50%: strong artifact
0.7 │      │                         ╨║  Raw collapses fastest
    │      │                          │  SASS/SSD more robust
0.65│      │                          │
    │      │  Artifact contamination  │
0.6 │      │  increasingly affects   │
    │      │  all recovery paths     │
    │      │                         │
0.5 └──────┴─────────────────────────┘
         10%   20%   30%   40%   50%
         Stimulation Intensity

KEY PATTERN:
- All paths decline (artifact increasing with intensity)
- SASS/SSD decline slower than Raw (better suppression)
- SSD best overall (combines spatial + spectral info)
```

---

## Step 2: Full Pseudo-Code with Comments

```python
"""Identify best EEG channels via phase locking; compare raw vs. filtered paths."""

from pathlib import Path
import numpy as np
from scipy.signal import hilbert
import mne

import preprocessing  # local helper module


# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════
STIM_VHDR_PATH = Path(r"C:\data\exp06-STIM-iTBS_run02.vhdr")
OUTPUT_DIR = Path(r"C:\data\outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES_PER_INTENSITY = 20
ON_WINDOW_S = (0.3, 1.5)           # physiologically meaningful ON segment
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}  # known artifact channels

TARGET_CENTER_HZ = 12.451172       # target frequency (where signal is expected)
SIGNAL_HALF_WIDTH_HZ = 0.5         # band width around target
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ,
                  TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
RUN02_STIM_THRESHOLD_FRACTION = 0.08  # rise-edge threshold for weak first block


# ════════════════════════════════════════════════════════════════════════════
# 1) LOAD & PREPARE
# ════════════════════════════════════════════════════════════════════════════

# ══ 1.1 Read recording ══
print("Loading VHDR file...")
raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), 
                                            preload=True, verbose=False)
# → MNE Raw: (22 EEG, stim, GT) @ 250 Hz, ~120 s continuous

sfreq = float(raw_stim_full.info["sfreq"])
print(f"Sampling rate: {sfreq:.0f} Hz")

# ══ 1.2 Extract timing and reference traces ══
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]
# → (n_samples,) voltage on stim channel; used for block detection

gt_trace = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]
# → (n_samples,) recorded ground truth signal; used as phase reference

raw_eeg = raw_stim_full.copy().drop_channels(
    [ch for ch in raw_stim_full.ch_names 
     if ch.lower() in {"stim", "ground_truth"} or ch in EXCLUDED_CHANNELS]
)
print(f"Retained {len(raw_eeg.ch_names)} EEG channels: {raw_eeg.ch_names}")

# ══ 1.3 Convert to numpy arrays ══
eeg_data = raw_eeg.get_data()  # → (22 channels, n_samples)
gt_data = gt_trace             # → (n_samples,)


# ════════════════════════════════════════════════════════════════════════════
# 2) DETECT STIMULUS BLOCKS & BUILD WINDOWS
# ════════════════════════════════════════════════════════════════════════════

# ══ 2.1 Detect block edges from stim trace ══
print("Detecting stimulus blocks...")
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION
)
# → arrays of sample indices where each stimulus block starts/stops
# First block is weaker; threshold parameter is part of the timing rule

n_blocks = len(block_onsets_samples)
print(f"Found {n_blocks} blocks (expected 5 intensities × 20 cycles = 100)")

# ══ 2.2 Convert time window to sample counts ══
# Seconds → samples. All slicing operations below work with sample indices.
on_window_start_shift = int(round(ON_WINDOW_S[0] * sfreq))
on_window_end_shift = int(round(ON_WINDOW_S[1] * sfreq))
on_window_samples = on_window_end_shift - on_window_start_shift
# → (75, 375, 300 samples) for (0.3 s, 1.5 s, 1.2 s window length)
print(f"ON window: {ON_WINDOW_S[0]}–{ON_WINDOW_S[1]} s = {on_window_samples} samples")


# ════════════════════════════════════════════════════════════════════════════
# 3) COMPUTE PHASE LOCKING (PLV) PER CHANNEL PER INTENSITY
# ════════════════════════════════════════════════════════════════════════════

print(f"\nComputing PLV (phase locking value) per channel...")
print(f"Target band: {SIGNAL_BAND_HZ[0]:.2f}–{SIGNAL_BAND_HZ[1]:.2f} Hz")

# Map each block to its intensity: [0 0...0 (20×), 1 1...1 (20×), ..., 4 4...4 (20×)]
blocks_per_intensity = BLOCK_CYCLES_PER_INTENSITY
intensity_indices = np.repeat(np.arange(5), blocks_per_intensity)

# Store: plv_by_intensity[intensity_idx][channel_name] = [plv_cycle1, plv_cycle2, ...]
plv_by_intensity_channel = {i: {ch: [] for ch in raw_eeg.ch_names} 
                            for i in range(5)}

# ══ 3.1 Main loop: iterate over blocks, compute PLV per cycle ══
for block_idx in range(n_blocks):
    intensity_idx = intensity_indices[block_idx]
    onset_sample = block_onsets_samples[block_idx]
    
    # Define ON-window boundaries (offset from block onset)
    on_start = onset_sample + on_window_start_shift
    on_end = onset_sample + on_window_end_shift
    
    # Safety check: ensure window fits inside recording
    if on_end > eeg_data.shape[1]:
        print(f"  Block {block_idx}: ON window extends beyond recording; skipping.")
        continue
    
    # ══ 3.1.1 Extract ON-window traces ══
    on_eeg = eeg_data[:, on_start:on_end]
    # → (22, 300) raw EEG in ON window
    on_gt = gt_data[on_start:on_end]
    
    # ══ 3.1.2 Band-pass filter to isolate target frequency ══
    # Filtering removes artifact harmonics and broadband noise, leaving only
    # the 12.45 Hz component. This isolates true phase coherence between
    # EEG channels and GT reference.
    on_eeg_filt = preprocessing.filter_signal(
        on_eeg, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )
    
    on_gt_filt = preprocessing.filter_signal(
        on_gt, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )
    
    # ══ 3.1.3 Compute instantaneous phase via Hilbert transform ══
    # Hilbert transform: analytic signal = amplitude × exp(i × phase).
    # We extract phase (angle) and discard amplitude.
    on_eeg_phase = np.angle(hilbert(on_eeg_filt, axis=-1))
    on_gt_phase = np.angle(hilbert(on_gt_filt, axis=-1))
    
    # ══ 3.1.4 Compute PLV (phase locking value) ══
    # PLV = |mean(exp(i × phase_diff))| across time.
    # Intuition: if phases are consistently aligned, their complex vectors
    # average to a large magnitude; if phase_diff is random, vectors cancel out.
    # Result: PLV ∈ [0, 1] where 1 = perfect sync, 0 = no sync.
    phase_diff = on_eeg_phase - on_gt_phase[np.newaxis, :]
    plv_per_channel = np.abs(
        np.mean(np.exp(1j * phase_diff), axis=-1)
    )
    # → (22,) one PLV score per channel (how locked to GT in this cycle)
    
    # ══ 3.1.5 Store PLV for this cycle ══
    for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
        plv_by_intensity_channel[intensity_idx][ch_name].append(
            plv_per_channel[ch_idx]
        )


# ════════════════════════════════════════════════════════════════════════════
# 4) SELECT BEST CHANNEL & AGGREGATE ACROSS CYCLES
# ════════════════════════════════════════════════════════════════════════════

print("\nMean PLV per channel per intensity (averaged across 20 cycles):")

best_channels = {}
FIXED_CHANNEL = None  # Will be locked at 10% and fixed for all others

for intensity_idx in range(5):
    intensity_label = RUN02_INTENSITY_LABELS[intensity_idx]
    print(f"\n{intensity_label}:")
    
    # Compute mean PLV per channel (average across all cycles for this intensity)
    channel_mean_plv = {}
    for ch_name in raw_eeg.ch_names:
        if plv_by_intensity_channel[intensity_idx][ch_name]:
            mean_plv = np.mean(plv_by_intensity_channel[intensity_idx][ch_name])
            channel_mean_plv[ch_name] = mean_plv
            print(f"  {ch_name:6s}: {mean_plv:.4f}")
    
    # ══ 4.1 At 10%: find best channel, lock it ══
    # Rationale: locking the channel across intensities ensures that PLV changes
    # reflect artifact contamination, not spatial drift (best channel changing).
    if intensity_idx == 0:  # 10% intensity
        if channel_mean_plv:
            best_ch = max(channel_mean_plv, key=channel_mean_plv.get)
            # → Channel with highest phase locking
            best_plv = channel_mean_plv[best_ch]
            FIXED_CHANNEL = best_ch
            best_channels[intensity_idx] = (best_ch, best_plv)
            print(f"  ✓ LOCKED: {best_ch} (PLV = {best_plv:.4f})")
        else:
            print(f"  ✗ No channels available for {intensity_label}")
    
    # ══ 4.2 At 20–50%: use locked channel ══
    # Same spatial reference across all intensities. PLV decline = artifact,
    # not channel switching.
    else:  # 20–50% intensities
        if FIXED_CHANNEL and FIXED_CHANNEL in channel_mean_plv:
            best_plv = channel_mean_plv[FIXED_CHANNEL]
            best_channels[intensity_idx] = (FIXED_CHANNEL, best_plv)
            print(f"  ✓ FIXED: {FIXED_CHANNEL} (PLV = {best_plv:.4f})")
        else:
            print(f"  ✗ Fixed channel unavailable at {intensity_label}")


# ════════════════════════════════════════════════════════════════════════════
# 5) EXTRACT FILTERED TIME COURSES FOR VISUALIZATION
# ════════════════════════════════════════════════════════════════════════════

print("\nExtracting filtered time courses for best channels...")

# For each intensity, collect all ON-window cycles of the best channel + GT
best_channel_cycles = {i: [] for i in range(5)}
best_gt_cycles = {i: [] for i in range(5)}

for block_idx in range(n_blocks):
    intensity_idx = intensity_indices[block_idx]
    onset_sample = block_onsets_samples[block_idx]
    
    on_start = onset_sample + on_window_start_shift
    on_end = onset_sample + on_window_end_shift
    
    if on_end > eeg_data.shape[1] or intensity_idx not in best_channels:
        continue
    
    best_ch, _ = best_channels[intensity_idx]
    ch_idx = raw_eeg.ch_names.index(best_ch)
    
    # ══ 5.1 Extract and filter ══
    # We re-extract and re-filter each cycle (same as in loop 3.1) so the
    # time courses match the PLV computation exactly. No shortcuts.
    on_eeg_raw = eeg_data[ch_idx, on_start:on_end]
    on_gt_raw = gt_data[on_start:on_end]
    
    on_eeg_filt = preprocessing.filter_signal(
        on_eeg_raw, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )
    on_gt_filt = preprocessing.filter_signal(
        on_gt_raw, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1]
    )
    # → Filtered to 12 Hz band for visualization (matches PLV computation)
    
    best_channel_cycles[intensity_idx].append(on_eeg_filt)
    best_gt_cycles[intensity_idx].append(on_gt_filt)

# Concatenate all cycles per intensity: 20 × 1.2s → 24 s total per intensity
best_channel_timecourses = {}
best_gt_timecourses = {}
for intensity_idx in range(5):
    if best_channel_cycles[intensity_idx]:
        best_channel_timecourses[intensity_idx] = np.concatenate(
            best_channel_cycles[intensity_idx]
        )  # → (7200,) at 250 Hz = 24 s
        best_gt_timecourses[intensity_idx] = np.concatenate(
            best_gt_cycles[intensity_idx]
        )


# ════════════════════════════════════════════════════════════════════════════
# 6) VISUALIZATION & EXPORT
# ════════════════════════════════════════════════════════════════════════════

print("\nGenerating figures and summary tables...")

# ══ 6.1 Create multi-panel overlay figure ══
# Expected pattern: low intensities (10–30%) show clean phase overlap;
# high intensities (40–50%) show increasing phase drift or amplitude collapse.

import matplotlib.pyplot as plt

fig, axes = plt.subplots(5, 1, figsize=(14, 12))
fig.suptitle("Best Raw Channels (Top Phase Locking) vs GT — ON Window (0.3–1.5 s post-onset)",
             fontsize=14, fontweight="bold")

INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]

for intensity_idx in range(5):
    ax = axes[intensity_idx]
    intensity_label = RUN02_INTENSITY_LABELS[intensity_idx]
    color = INTENSITY_COLORS[intensity_idx]
    
    if intensity_idx not in best_channels or best_channel_timecourses[intensity_idx] is None:
        ax.text(0.5, 0.5, f"No data for {intensity_label}", 
                ha="center", va="center", fontsize=12, color="red")
        continue
    
    best_ch, best_plv = best_channels[intensity_idx]
    ch_timecourse = best_channel_timecourses[intensity_idx]
    gt_timecourse = best_gt_timecourses[intensity_idx]
    
    time_axis_s = np.arange(len(ch_timecourse)) / sfreq
    
    ax.plot(time_axis_s, gt_timecourse, "k-", linewidth=2.0, 
            label="GT (reference)", zorder=3)
    ax.plot(time_axis_s, ch_timecourse, color=color, linewidth=1.5,
            label=f"{best_ch} (PLV={best_plv:.4f})", zorder=2)
    
    ax.set_title(f"{intensity_label}: {best_ch} vs GT", fontsize=11, fontweight="bold")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (µV)")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
output_fig_path = OUTPUT_DIR / "best_channel_sync_overlay.png"
plt.savefig(output_fig_path, dpi=150, bbox_inches="tight")
print(f"Saved figure: {output_fig_path}")
plt.close()

# ══ 6.2 Export summary table ══
summary_lines = [
    "BEST RAW CHANNELS (PHASE LOCKING) — EXP06 RUN02 ON-WINDOW SYNC",
    "=" * 80,
    f"Target frequency: {TARGET_CENTER_HZ:.3f} Hz (band: {SIGNAL_BAND_HZ[0]:.2f}–{SIGNAL_BAND_HZ[1]:.2f} Hz)",
    f"ON window: {ON_WINDOW_S[0]}–{ON_WINDOW_S[1]} s post-onset",
    f"Per-intensity cycles: {BLOCK_CYCLES_PER_INTENSITY}",
    "",
    "Intensity | Best Channel | Mean PLV  | Interpretation",
    "-" * 80,
]

for intensity_idx in range(5):
    intensity_label = RUN02_INTENSITY_LABELS[intensity_idx]
    if intensity_idx in best_channels:
        best_ch, best_plv = best_channels[intensity_idx]
        status = "✓ Good" if best_plv > 0.9 else "⚠ Declining" if best_plv > 0.8 else "✗ Poor"
        summary_lines.append(
            f"{intensity_label:10s} | {best_ch:12s} | {best_plv:.4f}   | {status}"
        )
    else:
        summary_lines.append(f"{intensity_label:10s} | {'N/A':12s} | N/A       | No data")

summary_lines.extend([
    "",
    "INTERPRETATION:",
    "- PLV > 0.95: excellent phase-locked recovery",
    "- PLV 0.80–0.95: moderate recovery with some artifact contamination",
    "- PLV < 0.80: significant artifact contamination or phase drift",
])

summary_text = "\n".join(summary_lines)
summary_path = OUTPUT_DIR / "best_channel_summary.txt"
with open(summary_path, "w") as f:
    f.write(summary_text)

print(summary_text)
print(f"\nSaved summary: {summary_path}")
print("Done!")
```

---

## Key Features of This Example

1. **Pipeline overview first** (visual box drawing before any code)

2. **Numbered sections** (1, 2, 3, 4, 5, 6) showing algorithm phases

3. **Numbered subsections** (1.1, 1.2, 1.3, 3.1.1, 3.1.2, etc.) for logical steps

4. **Four types of comments:**
   - **Arrow comments** (`# → (22, 300)`) show data shapes
   - **Explanatory comments** (multi-sentence) before complex operations (Hilbert transform, PLV formula)
   - **Guiding comments** (5-10 words) on non-obvious lines (intensity mapping, phase difference calculation)
   - **Section headers** for navigation

5. **Implicit input/output** — shown in code flow and arrow comments, not labeled explicitly

6. **Real loops and logic** — not hidden in helpers; the core algorithm is visible

7. **Rationale comments** (e.g., lines explaining why we lock the channel) embedded naturally in the code

