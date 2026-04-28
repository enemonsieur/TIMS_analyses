"""Extract and visualize TMS-evoked potentials (TEPs) from EXP08 phantom dose-response data.

Apply decay removal and 0.5–42 Hz bandpass filtering on full epoch, then extract PRE and POST windows and plot.

PIPELINE:
  Load epochs (28 channels, 20 per intensity)
  ├─ For each intensity:
  │   ├─ Decay removal: fit A·exp(-t/τ)+C on full epoch, subtract per channel
  │   ├─ Bandpass filter: 1–80 Hz on full epoch
  │   ├─ Demean per-epoch
  │   ├─ Check saturation on evoked (drop channels > 10 mV)
  │   ├─ Extract PRE (-0.8 to -0.3 s) and POST (0.020 to 0.5 s) windows
  │   ├─ Average remaining channels
  │   └─ Plot joint (timeseries + topomaps)
  └─ Output: PNGs (intensities × 2 windows)
"""

import os
from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

warnings.filterwarnings("ignore", message=".*magnetometers.*")
warnings.filterwarnings("ignore", message=".*grad.*")

import preprocessing


# ============================================================
# CONFIG
# ============================================================

FIF_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUT_DIR = FIF_DIR / "TEPs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = [] #['F7', 'FT9', 'FC5', 'FC1', 'C3', 'T7', 'Pz', 'O1', 'O2', 'CP6', 'T8', 'FT10', 'FC2']  # pre-identified artifact channels (28 → 15 retained)

INTENSITIES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # stimulation levels in % MSO
HIGHPASS_HZ = 1         # remove slow drift and residual DC
LOWPASS_HZ = 80.0           # noise ceiling; preserves TMS-evoked band
PRE_WINDOW_S = (-0.8, -0.3) # control window: 500 ms before pulse, no artifact
POST_WINDOW_S = (0.020, 0.5) # response window: 480 ms post-pulse, decay present
DECAY_FIT_START_S = 0.020   # fit exponential from 20 ms post-pulse
OUTLIER_THRESHOLD_V = 0.01  # skip channels with peak > 10 mV (saturated)

TOPOMAP_TIMES_PRE = [-0.75, -0.60, -0.45]   # representative PRE sample times
TOPOMAP_TIMES_POST = [0.03, 0.10, 0.20]      # early/mid/late TEP peaks
YLIM_UV = (-5.0, 5.0)       # display range; matched across intensities


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# EXP08 .fif epoch files (10 intensities, 28 EEG channels each)
# ├─ Load: exp08_epochs_{pct}_on-epo.fif (20×28×3001 per intensity)
# ├─ Per intensity:
# │   ├─ Decay removal: fit A·exp(-t/τ)+C on full epoch
# │   ├─ Bandpass filter: 1–80 Hz on full epoch TODO: NO!!! THATS STUPID
# │   ├─ Demean per-epoch
# │   ├─ Check saturation on evoked: drop channels > 10 mV
# │   ├─ Extract PRE (-0.8 to -0.3 s) and POST (0.020 to 0.5 s) windows
# │   └─ plot_joint at topomaps → PNG
# └─ Output: PNGs (intensities × 2 windows)

# ============================================================
# 1) LOAD EPOCHS
# ============================================================

print("=" * 70)
print("EXP08 TEP EXTRACTION")
print("=" * 70)
print(f"\nLoading {len(INTENSITIES)} intensities: {INTENSITIES}")

epochs_on_all = {}
for pct in INTENSITIES:
    fif_path = FIF_DIR / f"exp08_epochs_{pct}pct_on-epo.fif"
    if not fif_path.exists():
        raise FileNotFoundError(f"{fif_path}")
    epochs = mne.read_epochs(str(fif_path), preload=True, verbose=False)
    # epochs.drop_channels(BAD_CHANNELS, on_missing="ignore")  # Removed: let saturation threshold decide
    epochs_on_all[pct] = epochs

sfreq = float(epochs_on_all[10].info["sfreq"])
n_channels = len(epochs_on_all[10].ch_names)
print(f"Loaded: {sfreq:.0f} Hz, {n_channels} EEG channels (no pre-drop)")
# print(f"Dropped channels: {BAD_CHANNELS}")


# ============================================================
# 2) COMPUTE EVOKED & PLOT
# ============================================================

