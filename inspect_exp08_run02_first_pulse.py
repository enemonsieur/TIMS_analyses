"""Test triplet artifact removal (fixed 50ms window) on EXP08 run02 first pulse."""

import os
os.environ["QT_API"] = "pyqt6"
os.environ["MPLBACKEND"] = "qtagg"

from pathlib import Path
import warnings
import numpy as np
import mne
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
VHDR = DATA_DIR / "exp08-STIM-triplet_run02_10-100.vhdr"

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    raw = mne.io.read_raw_brainvision(str(VHDR), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
print(f"Sampling rate: {sfreq} Hz")
print(f"Duration: {raw.times[-1]:.2f} s")

FIRST_PULSE = int(31.67 * sfreq)  # first pulse at 31.67 s
INTENSITIES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
N_PULSES = 20
def ms(x): return int(round(x / 1000.0 * sfreq))

# Construct pulse schedule (same as run01)
pulse_samples = FIRST_PULSE + np.arange(N_PULSES * len(INTENSITIES)) * int(round(5.0 * sfreq))
print(f"Total pulses: {pulse_samples.size}")
print(f"First pulse: {pulse_samples[0] / sfreq:.2f} s (sample {pulse_samples[0]})")
print(f"Last pulse: {pulse_samples[-1] / sfreq:.2f} s (sample {pulse_samples[-1]})")

# Get Oz channel index and raw data
oz_idx = raw.ch_names.index("Oz")
raw_data = raw.get_data()
clean_data = raw_data.copy()

pulse = int(pulse_samples[-10])  # LAST pulse
art_start = pulse + ms(-25)
art_end = pulse + ms(70)  # fixed 50 ms window for triplet

# Linear interpolation
idx = np.arange(art_start, art_end)
clean_data[oz_idx, idx] = np.linspace(
    clean_data[oz_idx, art_start],
    clean_data[oz_idx, art_end],
    idx.size,
    endpoint=False
)

# Plot before/after around first pulse
t_start = (pulse - ms(200)) / sfreq
t_end = (pulse + ms(300)) / sfreq
t_idx = np.arange(int((pulse - ms(200))), int((pulse + ms(300))))

plt.figure(figsize=(12, 4))
plt.plot(raw.times, raw_data[oz_idx, :] * 1e6, label="Raw Oz", alpha=0.7)
plt.plot(raw.times, clean_data[oz_idx, :] * 1e6, label="Cleaned (70ms window)", linewidth=2)
#plt.axvline(raw.times[pulse], color="red", linestyle="--", linewidth=1, label="LAST pulse (worst case)")
#plt.axvspan(raw.times[art_start], raw.times[art_end], alpha=0.2, color="red", label="Removal window (-25 to +70 ms)")
plt.xlabel("Time (s)")
plt.ylabel("Amplitude (µV)")
plt.title(f"EXP08 Run02: Triplet Artifact Removal at Last Pulse (Oz channel)")
plt.legend(frameon=False)
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
