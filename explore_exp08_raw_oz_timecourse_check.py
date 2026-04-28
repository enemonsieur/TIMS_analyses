"""Plot one raw Oz time segment from the EXP08 continuous BrainVision recording."""

import os
from pathlib import Path
import warnings

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne


# ============================================================
# CONFIG
# ============================================================

VHDR_PATH = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp08-STIM-pulse_run01_10-100.vhdr")
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

CHANNEL = "Oz"  # current EXP08 filter-forensics channel
CROP_START_S = 914.0  # 100% block crop from explore_exp08_raw_pulse_view.py
CROP_DURATION_S = 5.0
CROP_STOP_S = CROP_START_S + CROP_DURATION_S

OUTPUT_PATH = OUTPUT_DIRECTORY / "exp08_raw_oz_100pct_timecourse_check.png"


# ============================================================
# 1) LOAD CONTINUOUS RAW RECORDING
# ============================================================

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Channels contain different highpass filters*")
    warnings.filterwarnings("ignore", message="Channels contain different lowpass filters*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels*")
    raw = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
if CHANNEL not in raw.ch_names:
    raise RuntimeError(f"Raw recording is missing requested channel: {CHANNEL}")
if CROP_STOP_S > raw.n_times / sfreq:
    raise RuntimeError("Requested crop extends beyond the raw recording duration.")

print("EXP08 raw Oz time-course check")
print(f"  source = {VHDR_PATH}")
print(f"  sfreq = {sfreq:.0f} Hz")
print(f"  channel = {CHANNEL}")
print(f"  crop = {CROP_START_S:.1f}-{CROP_STOP_S:.1f} s")
print("  representation = continuous raw crop; no epochs; no filtering; no averaging")


# ============================================================
# 2) EXTRACT ONE RAW CHANNEL SEGMENT
# ============================================================

segment = raw.copy().crop(tmin=CROP_START_S, tmax=CROP_STOP_S)
channel_uv = segment.copy().pick([CHANNEL]).get_data()[0] * 1e6
time_within_crop_s = segment.times - segment.times[0]


# ============================================================
# 3) PLOT RAW TIME COURSE
# ============================================================

fig, ax = plt.subplots(figsize=(11, 4.8))
ax.plot(time_within_crop_s, channel_uv, linewidth=0.8, color="#08519c")
ax.set_title("EXP08 raw Oz at 100% block: continuous VHDR crop, no epochs", fontsize=12, fontweight="bold")
ax.set_xlabel("Time within crop (s)")
ax.set_ylabel("Oz (uV)")
ax.grid(True, alpha=0.25, linewidth=0.6)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

fig.text(
    0.01,
    0.01,
    "Source: raw VHDR | crop 914-919 s | no filtering, no epochs, no averaging",
    fontsize=9,
    color="#4d4d4d",
)
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(OUTPUT_PATH, dpi=180)
plt.close(fig)

print(f"  saved = {OUTPUT_PATH}")
