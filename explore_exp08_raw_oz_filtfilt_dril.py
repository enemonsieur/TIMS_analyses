"""DRIL plot: show how filtfilt changes one raw EXP08 Oz time-course crop."""

import os
from pathlib import Path
import shutil
import warnings

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi, sosfiltfilt


# ============================================================
# CONFIG
# ============================================================

VHDR_PATH = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp08-STIM-pulse_run01_10-100.vhdr")
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

CHANNEL = "Oz"  # current EXP08 filter-forensics channel
CROP_START_S = 914.0  # raw 100% block crop from explore_exp08_raw_pulse_view.py
CROP_STOP_S = 919.0
FILTER_BAND_HZ = (11.0, 14.0)  # intentionally narrow enough to reveal ringing
FILTER_ORDER = 4
ZOOM_PRE_S = 0.45
ZOOM_POST_S = 1.20

OUTPUT_PATH = OUTPUT_DIRECTORY / "exp08_raw_oz_filtfilt_dril.png"
TMP_OUTPUT_PATH = Path(r"C:\tmp\exp08_raw_oz_filtfilt_dril.png")
SUMMARY_PATH = OUTPUT_DIRECTORY / "exp08_raw_oz_filtfilt_dril.txt"


# ============================================================
# 1) LOAD RAW CONTINUOUS CROP
# ============================================================

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Channels contain different highpass filters*")
    warnings.filterwarnings("ignore", message="Channels contain different lowpass filters*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels*")
    raw = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
if CHANNEL not in raw.ch_names:
    raise RuntimeError(f"Missing requested raw channel: {CHANNEL}")

segment = raw.copy().crop(tmin=CROP_START_S, tmax=CROP_STOP_S)
raw_v = segment.copy().pick([CHANNEL]).get_data()[0]
time_s = segment.times - segment.times[0]
raw_uv = raw_v * 1e6

# This only marks the largest deflection inside the already chosen raw crop.
artifact_index = int(np.argmin(raw_uv))
artifact_time_s = float(time_s[artifact_index])
zoom_start_s = artifact_time_s - ZOOM_PRE_S
zoom_stop_s = artifact_time_s + ZOOM_POST_S
zoom_mask = (time_s >= zoom_start_s) & (time_s <= zoom_stop_s)


# ============================================================
# 2) RUN ONE FORWARD-BACKWARD FILTER STEP BY STEP
# ============================================================

sos = butter(FILTER_ORDER, FILTER_BAND_HZ, btype="bandpass", fs=sfreq, output="sos")
n_sections = sos.shape[0]
padlen = 3 * (2 * n_sections + 1)

left_pad = 2 * raw_v[0] - raw_v[1:padlen + 1][::-1]
right_pad = 2 * raw_v[-1] - raw_v[-padlen - 1:-1][::-1]
padded_v = np.concatenate([left_pad, raw_v, right_pad])
padded_time_s = (np.arange(padded_v.size) - padlen) / sfreq

zi_forward = sosfilt_zi(sos) * padded_v[0]
forward_v, _ = sosfilt(sos, padded_v, zi=zi_forward)

reversed_forward_v = forward_v[::-1]
processing_index = np.arange(reversed_forward_v.size)
artifact_padded_index = artifact_index + padlen
artifact_processing_index = reversed_forward_v.size - 1 - artifact_padded_index

zi_backward = sosfilt_zi(sos) * reversed_forward_v[0]
backward_reversed_v, _ = sosfilt(sos, reversed_forward_v, zi=zi_backward)

manual_filtfilt_v = backward_reversed_v[::-1][padlen:-padlen]
scipy_filtfilt_v = sosfiltfilt(sos, raw_v, padtype="odd", padlen=padlen)
max_abs_difference_uv = float(np.max(np.abs((manual_filtfilt_v - scipy_filtfilt_v) * 1e6)))

