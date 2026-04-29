"""Compute TEP averages from run01 artifact-removed epochs and plot per intensity.

Artifact window is already interpolated (−10 ms to recovery) so no decay
removal is needed. Bandpass filtering is safe: no impulse at t=0 to ring on.

PIPELINE:
  artremoved-epo.fif (10 intensities, 28 EEG channels each)
  ├─ For each intensity:
  │   ├─ Bandpass filter: 1–80 Hz on full epoch (removes residual DC)
  │   ├─ Check saturation on evoked: drop channels > 10 mV
  │   ├─ Extract PRE (−0.8 to −0.3 s) and POST (0.020 to 0.5 s) windows
  │   ├─ Average and plot_joint (timeseries + topomaps)
  │   └─ Report amplitude ranges
  └─ Output: PNGs in EXP08/TEPs_artremoved/
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


# ============================================================
# CONFIG
# ============================================================

FIF_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUT_DIR = FIF_DIR / "TEPs_artremoved"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTENSITIES     = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # % MSO
HIGHPASS_HZ     = 1.0            # remove residual DC; kernel fits in full epoch
LOWPASS_HZ      = 80.0           # preserve gamma; remove HF noise
PRE_WINDOW_S    = (-0.8, -0.3)   # 500 ms pre-pulse control window
POST_WINDOW_S   = (0.020, 0.5)   # 480 ms post-pulse response window (skip artifact gap)
OUTLIER_THRESH_V = 0.01          # drop channels with evoked peak > 10 mV

TOPOMAP_TIMES_PRE  = [-0.75, -0.60, -0.45]
TOPOMAP_TIMES_POST = [0.03, 0.10, 0.20]
YLIM_UV = (-5.0, 5.0)


# ============================================================
# 1) LOAD EPOCHS
# ============================================================

# ══ 1.1 Read artremoved epochs per intensity ══
print("=" * 70)
print("EXP08 TEP EXTRACTION — ARTREMOVED EPOCHS")
print("=" * 70)
print(f"\nLoading {len(INTENSITIES)} intensities: {INTENSITIES}")

epochs_all = {}
for pct in INTENSITIES:
    fif_path = FIF_DIR / f"exp08_epochs_{pct}pct_on_artremoved-epo.fif"
    if not fif_path.exists():
        raise FileNotFoundError(f"{fif_path}")
    epochs_all[pct] = mne.read_epochs(str(fif_path), preload=True, verbose=False)

sfreq = float(epochs_all[10].info["sfreq"])
n_ch  = len(epochs_all[10].ch_names)
print(f"Loaded: {sfreq:.0f} Hz, {n_ch} EEG channels, no decay removal (artifact interpolated)")


# ============================================================
# 2) COMPUTE EVOKED & PLOT
# ============================================================

print(f"\nProcessing...")
print(f"  Filter: {HIGHPASS_HZ}–{LOWPASS_HZ} Hz on full epoch")
print(f"  Saturation threshold: >{OUTLIER_THRESH_V*1e6:.0f} µV on evoked")
print(f"  Windows: PRE {PRE_WINDOW_S}, POST {POST_WINDOW_S}\n")

for pct in INTENSITIES:
    epochs = epochs_all[pct].copy()

    # ══ 2.1 Filter full epoch ══
    # Remove DC residual and HF noise; full-epoch kernel avoids edge distortion.
    epochs.filter(l_freq=HIGHPASS_HZ, h_freq=LOWPASS_HZ, verbose=False)

    # ══ 2.2 Drop saturated channels ══
    evoked_full = epochs.average()
    bad_chs = [
        ch for ch, row in zip(epochs.ch_names, evoked_full.data)
        if np.max(np.abs(row)) > OUTLIER_THRESH_V
    ]
    if bad_chs:
        epochs.drop_channels(bad_chs)
        print(f"  {pct}%: dropped {len(bad_chs)} saturated: {bad_chs}")

    # ══ 2.3 Crop windows and average ══
    evoked_pre  = epochs.copy().crop(*PRE_WINDOW_S).average()
    evoked_post = epochs.copy().crop(*POST_WINDOW_S).average()

    pre_range_uv  = (evoked_pre.data.max()  - evoked_pre.data.min())  * 1e6
    post_range_uv = (evoked_post.data.max() - evoked_post.data.min()) * 1e6

    # ══ 2.4 Plot joint and save ══
    for label, evoked, times in [
        ("pre",  evoked_pre,  TOPOMAP_TIMES_PRE),
        ("post", evoked_post, TOPOMAP_TIMES_POST),
    ]:
        fig = evoked.plot_joint(
            times=times,
            title=f"EXP08 artremoved {label.upper()} | {pct}%  (n={evoked.nave})",
            ts_args={"gfp": True, "ylim": {"eeg": list(YLIM_UV)}},
            topomap_args={"outlines": "head"},
        )
        fig.set_size_inches(10.0, 6.0)
        fig.savefig(str(OUT_DIR / f"exp08_tep_{pct}pct_artremoved_{label}.png"), dpi=220, bbox_inches="tight")
        plt.close(fig)

    print(f"  {pct}%: saved PRE/POST  |  PRE range {pre_range_uv:7.2f} µV  |  POST range {post_range_uv:9.2f} µV")


# ============================================================
# 3) SUMMARY
# ============================================================

print(f"\n{'='*70}")
print(f"DONE: {len(INTENSITIES)*2} plots -> {OUT_DIR}")
print(f"{'='*70}")
