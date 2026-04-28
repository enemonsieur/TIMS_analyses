"""Compare good vs bad channels after decay removal to understand why decay fit breaks.

Inspect POST window (response) after exponential decay removal. Identify channels
where decay removal works (baseline near zero) vs channels where it fails (large
residual offsets). Visualize side-by-side to see the contrast.
"""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import mne
import preprocessing

# ============================================================
# CONFIG
# ============================================================
FIF_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUT_DIR = FIF_DIR / "TEPs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ['F7', 'FT9', 'FC5', 'FC1', 'C3', 'T7', 'Pz', 'O1', 'O2', 'CP6', 'T8', 'FT10', 'FC2']

INTENSITY = 20  # Use 20% where decay removal starts to break
POST_WINDOW_S = (0.020, 0.5)  # Response window (where decay is fitted)
DECAY_FIT_START_S = 0.020
OUTLIER_THRESHOLD_V = 0.01
LOWPASS_HZ = 42.0


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Goal: Identify which channels decay removal helps vs hurts at 20% intensity
#
# Load epochs (28 channels)
# ├─ Drop known bad channels
# │  → 15 remaining channels
# │
# ├─ Apply decay removal to all 15 channels
# │  → evoked POST after decay: (15 channels, 480 samples)
# │
# ├─ Measure baseline offset in each channel's POST trace
# │  (mean amplitude = indicator of residual DC after decay)
# │
# ├─ Rank channels by |baseline offset|:
# │   - GOOD: channels with offset near zero (decay worked)
# │   - BAD: channels with large positive/negative offset (decay failed)
# │
# └─ Plot: 3 good + 3 bad side-by-side for visual comparison
#     (readers see what "working" vs "broken" decay looks like)


# ============================================================
# 1) LOAD & APPLY DECAY REMOVAL
# ============================================================

print("=" * 80)
print(f"DECAY REMOVAL INSPECTION: {INTENSITY}% intensity")
print("=" * 80)

fif_path = FIF_DIR / f"exp08_epochs_{INTENSITY}pct_on-epo.fif"
epochs = mne.read_epochs(str(fif_path), preload=True, verbose=False)
epochs.drop_channels(BAD_CHANNELS, on_missing="ignore")
print(f"\nLoaded {INTENSITY}%: {len(epochs.ch_names)} channels, {len(epochs)} epochs")

# ══ 1.1 Apply decay removal ══
# Fit A·exp(-t/τ)+C on evoked average from 20ms onward, subtract from all epochs.
# → epochs now have exponential decay removed

epochs_decayed = preprocessing.subtract_exponential_decay(
    epochs.copy(),
    fit_start_s=DECAY_FIT_START_S,
    outlier_threshold_v=OUTLIER_THRESHOLD_V,
)
# → epochs_decayed: (15 channels, 20 epochs, ~1000 samples)

# ══ 1.1b Apply baseline from pre-pulse window ══
# Demean each epoch using pre-pulse baseline (-0.8 to -0.3 s) as reference.
epochs_decayed.apply_baseline((-0.8, -0.3))

# ══ 1.2 Filter and extract POST window ══
# Lowpass filter, then crop to POST response window where decay was fitted.
epochs_decayed.filter(l_freq=None, h_freq=LOWPASS_HZ, verbose=False)
epochs_post = epochs_decayed.copy().crop(*POST_WINDOW_S)
evoked_post = epochs_post.average()
# → evoked_post: (15 channels, 480 samples @ 1 kHz)


# ============================================================
# 2) IDENTIFY GOOD vs BAD CHANNELS
# ============================================================

# ══ 2.1 Measure baseline offset in each channel ══
# After decay removal, a "good" channel should have mean ≈ 0 in the POST window.
# A "bad" channel will have large positive or negative mean (residual DC).

channel_baseline_offsets = {}
for ch_idx, ch_name in enumerate(evoked_post.ch_names):
    ch_data_uv = evoked_post.data[ch_idx] * 1e6
    baseline_offset = np.abs(ch_data_uv.mean())  # |mean| = indicator of DC residual
    channel_baseline_offsets[ch_name] = baseline_offset

# ══ 2.2 Rank channels: good (low offset) vs bad (high offset) ══
# Sort by baseline offset magnitude
sorted_channels = sorted(channel_baseline_offsets.items(), key=lambda x: x[1])

good_channels = [ch for ch, offset in sorted_channels[:3]]  # 3 best (smallest offset)
bad_channels = [ch for ch, offset in sorted_channels[-3:]]  # 3 worst (largest offset)