zoom_padded_mask = (padded_time_s >= zoom_start_s) & (padded_time_s <= zoom_stop_s)
processing_mask = (
    (processing_index >= artifact_processing_index - int(ZOOM_POST_S * sfreq))
    & (processing_index <= artifact_processing_index + int(ZOOM_PRE_S * sfreq))
)


# ============================================================
# 3) PLOT THE DRIL TUTORIAL FIGURE
# ============================================================

fig, axes = plt.subplots(6, 1, figsize=(13, 15), constrained_layout=False)
fig.suptitle(
    "DRIL: filtfilt turns one raw Oz artifact into ringing before and after the artifact",
    fontsize=15,
    fontweight="bold",
)

def style_axis(axis, title, ylabel="uV"):
    axis.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
    axis.set_ylabel(ylabel)
    axis.grid(True, axis="y", color="#dddddd", lw=0.55, alpha=0.7)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def mark_artifact(axis):
    axis.axvline(artifact_time_s, color="black", lw=0.9, ls="--")
    axis.axvspan(artifact_time_s - 0.02, artifact_time_s + 0.04, color="#f2c94c", alpha=0.18, lw=0)


axes[0].plot(time_s, raw_uv, color="#4d4d4d", lw=0.85)
mark_artifact(axes[0])
style_axis(axes[0], "1. Define x[n]: one raw continuous Oz crop, no epochs, no filtering, no averaging")
axes[0].set_xlabel("Time within 914-919 s crop (s)")
axes[0].text(
    time_s[-1],
    np.nanpercentile(raw_uv, 92),
    r"$x[n]$ is the raw input",
    ha="right",
    fontsize=11,
)

axes[1].plot(time_s[zoom_mask], raw_uv[zoom_mask], color="#4d4d4d", lw=1.1)
mark_artifact(axes[1])
style_axis(axes[1], "2. Isolate the problem: the filter receives a huge impulse-like artifact")
axes[1].set_xlabel("Time within crop (s)")
axes[1].text(
    artifact_time_s + 0.06,
    np.nanmin(raw_uv[zoom_mask]),
    "large raw deflection enters the filter",
    color="#4d4d4d",
    fontsize=10,
    va="bottom",
)

axes[2].plot(padded_time_s[zoom_padded_mask], forward_v[zoom_padded_mask] * 1e6, color="#1f77b4", lw=1.25)
mark_artifact(axes[2])
style_axis(axes[2], "3. Route forward: a causal pass spreads artifact energy to later samples")
axes[2].set_xlabel("Time within crop (s)")
axes[2].text(
    zoom_start_s + 0.04,
    np.nanpercentile(forward_v[zoom_padded_mask] * 1e6, 10),
    r"$y_f[n]=F(x_{pad})[n]$",
    color="#1f77b4",
    fontsize=11,
)

axes[3].plot(processing_index[processing_mask], reversed_forward_v[processing_mask] * 1e6, color="#9467bd", lw=1.25)
axes[3].axvline(artifact_processing_index, color="black", lw=0.9, ls="--")
style_axis(axes[3], "4. Reverse: the values are flipped, so left-to-right processing now walks backward in real time")
axes[3].set_xlabel("Processing index after reverse")
axes[3].text(
    processing_index[processing_mask][-1],
    np.nanpercentile(reversed_forward_v[processing_mask] * 1e6, 90),
    "same values, opposite time order",
    ha="right",
    color="#9467bd",
    fontsize=10,
)

axes[4].plot(processing_index[processing_mask], backward_reversed_v[processing_mask] * 1e6, color="#ff7f0e", lw=1.25)
axes[4].axvline(artifact_processing_index, color="black", lw=0.9, ls="--")
style_axis(axes[4], "5. Route backward: the same causal rule now spreads energy toward earlier real time")
axes[4].set_xlabel("Processing index after reverse")
axes[4].text(
    processing_index[processing_mask][0],
    np.nanpercentile(backward_reversed_v[processing_mask] * 1e6, 12),
    r"$y_b[n]=F(reverse(y_f))[n]$",
    color="#ff7f0e",
    fontsize=11,
)

