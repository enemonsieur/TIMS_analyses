"""What does one raw EEG channel look like at 10% vs 100% TIMS intensity?"""

from pathlib import Path
import warnings

import matplotlib
#matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne

# ============================================================
# CONFIG
# ============================================================

VHDR_PATH = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp08-STIM-pulse_run01_10-100.vhdr")
OUTPUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

CHANNEL = "stim"
WINDOW_S = 5.0         # duration to show per panel

# Rough block start times; tweak ±20 s if no pulse visible
CROPS = {
    "10%":  18.0+5,
    "100%": 911.0+3,
}


# ============================================================
# 1) LOAD
# ============================================================

with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    raw = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)

print(f"Loaded: {raw.n_times / raw.info['sfreq']:.1f} s @ {raw.info['sfreq']:.0f} Hz")


# ============================================================
# 2) PLOT — one panel per intensity
# ============================================================

fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=False)

for ax, (label, crop_start) in zip(axes, CROPS.items()):
    segment = raw.copy().crop(tmin=crop_start, tmax=crop_start + WINDOW_S) #.filter(l_freq=0.5, h_freq=None, verbose=False)  # gentle high-pass to remove slow drifts
    ch_uv = segment.pick(["stim"]).get_data()[0] * 1e6
    ch_uv = ch_uv - ch_uv.mean()  # demean —> (n_samples,) µV, raw unfiltered → (n_samples,) µV, raw unfiltered

    ax.plot(segment.times, ch_uv, linewidth=0.8, color="#08519c")
    ax.set_ylabel(f"{CHANNEL} (µV)")
    ax.set_title(f"{label}  (t = {crop_start:.0f} s)")
    ax.grid(True, alpha=0.3)
    #ax.set_ylim(-1000, 1000)

axes[-1].set_xlabel("Time within window (s)")
fig.suptitle(f"EXP08 — raw {CHANNEL}: 10% vs 100% TIMS artifact", fontsize=12)

fig.tight_layout()
out_path = OUTPUT_DIR / "exp08_raw_pulse_view.png"
fig.savefig(out_path, dpi=150)
plt.show()
#plt.close()

print(f"Saved: {out_path}")
