"""Does SASS or SSD recover 13 Hz phase better than raw Oz after EXP08 run02 triplet artifact removal?"""

from pathlib import Path
import os
import numpy as np
import mne
import matplotlib.pyplot as plt
from scipy.signal import hilbert
from preprocessing import sass_demixing, ssd_demixing

os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(Path(__file__).resolve().parent / ".mne"))

# ============================================================
# CONFIG
# ============================================================
EPOCH_DIR      = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
RESULTS_TXT    = EPOCH_DIR / "exp08_run02_art_filtering_scores.txt"
ITPC_PATH      = EPOCH_DIR / "exp08_run02_itpc_artremoved_raw_sass_ssd_vs_gt.png"
INTENSITIES    = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
PHASE_WINDOW_S = (-0.5, 0.5)   # pulse-adjacent scoring window

# ============================================================
# PIPELINE OVERVIEW
# ============================================================
#   load 4 pre-filtered FIF files (all 200 triplets, event_id 1–10 per intensity)
#   → per intensity: select by event key → flatten (C, E*S) → SASS + SSD demixing
#   → apply demixing weights to signal-band data → Hilbert phase
#   → diff vs GT phase → |mean over epochs| = ITPC timecourse; |mean over epochs+time| = PLV
#   → write PLV table + save ITPC figure

# ============================================================
# 1) LOAD
# ============================================================
print("Loading 4 pre-filtered epoch files (run02 triplets)...")
kw = dict(preload=True, verbose=False)
on_epo    = mne.read_epochs(EPOCH_DIR / "exp08_run02_all_on_artremoved-epo.fif", **kw)
sig_epo   = mne.read_epochs(EPOCH_DIR / "exp08_run02_all_on_signal-epo.fif",     **kw)
noise_epo = mne.read_epochs(EPOCH_DIR / "exp08_run02_all_on_noise-epo.fif",      **kw)
loff_epo  = mne.read_epochs(EPOCH_DIR / "exp08_run02_all_lateoff_noise-epo.fif", **kw)
# → 4 files; all share times axis and event_id map (intensity_10pct … intensity_100pct)
# data shapes: (20, 28, 3001) per intensity; 28 channels include EEG + GT + STIM; 3001 samples = -1.0 to +2.0 s at 1000 Hz
# ============================================================
# 2) SHARED METADATA
# ============================================================
sfreq     = float(on_epo.info["sfreq"])
times     = on_epo.times
eeg_names = [ch for ch in on_epo.ch_names if ch not in {"ground_truth", "stim"}]
oz_idx    = eeg_names.index("Oz")
mask      = (times >= PHASE_WINDOW_S[0]) & (times <= PHASE_WINDOW_S[1])
ph_times  = times[mask]                  # (mask_samples,) for ITPC x-axis
on_oz   = on_epo.copy().pick("Oz").get_data()[:, 0, :] * 1e6  # (E, S) raw Oz in µV for sanity check
# ============================================================
# 3) PER-INTENSITY SCORING
# ============================================================
# results[pct][method] = {"plv": float, "itpc": (mask_samples,)}
# Methods: raw_oz (signal-band Oz sensor), sass, ssd, stim (timing control vs GT)
METHODS = ["raw_oz", "sass", "ssd", "stim"]
COLORS  = {"raw_oz": "#2C7BB6", "sass": "#009E73", "ssd": "#D95F02", "stim": "#6A51A3"}
results = {}