print(f"\nProcessing...")
print(f"  Decay removal: fit from {DECAY_FIT_START_S*1000:.0f} ms")
print(f"  Filter: {HIGHPASS_HZ}–{LOWPASS_HZ} Hz bandpass")
print(f"  Demean: per-epoch")
print(f"  Bad channel threshold: >{OUTLIER_THRESHOLD_V*1e6:.0f} uV on normalized evoked")
print(f"  Windows: PRE {PRE_WINDOW_S[0]:.2f}-{PRE_WINDOW_S[1]:.2f} s, POST {POST_WINDOW_S[0]:.3f}-{POST_WINDOW_S[1]:.2f} s\n")

for pct in INTENSITIES:
    epochs = epochs_on_all[pct].copy()

    # ══ Decay removal ══
    # Fit decay model on full epoch to capture exponential transient.
    epochs = preprocessing.subtract_exponential_decay(
        epochs,
        fit_start_s=DECAY_FIT_START_S,
        outlier_threshold_v=OUTLIER_THRESHOLD_V,
    )

    # ══ Bandpass filter ══
    # Remove residual DC and slow drift (full epoch for proper kernel).
    epochs.filter(l_freq=HIGHPASS_HZ, h_freq=LOWPASS_HZ, verbose=False)

    # ══ Demean per-epoch ══
    # Remove DC offset per trial.
    epochs._data -= np.mean(epochs._data, axis=2, keepdims=True)

    # ══ Check saturation on normalized evoked ══
    # Average all epochs, identify channels still > threshold, drop them.
    evoked_full = epochs.average()
    bad_ch_idx = []
    for ch_idx in range(len(epochs.ch_names)):
        if np.max(np.abs(evoked_full.data[ch_idx])) > OUTLIER_THRESHOLD_V:
            bad_ch_idx.append(ch_idx)

    if bad_ch_idx:
        bad_ch_names = [epochs.ch_names[i] for i in bad_ch_idx]
        epochs.drop_channels(bad_ch_names)
        print(f"  {pct}%: dropped {len(bad_ch_names)} saturated channels: {bad_ch_names}")

    # ══ Extract windows ══
    # Crop to PRE and POST for evoked averaging.
    epochs_pre = epochs.copy().crop(*PRE_WINDOW_S)
    epochs_post = epochs.copy().crop(*POST_WINDOW_S)

    # ══ Extract evoked ══
    evoked_pre = epochs_pre.average()
    evoked_post = epochs_post.average()

    # ══ Diagnostic: track amplitude ranges in evoked ══
    pre_min_uv = evoked_pre.data.min() * 1e6
    pre_max_uv = evoked_pre.data.max() * 1e6
    pre_range_uv = pre_max_uv - pre_min_uv

    post_min_uv = evoked_post.data.min() * 1e6
    post_max_uv = evoked_post.data.max() * 1e6
    post_range_uv = post_max_uv - post_min_uv

    # ══ Plot both ══
    for label, evoked, times in [
        ("pre", evoked_pre, TOPOMAP_TIMES_PRE),
        ("post", evoked_post, TOPOMAP_TIMES_POST),
    ]:
        fig = evoked.plot_joint(
            times=times,
            title=f"EXP08 {label.upper()} | {pct}%  (n={evoked.nave})",
            ts_args={"gfp": True, "ylim": {"eeg": list(YLIM_UV)}},
            topomap_args={"outlines": "head"},
        )
        fig.set_size_inches(10.0, 6.0)
        out_path = OUT_DIR / f"exp08_tep_{pct}pct_raw_{label}.png"
        fig.savefig(str(out_path), dpi=220, bbox_inches="tight")
        plt.close(fig)

    print(f"  {pct}%: saved PRE and POST")
    print(f"       PRE:  min={pre_min_uv:8.2f} uV  max={pre_max_uv:8.2f} uV  range={pre_range_uv:8.2f} uV")
    print(f"       POST: min={post_min_uv:8.2f} uV  max={post_max_uv:8.2f} uV  range={post_range_uv:8.2f} uV")


# ============================================================
# 3) SUMMARY
# ============================================================

print(f"\n" + "=" * 70)
print(f"DONE: {len(INTENSITIES) * 2} plots in {OUT_DIR}/")
print(f"=" * 70)
