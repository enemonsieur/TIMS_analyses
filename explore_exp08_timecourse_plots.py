"""Plot STIM channel voltage and EEG timecourse from EXP08 dose-response recording."""

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
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# VHDR Recording (31 EEG + stim, 1000 Hz)
# ├─ Extract: stim trace → plot with log y-axis
# │  └─ OUTPUT: stim_timecourse.png
# │
# └─ Extract: EEG channels → plot timecourse (MNE native)
#    └─ OUTPUT: eeg_timecourse.png

# ============================================================
# 1) LOAD & PREPARE
# ============================================================

# ══ 1.1 Read BrainVision file, suppress metadata warnings ══
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc*")
    raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
duration_s = raw.n_times / sfreq

print(f"Loaded: {duration_s:.1f} s, {len(raw.ch_names)} channels, {sfreq:.0f} Hz")

# ============================================================
# 2) PLOT STIM TIMECOURSE
# ============================================================

# ══ 2.1 Extract stim trace and prepare time axis ══
stim_trace = raw.copy().pick(["stim"]).get_data()[0]
# → (n_samples,) stim voltage in volts
time_s = np.arange(len(stim_trace)) / sfreq

# ══ 2.2 Plot stim with log y-axis ══
# Absolute value removes sign ambiguity; log scale reveals pulse structure
fig, ax = plt.subplots(figsize=(14, 4))
ax.semilogy(time_s, np.abs(stim_trace) * 1e6, linewidth=0.5, alpha=0.8)
ax.set_xlabel("Time (s)")
ax.set_ylabel("STIM voltage (µV, log scale)")
ax.set_title("EXP08: STIM channel timecourse")
ax.grid(True, alpha=0.3, which='both')
fig.tight_layout()
fig.savefig(OUTPUT_DIRECTORY / "01_stim_timecourse.png", dpi=100)
plt.close()

print(f"Saved: 01_stim_timecourse.png")

# ============================================================
# 3) PLOT EEG TIMECOURSE
# ============================================================

# ══ 3.1 Pick EEG channels ══
raw_eeg = raw.copy().pick("eeg")
# → (31, n_samples) EEG data

# ══ 3.2 Plot using MNE native plot ══
# MNE's plot() handles scaling, channel ordering, and scrolling natively
fig = raw_eeg.plot(duration=10, n_channels=31, show=False)
fig.savefig(OUTPUT_DIRECTORY / "02_eeg_timecourse.png", dpi=100)
plt.close()

print(f"Saved: 02_eeg_timecourse.png")
print("\nDone.")
