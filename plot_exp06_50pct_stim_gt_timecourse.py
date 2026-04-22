"""Plot average time course of STIM and ground_truth at 50% ON pulse."""

import warnings
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import mne
import preprocessing

# CONFIG
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR = DATA_DIR / "exp06-STIM-iTBS_run02.vhdr"
OUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TIME_WINDOW = (0.0, 2.0)
BLOCK_50PCT_START = 80
BLOCK_CYCLES = 20

# LOAD
with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    raw = mne.io.read_raw_brainvision(str(STIM_VHDR), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
stim_trace = raw.copy().pick(["stim"]).get_data()[0]
gt_trace = raw.copy().pick(["ground_truth"]).get_data()[0]

# DETECT BLOCKS
block_onsets, _ = preprocessing.detect_stim_blocks(stim_trace, sfreq, threshold_fraction=0.08)

# EXTRACT & AVERAGE
win_start = int(TIME_WINDOW[0] * sfreq)
win_end = int(TIME_WINDOW[1] * sfreq)
stim_epochs = []
gt_epochs = []

for i in range(BLOCK_50PCT_START, BLOCK_50PCT_START + BLOCK_CYCLES):
    ep_start = block_onsets[i] + win_start
    ep_end = block_onsets[i] + win_end
    if ep_end <= len(stim_trace):
        stim_epochs.append(stim_trace[ep_start:ep_end])
        gt_epochs.append(gt_trace[ep_start:ep_end])

stim_avg = np.mean(stim_epochs, axis=0)
gt_avg = np.mean(gt_epochs, axis=0)
time_s = np.arange(len(stim_avg)) / sfreq

# ITPC (Inter-Trial Phase Coherence)
from scipy.signal import hilbert
stim_analytic = np.array([hilbert(ep) for ep in stim_epochs])
gt_analytic = np.array([hilbert(ep) for ep in gt_epochs])
stim_phase = np.angle(stim_analytic)
gt_phase = np.angle(gt_analytic)
phase_diff = stim_phase - gt_phase
itpc = np.abs(np.mean(np.exp(1j * phase_diff), axis=0))
itpc_mean = np.mean(itpc)

print(f"ITPC (STIM vs GT): {itpc_mean:.4f}")

# PLOT
fig, ax1 = plt.subplots(figsize=(10, 5))
ax1.plot(time_s, gt_avg, color="black", linewidth=2.5, label="Ground Truth")
ax1.set_ylabel("GT (V)", fontsize=11, fontweight="bold")
ax1.grid(True, alpha=0.3)

ax2 = ax1.twinx()
ax2.plot(time_s, stim_avg, color="#FF6B6B", linewidth=2.5, label="STIM")
ax2.set_ylabel("STIM (V)", fontsize=11, color="#FF6B6B", fontweight="bold")

ax1.set_xlabel("Time (s)", fontsize=11, fontweight="bold")
fig.suptitle("50% ON: STIM vs GT Temporal Coupling (Averaged)", fontsize=12, fontweight="bold")
ax1.legend(loc="upper left", fontsize=10)
ax2.legend(loc="upper right", fontsize=10)

plt.tight_layout()
plt.savefig(OUT_DIR / "plot_exp06_50pct_stim_gt_timecourse.png", dpi=150, bbox_inches="tight")
print("Done.")
