"""Visualize raw evoked potentials across 10-30% intensities to inspect baseline data quality.

No preprocessing. Just load epochs and show per-channel timeseries (PRE and POST windows)
to understand what we're working with before decay removal.
"""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import mne

# ============================================================
# CONFIG
# ============================================================
FIF_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUT_DIR = FIF_DIR / "TEPs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ['F7', 'FT9', 'FC5', 'FC1', 'C3', 'T7', 'Pz', 'O1', 'O2', 'CP6', 'T8', 'FT10', 'FC2']

INTENSITIES = [10, 20, 30]  # Inspect this dose range
CHANNELS_TO_SHOW = ['CP2', 'Cz', 'FC6', 'F4', 'P3', 'P4', 'Oz', 'F3']  # Sample of remaining 15 channels
PRE_WINDOW_S = (-0.8, -0.3)   # Pre-pulse baseline window (no artifact expected)
POST_WINDOW_S = (0.020, 0.5)  # Post-pulse response window (artifact + signal)


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Goal: Inspect raw EEG evoked potentials at 3 intensities to see baseline quality
# before any preprocessing.
#
# Load epochs (28 EEG channels, 20 per intensity)
# ├─ Drop known bad channels (outliers from prior QC)
# │  → 15 clean channels remain
# │
# ├─ For each intensity (10, 20, 30%):
# │   ├─ Extract PRE window (baseline, −0.8 to −0.3 s)
# │   ├─ Average across 20 epochs
# │   │  → evoked PRE: (15 channels, 500 samples)
# │   │
# │   ├─ Extract POST window (response, 0.020 to 0.5 s)
# │   ├─ Average across 20 epochs
# │   │  → evoked POST: (15 channels, 480 samples)
# │   │
# │   └─ Plot: 8 channels × 2 windows per intensity
# │       (3 rows of subplots, each row = one intensity)
# │
# └─ Output: PNG showing raw traces + per-channel amplitude stats


# ============================================================
# 1) LOAD & DROP BAD CHANNELS
# ============================================================

print("=" * 80)
print("EXP08 RAW EVOKED INSPECTION (no preprocessing)")
print("=" * 80)
print(f"\nChannels to visualize: {CHANNELS_TO_SHOW}")
print(f"Intensities: {INTENSITIES}%\n")

# ══ 1.1 Load epochs and drop bad channels ══
# Each intensity has a separate .fif file (28 channels, 20 epochs each).
# We drop the known problematic channels first, reducing to 15 clean channels.

epochs_by_intensity = {}
for pct in INTENSITIES:
    fif_path = FIF_DIR / f"exp08_epochs_{pct}pct_on-epo.fif"
    epochs = mne.read_epochs(str(fif_path), preload=True, verbose=False)
    epochs.drop_channels(BAD_CHANNELS, on_missing="ignore")
    # → epochs: (15 channels, 20 trials, ~1000 samples @ 1 kHz)
    epochs_by_intensity[pct] = epochs

print(f"Loaded and cleaned {len(INTENSITIES)} intensities")
print(f"Channels retained: {epochs_by_intensity[10].ch_names}\n")


# ============================================================
# 2) EXTRACT & AVERAGE WINDOWS
# ============================================================

# ══ 2.1 Get evoked PRE and POST for each intensity ══
# Crop to time window, average across trials (the 20 epochs).
# PRE = baseline before pulse (clean, no artifact expected)
# POST = response after pulse (contains stimulus artifact + evoked response)

evoked_data = {}  # Store min/max stats per channel per window

for pct in INTENSITIES:
    epochs = epochs_by_intensity[pct]

    # Extract time windows and compute evoked average
    epochs_pre = epochs.copy().crop(*PRE_WINDOW_S)
    epochs_post = epochs.copy().crop(*POST_WINDOW_S)

    evoked_pre = epochs_pre.average()
    # → evoked_pre: (15 channels, 500 samples) @ 1 kHz, PRE window times
    evoked_post = epochs_post.average()
    # → evoked_post: (15 channels, 480 samples) @ 1 kHz, POST window times

    evoked_data[pct] = {
        'pre': evoked_pre,
        'post': evoked_post,
    }


# ============================================================
# 3) VISUALIZE RAW TRACES
# ============================================================

# ══ 3.1 Setup figure: 3 rows (one per intensity) × 2 panels (PRE, POST per row) ══
fig, axes = plt.subplots(
    len(INTENSITIES), 2,
    figsize=(14, 10),
    sharex=False, sharey=False,
)
fig.suptitle("RAW Evoked Potentials: PRE (baseline) vs POST (response)", fontsize=13, fontweight='bold')

# ══ 3.2 Plot per intensity ══
# For each intensity, show 8 sample channels in PRE and POST windows.
# All traces are stacked on the same axes to see amplitude ranges.

