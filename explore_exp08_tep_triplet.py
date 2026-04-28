"""Extract TMS-evoked potentials (TEPs) from EXP08 run02 triplet epochs.

NEVER filter on the full epoch — crop PRE and POST first, filter each window separately.

PIPELINE:
  Load triplet ON epochs (10 intensities, exp08t_ prefix)
  ├─ Per intensity:
  │   ├─ Crop POST (0.020–0.500 s) → decay removal (POST only) → bandpass
  │   ├─ Crop PRE (-0.300 to -0.005 s) → bandpass only
  │   ├─ Drop saturated channels: POST evoked peak > 10 mV after decay removal
  │   ├─ Baseline correction: subtract per-epoch PRE mean from POST
  │   ├─ Average → evoked_pre, evoked_post
  │   └─ plot_joint for PRE and POST → PNG
  └─ Output: EXP08/TEPs_triplet/exp08t_tep_{pct}pct_{pre,post}.png
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
OUT_DIR = FIF_DIR / "TEPs_triplet"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTENSITIES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

# Windows (applied AFTER cropping from the -0.6 to +0.7 s ON epoch)
PRE_WINDOW_S   = (-0.300, -0.005)  # 295 ms: pre-stimulus, no artifact
POST_WINDOW_S  = ( 0.020,  0.500)  # 480 ms: post-triplet onset, decay present

DECAY_FIT_START_S   = 0.020        # fit A·exp(-t/τ)+C from start of POST window
HIGHPASS_HZ         = 1.0          # per-window high-pass; raise to 3 Hz if MNE warns about edge effects
LOWPASS_HZ          = 80.0
OUTLIER_THRESHOLD_V = 0.010        # drop channels where POST evoked peak > 10 mV after decay removal

TOPOMAP_TIMES_PRE  = [-0.25, -0.15, -0.05]
TOPOMAP_TIMES_POST = [ 0.030,  0.10,  0.20]
YLIM_UV = (-5.0, 5.0)


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# exp08t_epochs_{pct}pct_on-epo.fif (10 intensities, -0.6 to +0.7 s)
# ├─ Per intensity:
# │   ├─ crop → POST (0.020–0.500 s): decay removal → bandpass 1–80 Hz
# │   ├─ crop → PRE (-0.300 to -0.005 s): bandpass 1–80 Hz only
# │   ├─ drop saturated channels from POST evoked (> 10 mV) → apply to PRE too
# │   ├─ baseline correct: per-epoch subtract mean(PRE) from POST
# │   ├─ average → evoked_pre / evoked_post
# │   └─ plot_joint → PNG (PRE and POST saved separately)
# └─ Output: TEPs_triplet/exp08t_tep_{pct}pct_{pre,post}.png


# ============================================================
# 1) LOAD EPOCHS
# ============================================================

print("=" * 70)
print("EXP08 TRIPLET TEP EXTRACTION")
print("=" * 70)

epochs_all = {}
for pct in INTENSITIES:
    fif_path = FIF_DIR / f"exp08t_epochs_{pct}pct_on-epo.fif"
    if not fif_path.exists():
        raise FileNotFoundError(f"Missing: {fif_path}\nRun explore_exp08_triplet_epochs.py first.")
    epochs_all[pct] = mne.read_epochs(str(fif_path), preload=True, verbose=False)

sfreq = float(epochs_all[INTENSITIES[0]].info["sfreq"])
print(f"Loaded: {sfreq:.0f} Hz, {len(epochs_all[INTENSITIES[0]].ch_names)} EEG channels\n")
print(f"PRE  window: {PRE_WINDOW_S[0]:.3f} to {PRE_WINDOW_S[1]:.3f} s  ({int((-PRE_WINDOW_S[0]+PRE_WINDOW_S[1])*1000)} ms)")
print(f"POST window: {POST_WINDOW_S[0]:.3f} to {POST_WINDOW_S[1]:.3f} s  ({int((POST_WINDOW_S[1]-POST_WINDOW_S[0])*1000)} ms)")
print(f"Filter: {HIGHPASS_HZ}–{LOWPASS_HZ} Hz  |  Decay fit from {DECAY_FIT_START_S*1000:.0f} ms\n")


# ============================================================
# 2) PROCESS EACH INTENSITY
# ============================================================

for pct in INTENSITIES:

    # ══ 2.1 Crop PRE and POST from the raw ON epoch ══
    epochs_post = epochs_all[pct].copy().crop(*POST_WINDOW_S)
    epochs_pre  = epochs_all[pct].copy().crop(*PRE_WINDOW_S)

    # ══ 2.2 Decay removal on POST window only ══
    # Fit A·exp(-t/τ)+C on POST evoked from DECAY_FIT_START_S onward; subtract per channel.
    epochs_post = preprocessing.subtract_exponential_decay(
        epochs_post,
        fit_start_s=DECAY_FIT_START_S,
        outlier_threshold_v=OUTLIER_THRESHOLD_V,
    )

    # ══ 2.3 Drop saturated channels from POST evoked, apply same drop to PRE ══
    evoked_post_check = epochs_post.average()
    bad_chs = [
        epochs_post.ch_names[i]
        for i in range(len(epochs_post.ch_names))
        if np.max(np.abs(evoked_post_check.data[i])) > OUTLIER_THRESHOLD_V
    ]
    n_total = len(epochs_post.ch_names)
    if bad_chs and len(bad_chs) < n_total:
        epochs_post.drop_channels(bad_chs)
        epochs_pre.drop_channels(bad_chs)
        print(f"  {pct}%: dropped {len(bad_chs)} saturated channels: {bad_chs}")
    elif bad_chs:
        print(f"  {pct}%: WARNING all {n_total} channels exceed threshold; retaining all")

    # ══ 2.4 Bandpass filter PRE and POST separately ══
    # Never filter across the full epoch (artifact at t=0 causes ringing in PRE).
    # Use IIR (Butterworth filtfilt) — no kernel length constraint on short windows.
    epochs_pre.filter(l_freq=HIGHPASS_HZ,  h_freq=LOWPASS_HZ, method="iir", verbose=False)
    epochs_post.filter(l_freq=HIGHPASS_HZ, h_freq=LOWPASS_HZ, method="iir", verbose=False)

    # ══ 2.5 Baseline correction: subtract per-epoch PRE mean from POST ══
    pre_means = np.mean(epochs_pre.get_data(), axis=2, keepdims=True)  # → (n_epochs, n_ch, 1)
    epochs_post._data -= pre_means

    # ══ 2.6 Average across epochs ══
    evoked_pre  = epochs_pre.average()
    evoked_post = epochs_post.average()

    # ══ 2.7 Diagnostic: amplitude ranges ══
    pre_range  = (evoked_pre.data.min()  * 1e6, evoked_pre.data.max()  * 1e6)
    post_range = (evoked_post.data.min() * 1e6, evoked_post.data.max() * 1e6)
    print(f"  {pct}%: n_ch={len(evoked_pre.ch_names)}  "
          f"PRE [{pre_range[0]:+.1f}, {pre_range[1]:+.1f}] µV  "
          f"POST [{post_range[0]:+.1f}, {post_range[1]:+.1f}] µV")

    # ══ 2.8 Plot joint for PRE and POST ══
    for label, evoked, topo_times in [
        ("pre",  evoked_pre,  TOPOMAP_TIMES_PRE),
        ("post", evoked_post, TOPOMAP_TIMES_POST),
    ]:
        fig = evoked.plot_joint(
            times=topo_times,
            title=f"EXP08 Triplet {label.upper()} | {pct}%  (n={evoked.nave})",
            ts_args={"gfp": True, "ylim": {"eeg": list(YLIM_UV)}},
            topomap_args={"outlines": "head"},
            show=False,
        )
        fig.set_size_inches(10.0, 6.0)
        fig.savefig(OUT_DIR / f"exp08t_tep_{pct}pct_{label}.png", dpi=220, bbox_inches="tight")
        plt.close(fig)


# ============================================================
# 3) SUMMARY
# ============================================================

print(f"\n{'='*70}")
print(f"DONE: {len(INTENSITIES) * 2} plots saved in {OUT_DIR}/")
print(f"  Naming: exp08t_tep_{{pct}}pct_pre.png / _post.png")
print(f"{'='*70}")
