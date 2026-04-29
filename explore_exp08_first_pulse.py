"""Diagnostic: plot first 15 s of stim trace to identify exact first-pulse sample."""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import mne
import numpy as np

# ============================================================
# CONFIG
# ============================================================

DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp08-STIM-pulse_run01_10-100.vhdr"

# ════════════════════════════════════════════════════════════════════════════
# 1) LOAD STIM TRACE (first 15 s only)
# ════════════════════════════════════════════════════════════════════════════

# ══ 1.1 Read VHDR, extract stim channel ══
with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
stim_trace = raw.copy().pick(["stim"]).get_data()[0]
# → (n_samples,) stim voltage in volts

# ══ 1.2 Crop to first 15 s ══
n_display = int(30 * sfreq)   # 15000 samples at 1 kHz
short_trace = stim_trace[:n_display]
sample_axis = np.arange(n_display)
# → (15000,) sample indices — user reads x-axis to identify first-pulse sample

# ══ 1.3 Plot stim vs. sample index ══
fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(sample_axis, short_trace * 1e6, linewidth=0.8)
ax.set_xlabel("Sample index (= ms at 1 kHz)")
ax.set_ylabel("STIM voltage (µV)")
ax.set_title("EXP08 stim trace — first 15 s  |  read off sample of first pulse peak")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
# User reports exact sample number → used as FIRST_PULSE_SAMPLE in Phase B