for pct in INTENSITIES:
    key  = f"intensity_{pct}pct"
    ns   = noise_epo[key].get_data(picks=eeg_names)          # (E, C, S) 4–20 Hz — SASS/SSD covariance inputs
    sig  = sig_epo[key].get_data(picks=eeg_names)            # (E, C, S) 12–14 Hz — demixing output + raw Oz phase
    loff = loff_epo[key].get_data(picks=eeg_names)           # (E, C, S) 4–20 Hz lateOFF — SASS denominator covariance
    gt   = sig_epo[key].get_data(picks="ground_truth")[:, 0, :]  # (E, S) 12–14 Hz reference phase
    stim = sig_epo[key].get_data(picks="stim")[:, 0, :]          # (E, S) 12–14 Hz pulse timing control

    # --- flatten (Channel, Epochs*Samples) for demixing covariance inputs ---
    C, E, S   = ns.shape[1], ns.shape[0], ns.shape[2]
    ns_flat   = ns.transpose(1, 0, 2).reshape(C, -1)         # (C, E*S) noise-band ON
    sig_flat  = sig.transpose(1, 0, 2).reshape(C, -1)        # (C, E*S) signal-band ON
    loff_flat = loff.transpose(1, 0, 2).reshape(C, -1)       # (C, E*S) noise-band lateOFF

    # --- spatial filters; demixing weights applied to signal-band data for clean phase output ---
    # SASS: noise-band ON-vs-lateOFF contrast; skip component 0 (artifact direction), take component 1
    sass_sig = (sass_demixing(ns_flat, loff_flat)[1] @ sig_flat).reshape(E, S)
    # SSD: signal-band numerator vs noise-band denominator; component 0 = canonical SSD output
    ssd_sig  = (ssd_demixing(sig_flat,  ns_flat)[0]  @ sig_flat).reshape(E, S)

    # --- Hilbert phase → ITPC timecourse + scalar PLV ---
    # ph(x): angle of analytic signal restricted to scoring mask → (E, mask_samples)
    # diff: complex unit vector (phase difference to GT per epoch per timepoint)
    # itpc = |mean over epochs| at each timepoint; plv = |mean over epochs and time|
    ph   = lambda x: np.angle(hilbert(x, axis=-1))[:, mask]
    gt_p = ph(gt)
    results[pct] = {}
    for sig_data, method in [
        (sig[:, oz_idx, :], "raw_oz"),
        (sass_sig,          "sass"),
        (ssd_sig,           "ssd"),
        (stim,              "stim"),
    ]:
        diff = np.exp(1j * (ph(sig_data) - gt_p))            # (E, mask_samples) complex unit vector
        results[pct][method] = {
            "plv":  float(np.abs(diff.mean())),              # scalar: mean over epochs and time
            "itpc": np.abs(diff.mean(axis=0)),               # (mask_samples,) ITPC time course
        }

    print(f"{pct}%  raw={results[pct]['raw_oz']['plv']:.3f}  "
          f"SASS={results[pct]['sass']['plv']:.3f}  "
          f"SSD={results[pct]['ssd']['plv']:.3f}  "
          f"stim={results[pct]['stim']['plv']:.3f}")


# ============================================================
# 4) WRITE PLV TABLE
# ============================================================
lines = [
    f"{pct}% PLV: raw={results[pct]['raw_oz']['plv']:.3f}, "
    f"SASS={results[pct]['sass']['plv']:.3f}, "
    f"SSD={results[pct]['ssd']['plv']:.3f}, "
    f"stim={results[pct]['stim']['plv']:.3f}"
    for pct in INTENSITIES
]
for line in lines:
    print(line)
RESULTS_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================
# 5) ITPC TIME-COURSE FIGURE
# ============================================================
fig, axes = plt.subplots(5, 2, figsize=(11, 12), sharex=True, sharey=True)
for ax, pct in zip(axes.ravel(), INTENSITIES):
    for m in METHODS:
        ax.plot(ph_times, results[pct][m]["itpc"], label=m, color=COLORS[m], linewidth=1.5)
    ax.axvline(0, color="0.65", linewidth=0.8)
    ax.set_title(f"{pct}%"); ax.set_ylim(0, 1.05); ax.grid(alpha=0.2)
axes[0, 0].legend(frameon=False, fontsize=8)
fig.supxlabel("Time relative to pulse (s)"); fig.supylabel("ITPC")
fig.suptitle("EXP08 Run02 13 Hz ITPC — raw Oz / SASS / SSD vs GT")
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(ITPC_PATH, dpi=180); plt.close(fig)
print(f"Saved {ITPC_PATH.name}")