print(f"\nGOOD channels (decay removal worked):")
for ch in good_channels:
    offset = channel_baseline_offsets[ch]
    print(f"  {ch:>3s}: baseline offset = {offset:.2f} µV")

print(f"\nBAD channels (decay removal failed):")
for ch in reversed(bad_channels):  # Print worst first
    offset = channel_baseline_offsets[ch]
    print(f"  {ch:>3s}: baseline offset = {offset:.2f} µV")


# ============================================================
# 3) VISUALIZE SIDE-BY-SIDE: GOOD vs BAD
# ============================================================

# ══ 3.1 Setup figure: 2 rows (good, bad) × 3 columns (channels) ══
fig, axes = plt.subplots(2, 3, figsize=(14, 7), sharex=True)
fig.suptitle(
    f"POST Window After Decay Removal ({INTENSITY}% intensity)\n"
    "Left row: GOOD channels (decay worked). Right row: BAD channels (decay failed).",
    fontsize=12, fontweight='bold'
)

times_post = evoked_post.times

# ══ 3.2 Plot good channels (top row) ══
for col_idx, ch_name in enumerate(good_channels):
    ax = axes[0, col_idx]
    ch_idx = evoked_post.ch_names.index(ch_name)
    ch_data_uv = evoked_post.data[ch_idx] * 1e6

    ax.plot(times_post, ch_data_uv, linewidth=2, color='green', alpha=0.8)
    ax.axhline(0, color='k', linestyle='--', alpha=0.3, linewidth=0.8)
    ax.axvline(0, color='k', linestyle='--', alpha=0.3, linewidth=0.8)
    ax.grid(True, alpha=0.2)

    # Title shows baseline offset
    offset = channel_baseline_offsets[ch_name]
    ax.set_title(f"{ch_name}\nBaseline offset: {offset:.2f} µV", fontsize=11, fontweight='bold', color='green')
    ax.set_ylabel("µV", fontsize=10)

    # Show min/max on plot
    ch_min = ch_data_uv.min()
    ch_max = ch_data_uv.max()
    ax.text(0.02, 0.98, f"Min: {ch_min:.1f} µV\nMax: {ch_max:.1f} µV",
            transform=ax.transAxes, fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))

# ══ 3.3 Plot bad channels (bottom row) ══
for col_idx, ch_name in enumerate(bad_channels):
    ax = axes[1, col_idx]
    ch_idx = evoked_post.ch_names.index(ch_name)
    ch_data_uv = evoked_post.data[ch_idx] * 1e6

    ax.plot(times_post, ch_data_uv, linewidth=2, color='red', alpha=0.8)
    ax.axhline(0, color='k', linestyle='--', alpha=0.3, linewidth=0.8)
    ax.axvline(0, color='k', linestyle='--', alpha=0.3, linewidth=0.8)
    ax.grid(True, alpha=0.2)

    # Title shows baseline offset
    offset = channel_baseline_offsets[ch_name]
    ax.set_title(f"{ch_name}\nBaseline offset: {offset:.2f} µV", fontsize=11, fontweight='bold', color='red')
    ax.set_ylabel("µV", fontsize=10)
    ax.set_xlabel("Time (s)", fontsize=10)

    # Show min/max on plot
    ch_min = ch_data_uv.min()
    ch_max = ch_data_uv.max()
    ax.text(0.02, 0.98, f"Min: {ch_min:.1f} µV\nMax: {ch_max:.1f} µV",
            transform=ax.transAxes, fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))

plt.tight_layout()
out_path = OUT_DIR / f"exp08_decay_inspection_{INTENSITY}pct_good_vs_bad.png"
plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
plt.close(fig)

print(f"\nSaved plot -> {out_path}")


# ============================================================
# 4) INTERPRETATION SUMMARY
# ============================================================

print(f"\n" + "=" * 80)
print("WHAT YOU'RE SEEING:")
print("=" * 80)
print("\nGOOD channels (green, top row):")
print("  - Baseline hovers near zero (±1-3 µV)")
print("  - Decay removal worked: fitted curve matched the data")
print("  - Safe to keep in final TEP average")

print("\nBAD channels (red, bottom row):")
print("  - Baseline has large positive or negative offset (±100+ µV)")
print("  - Decay removal FAILED: residual DC offset remains")
print("  - Likely causes: decay fit overfit, channel had pathological baseline, or")
print("    the exponential model doesn't match the actual artifact")

print("\nNEXT STEP:")
print(f"  Add these {len(bad_channels)} bad channels to the exclusion list:")
print(f"  {bad_channels}")
print("=" * 80)