for intensity_idx, pct in enumerate(INTENSITIES):
    evoked_pre = evoked_data[pct]['pre']
    evoked_post = evoked_data[pct]['post']

    # ══ PRE window (left column) ══
    ax_pre = axes[intensity_idx, 0]
    times_pre = evoked_pre.times

    for ch_name in CHANNELS_TO_SHOW:
        if ch_name not in evoked_pre.ch_names:
            continue
        ch_idx = evoked_pre.ch_names.index(ch_name)
        ch_data_uv = evoked_pre.data[ch_idx] * 1e6
        ax_pre.plot(times_pre, ch_data_uv, linewidth=1, alpha=0.7, label=ch_name)

    ax_pre.axvline(0, color='k', linestyle='--', alpha=0.4, linewidth=0.8)
    ax_pre.set_title(f"{pct}% PRE window (baseline, no artifact expected)", fontsize=11, fontweight='bold')
    ax_pre.set_xlabel("Time (s)")
    ax_pre.set_ylabel("µV")
    ax_pre.grid(True, alpha=0.2)
    ax_pre.legend(loc='best', fontsize=8, ncol=2)

    # Amplitude range comment: show min/max across all channels
    pre_min = evoked_pre.data.min() * 1e6
    pre_max = evoked_pre.data.max() * 1e6
    pre_range = pre_max - pre_min
    ax_pre.text(0.02, 0.98, f"Range: {pre_min:.1f} to {pre_max:.1f} µV (Δ={pre_range:.1f} µV)",
                transform=ax_pre.transAxes, fontsize=9, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # ══ POST window (right column) ══
    ax_post = axes[intensity_idx, 1]
    times_post = evoked_post.times

    for ch_name in CHANNELS_TO_SHOW:
        if ch_name not in evoked_post.ch_names:
            continue
        ch_idx = evoked_post.ch_names.index(ch_name)
        ch_data_uv = evoked_post.data[ch_idx] * 1e6
        ax_post.plot(times_post, ch_data_uv, linewidth=1, alpha=0.7, label=ch_name)

    ax_post.axvline(0, color='k', linestyle='--', alpha=0.4, linewidth=0.8)
    ax_post.set_title(f"{pct}% POST window (response + artifact)", fontsize=11, fontweight='bold')
    ax_post.set_xlabel("Time (s)")
    ax_post.set_ylabel("µV")
    ax_post.grid(True, alpha=0.2)
    ax_post.legend(loc='best', fontsize=8, ncol=2)

    # Amplitude range comment
    post_min = evoked_post.data.min() * 1e6
    post_max = evoked_post.data.max() * 1e6
    post_range = post_max - post_min
    ax_post.text(0.02, 0.98, f"Range: {post_min:.1f} to {post_max:.1f} µV (Δ={post_range:.1f} µV)",
                 transform=ax_post.transAxes, fontsize=9, verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

plt.tight_layout()
out_path = OUT_DIR / "exp08_tep_qc_raw_evoked.png"
plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
plt.close(fig)

print(f"\nSaved plot -> {out_path}")


# ============================================================
# 4) SUMMARY STATISTICS
# ============================================================

print(f"\n" + "=" * 80)
print("SUMMARY: Raw evoked amplitude ranges per intensity")
print("=" * 80)

for pct in INTENSITIES:
    evoked_pre = evoked_data[pct]['pre']
    evoked_post = evoked_data[pct]['post']

    pre_min_uv = evoked_pre.data.min() * 1e6
    pre_max_uv = evoked_pre.data.max() * 1e6
    pre_range = pre_max_uv - pre_min_uv

    post_min_uv = evoked_post.data.min() * 1e6
    post_max_uv = evoked_post.data.max() * 1e6
    post_range = post_max_uv - post_min_uv

    print(f"\n{pct}% INTENSITY:")
    print(f"  PRE  (baseline):  min={pre_min_uv:8.1f} µV  max={pre_max_uv:8.1f} µV  range={pre_range:8.1f} µV")
    print(f"  POST (response):  min={post_min_uv:8.1f} µV  max={post_max_uv:8.1f} µV  range={post_range:8.1f} µV")
    print(f"  Ratio (POST/PRE): {post_range / pre_range:.1f}× amplification from baseline to response")

    # Flag if POST explodes compared to PRE
    if post_range > pre_range * 2:
        print(f"    ⚠ POST is >{post_range/pre_range:.0f}× larger than PRE (massive artifact/response)")

print(f"\n" + "=" * 80)
print("EXPECTED PATTERN:")
print("=" * 80)
print("\n10-20%: PRE and POST ranges should be similar, both small (clean signal)")
print("30%+:   POST range grows (artifact increases) but PRE stays stable")
print("\nPROBLEM INDICATORS:")
print("  - PRE baseline has huge swings (±thousands µV) -> bad channel remained")
print("  - POST is massively larger than PRE -> heavy artifact")
print("=" * 80)
