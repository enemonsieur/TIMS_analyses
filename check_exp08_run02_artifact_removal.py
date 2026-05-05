"""Check artifact removal across all channels for 100% intensity (run02 triplets)."""

import os
os.environ["QT_API"] = "pyqt6"

from pathlib import Path
import warnings
import numpy as np
import mne
import matplotlib.pyplot as plt

DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
VHDR = DATA_DIR / "exp08-STIM-triplet_run02_10-100.vhdr"

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    raw = mne.io.read_raw_brainvision(str(VHDR), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
FIRST_PULSE = int(31.67 * sfreq)
INTENSITIES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
N_PULSES = 20
def ms(x): return int(round(x / 1000.0 * sfreq))

# All pulses across all intensities
all_pulses = FIRST_PULSE + np.arange(N_PULSES * len(INTENSITIES)) * int(round(5.0 * sfreq))

print(f"Testing {len(all_pulses)} pulses across ALL intensities")
print(f"Pulse range: {all_pulses[0]/sfreq:.2f}–{all_pulses[-1]/sfreq:.2f} s\n")

raw_data = raw.get_data()
clean_data = raw_data.copy()

# TODO: Check the parameters for removing artifacts, as some triplets weren't removed.
# Apply artifact removal to ALL pulses
for pulse in all_pulses.astype(int):
    art_start = pulse + ms(-25)
    art_end = pulse + ms(70)
    idx = np.arange(art_start, art_end)
    for ch in range(clean_data.shape[0]):
        clean_data[ch, idx] = np.linspace(
            clean_data[ch, art_start],
            clean_data[ch, art_end],
            idx.size,
            endpoint=False
        )

# Compute stats around ALL pulses (artifact window + margins)
window_start = int(all_pulses[0]) + ms(-25)
window_end = int(all_pulses[-1]) + ms(70)

print(f"{'Channel':<12} {'Raw Mean (µV)':<15} {'Raw SD (µV)':<15} {'Clean Mean (µV)':<15} {'Clean SD (µV)':<15}")
print("=" * 80)
for ch in range(raw_data.shape[0]):
    ch_name = raw.ch_names[ch]
    raw_mean = raw_data[ch, window_start:window_end].mean() * 1e6
    raw_std = raw_data[ch, window_start:window_end].std() * 1e6
    clean_mean = clean_data[ch, window_start:window_end].mean() * 1e6
    clean_std = clean_data[ch, window_start:window_end].std() * 1e6
    print(f"{ch_name:<12} {raw_mean:>14.2f} {raw_std:>14.2f} {clean_mean:>14.2f} {clean_std:>14.2f}")


# Plot before/after across all pulses
oz_idx = raw.ch_names.index("Oz")
plt.figure(figsize=(14, 5))
plt.plot(raw.times, raw_data[oz_idx, :] * 1e6, label="Raw Oz", alpha=0.7)
plt.plot(raw.times, clean_data[oz_idx, :] * 1e6, label="Cleaned (70ms window)", linewidth=2)
#plt.axvline(raw.times[pulse], color="red", linestyle="--", linewidth=1, label="LAST pulse (worst case)")
#plt.axvspan(raw.times[art_start], raw.times[art_end], alpha=0.2, color="red", label="Removal window (-25 to +70 ms)")
plt.xlabel("Time (s)")
plt.ylabel("Amplitude (µV)")
plt.title("EXP08 Run02: Artifact Removal Across ALL Pulses (Oz channel)")
plt.legend(frameon=False)
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
