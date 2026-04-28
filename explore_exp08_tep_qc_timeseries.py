"""Visualize per-channel timeseries: raw vs after-decay removal across intensities.

Plot 3-4 clean channels showing evoked traces before and after exponential decay
removal for 10%, 20%, 30% to diagnose where decay fit breaks down.
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
# Remaining after dropping BAD: ['F3', 'CP5', 'CP1', 'P3', 'P7', 'Oz', 'P4', 'P8', 'CP2', 'Cz', 'C4', 'FC6', 'F4', 'F8', 'Fp2']

INTENSITIES_TO_PLOT = [10, 20, 30]
CHANNELS_TO_SHOW = ['CP2', 'Cz', 'FC6', 'F4']  # pick 4 from remaining good channels
HIGHPASS_HZ = 0.5    # remove DC offset and slow drift
LOWPASS_HZ = 42.0
PRE_WINDOW_S = (-0.8, -0.3)
POST_WINDOW_S = (0.020, 0.5)
DECAY_FIT_START_S = 0.020
OUTLIER_THRESHOLD_V = 0.01

# ============================================================
# PIPELINE OVERVIEW
# ============================================================
#
# Load epochs (28 channels, 20 per intensity)
# ├─ Drop bad channels
# ├─ For each intensity (10, 20, 30%):
# │   ├─ Compute raw evoked (PRE, POST)
# │   ├─ Apply decay removal
# │   ├─ Compute decayed evoked (PRE, POST)
# │   ├─ Plot overlay: raw vs decayed timeseries
# │   └─ Track amplitude deltas
# └─ Output: PNG + summary stats


# ============================================================
# 1) LOAD & PROCESS
# ============================================================
print("=" * 80)
print("EXP08 TEP QC: TIMESERIES BEFORE/AFTER DECAY REMOVAL")
print("=" * 80)
print(f"\nPlotting channels: {CHANNELS_TO_SHOW}")
print(f"Intensities: {INTENSITIES_TO_PLOT}%\n")

fig, axes = plt.subplots(
    len(INTENSITIES_TO_PLOT) * 2,  # 2 rows per intensity (PRE, POST)
    len(CHANNELS_TO_SHOW),
    figsize=(16, 10),
    sharex=False,
)
fig.suptitle("TEP QC: Raw vs After-Decay Removal", fontsize=14, fontweight='bold')

summary_stats = {}

for intensity_idx, pct in enumerate(INTENSITIES_TO_PLOT):
    fif_path = FIF_DIR / f"exp08_epochs_{pct}pct_on-epo.fif"
    epochs_raw = mne.read_epochs(str(fif_path), preload=True, verbose=False)
    epochs_raw.drop_channels(BAD_CHANNELS, on_missing="ignore")

    # Get raw evoked PRE and POST
    # Note: filter on epochs before cropping to fit filter kernel properly
    epochs_raw_filtered = epochs_raw.copy()
    epochs_raw_filtered.filter(l_freq=HIGHPASS_HZ, h_freq=LOWPASS_HZ, verbose=False)
    evoked_raw_pre = epochs_raw_filtered.copy().crop(*PRE_WINDOW_S).average()
    evoked_raw_post = epochs_raw_filtered.copy().crop(*POST_WINDOW_S).average()

    # Apply decay removal and get decayed evoked
    epochs_decayed = preprocessing.subtract_exponential_decay(
        epochs_raw.copy(),
        fit_start_s=DECAY_FIT_START_S,
        outlier_threshold_v=OUTLIER_THRESHOLD_V,
    )

    # Demean using PRE window as baseline, filter to remove residual DC
    epochs_decayed.apply_baseline(PRE_WINDOW_S)
    epochs_decayed.filter(l_freq=HIGHPASS_HZ, h_freq=LOWPASS_HZ, verbose=False)
    evoked_decayed_pre = epochs_decayed.copy().crop(*PRE_WINDOW_S).average()
    evoked_decayed_post = epochs_decayed.copy().crop(*POST_WINDOW_S).average()

    # Summary stats for this intensity
    summary_stats[pct] = {}

    # ══ PRE WINDOW ══
    for ch_idx, ch_name in enumerate(CHANNELS_TO_SHOW):
        if ch_name not in evoked_raw_pre.ch_names:
            continue

        ch_idx_mne = evoked_raw_pre.ch_names.index(ch_name)

        # Get timeseries
        times_pre = evoked_raw_pre.times
        raw_pre_uv = evoked_raw_pre.data[ch_idx_mne] * 1e6
        decayed_pre_uv = evoked_decayed_pre.data[ch_idx_mne] * 1e6

        # Plot row: intensity_idx * 2 (PRE)
        ax = axes[intensity_idx * 2, ch_idx]
        ax.plot(times_pre, raw_pre_uv, 'b-', linewidth=1.5, label='Raw', alpha=0.7)
        ax.plot(times_pre, decayed_pre_uv, 'r-', linewidth=1.5, label='After Decay', alpha=0.7)
        ax.axvline(0, color='k', linestyle='--', alpha=0.3, linewidth=0.8)
        ax.set_title(f"{pct}% {ch_name} PRE", fontsize=10, fontweight='bold')
        ax.set_ylabel('µV')
        ax.grid(True, alpha=0.2)
        if ch_idx == 0:
            ax.legend(loc='upper right', fontsize=8)

        # Track stats
        raw_range = raw_pre_uv.max() - raw_pre_uv.min()
        decayed_range = decayed_pre_uv.max() - decayed_pre_uv.min()
        if ch_name not in summary_stats[pct]:
            summary_stats[pct][ch_name] = {}
        summary_stats[pct][ch_name]['PRE_raw_range'] = raw_range
        summary_stats[pct][ch_name]['PRE_decayed_range'] = decayed_range

    # ══ POST WINDOW ══
    for ch_idx, ch_name in enumerate(CHANNELS_TO_SHOW):
        if ch_name not in evoked_raw_post.ch_names:
            continue

        ch_idx_mne = evoked_raw_post.ch_names.index(ch_name)

        # Get timeseries
        times_post = evoked_raw_post.times
        raw_post_uv = evoked_raw_post.data[ch_idx_mne] * 1e6
        decayed_post_uv = evoked_decayed_post.data[ch_idx_mne] * 1e6

        # Plot row: intensity_idx * 2 + 1 (POST)
        ax = axes[intensity_idx * 2 + 1, ch_idx]
        ax.plot(times_post, raw_post_uv, 'b-', linewidth=1.5, label='Raw', alpha=0.7)
        ax.plot(times_post, decayed_post_uv, 'r-', linewidth=1.5, label='After Decay', alpha=0.7)
        ax.axvline(0, color='k', linestyle='--', alpha=0.3, linewidth=0.8)
        ax.set_title(f"{pct}% {ch_name} POST", fontsize=10, fontweight='bold')
        ax.set_ylabel('µV')
        ax.grid(True, alpha=0.2)
        if ch_idx == 0:
            ax.legend(loc='upper right', fontsize=8)

        # Track stats
        raw_range = raw_post_uv.max() - raw_post_uv.min()
        decayed_range = decayed_post_uv.max() - decayed_post_uv.min()
        summary_stats[pct][ch_name]['POST_raw_range'] = raw_range
        summary_stats[pct][ch_name]['POST_decayed_range'] = decayed_range

plt.tight_layout()
out_path = OUT_DIR / "exp08_tep_qc_timeseries_raw_vs_decay.png"
plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved plot -> {out_path}\n")


# ============================================================
# 2) SUMMARY STATISTICS
# ============================================================
print("=" * 80)
print("SUMMARY: AMPLITUDE RANGES (raw vs after-decay)")
print("=" * 80)

for pct in INTENSITIES_TO_PLOT:
    print(f"\n{pct}% INTENSITY:")
    print(f"  {'Channel':<8s} {'PRE Raw':<12s} {'PRE Decayed':<12s} {'POST Raw':<12s} {'POST Decayed':<12s}")
    print(f"  {'-'*60}")

    for ch_name in CHANNELS_TO_SHOW:
        if ch_name in summary_stats[pct]:
            stats = summary_stats[pct][ch_name]
            pre_raw = stats.get('PRE_raw_range', np.nan)
            pre_decayed = stats.get('PRE_decayed_range', np.nan)
            post_raw = stats.get('POST_raw_range', np.nan)
            post_decayed = stats.get('POST_decayed_range', np.nan)

            print(f"  {ch_name:<8s} {pre_raw:>10.2f}µV {pre_decayed:>10.2f}µV {post_raw:>10.2f}µV {post_decayed:>10.2f}µV")

            # Flag if decay made it worse
            if pre_decayed > pre_raw * 1.5:
                print(f"    ^ PRE got WORSE by {(pre_decayed/pre_raw - 1)*100:.0f}%")
            if post_decayed > post_raw * 1.5:
                print(f"    ^ POST got WORSE by {(post_decayed/post_raw - 1)*100:.0f}%")

print(f"\n" + "=" * 80)
print("DIAGNOSIS:")
print("=" * 80)
print("\nIf RED trace (After Decay) is bigger than BLUE trace (Raw),")
print("then decay removal is AMPLIFYING the signal, not removing it.")
print("\nExpected: RED should be SMALLER (artifact removed)")
print("Problem: RED is LARGER or SIMILAR (decay fit is broken)")