axes[5].plot(time_s[zoom_mask], manual_filtfilt_v[zoom_mask] * 1e6, color="#d62728", lw=1.35, label="manual step-by-step")
axes[5].plot(time_s[zoom_mask], scipy_filtfilt_v[zoom_mask] * 1e6, color="black", lw=0.85, ls="--", alpha=0.55, label="SciPy check")
mark_artifact(axes[5])
style_axis(axes[5], "6. Loop back: flip and trim; final filtfilt output rings on both sides of the artifact")
axes[5].set_xlabel("Time within crop (s)")
axes[5].legend(frameon=False, loc="lower right")

fig.text(
    0.01,
    0.018,
    "Source: raw BrainVision VHDR | Oz | crop 914-919 s | no epochs, no pulse extraction, no averaging. "
    f"Filter: Butterworth {FILTER_BAND_HZ[0]:.0f}-{FILTER_BAND_HZ[1]:.0f} Hz, order {FILTER_ORDER}.",
    fontsize=8.8,
    color="#4d4d4d",
)
fig.tight_layout(rect=(0, 0.04, 1, 0.985))
fig.savefig(OUTPUT_PATH, dpi=190)
plt.close(fig)

TMP_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
try:
    shutil.copy2(OUTPUT_PATH, TMP_OUTPUT_PATH)
    copied_path = TMP_OUTPUT_PATH
except PermissionError:
    copied_path = None


# ============================================================
# 4) SAVE NUMERIC ANCHORS FOR THE TEXT DRIL
# ============================================================

baseline_mask = (time_s >= artifact_time_s - 0.35) & (time_s <= artifact_time_s - 0.10)
baseline_uv = float(np.median(raw_uv[baseline_mask]))
artifact_uv = float(raw_uv[artifact_index])
artifact_deflection_uv = artifact_uv - baseline_uv

with open(SUMMARY_PATH, "w", encoding="utf-8") as summary_file:
    summary_file.write("EXP08 RAW OZ FILTFILT DRIL\n")
    summary_file.write("=" * 80 + "\n\n")
    summary_file.write(f"Source: {VHDR_PATH}\n")
    summary_file.write(f"Crop: {CROP_START_S:.1f}-{CROP_STOP_S:.1f} s\n")
    summary_file.write(f"Channel: {CHANNEL}\n")
    summary_file.write("Representation: continuous raw crop; no epochs; no pulse extraction; no averaging\n")
    summary_file.write(f"Sampling rate: {sfreq:.1f} Hz\n")
    summary_file.write(f"Artifact time within crop: {artifact_time_s:.3f} s\n")
    summary_file.write(f"Baseline median before artifact: {baseline_uv:.3f} uV\n")
    summary_file.write(f"Artifact trough: {artifact_uv:.3f} uV\n")
    summary_file.write(f"Artifact deflection: {artifact_deflection_uv:.3f} uV\n")
    summary_file.write(f"Filter: Butterworth {FILTER_BAND_HZ[0]:.1f}-{FILTER_BAND_HZ[1]:.1f} Hz, order {FILTER_ORDER}\n")
    summary_file.write(f"Padding length: {padlen} samples = {padlen / sfreq:.3f} s per edge\n")
    summary_file.write(f"Manual-vs-Scipy max abs difference: {max_abs_difference_uv:.9f} uV\n")
    summary_file.write(f"Figure: {OUTPUT_PATH}\n")
    summary_file.write(f"Figure copy: {copied_path}\n")

print(f"Saved figure: {OUTPUT_PATH}")
if copied_path is not None:
    print(f"Copied figure: {copied_path}")
print(f"Saved summary: {SUMMARY_PATH}")
print(f"Artifact time within crop: {artifact_time_s:.3f} s")
print(f"Artifact deflection: {artifact_deflection_uv:.1f} uV")
print(f"Manual-vs-Scipy max abs difference: {max_abs_difference_uv:.9f} uV")
