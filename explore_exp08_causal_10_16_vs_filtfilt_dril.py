"""DRIL: compare causal 10-16 Hz filtering with filtfilt on one raw EXP08 pulse."""

import os
from pathlib import Path
import textwrap
import warnings

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import butter, dimpulse, hilbert, sos2tf, sosfilt, sosfilt_zi, sosfiltfilt


# ============================================================
# CONFIG
# ============================================================

VHDR_PATH = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp08-STIM-pulse_run01_10-100.vhdr")
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

CHANNEL = "Oz"  # raw EEG channel used in the EXP08 filter forensics
INTENSITY_PCT = 100
PULSES_PER_INTENSITY = 20
PULSE_INDEX_WITHIN_INTENSITY = 0
STIM_THRESHOLD_FRACTION = 0.08

RAW_WINDOW_S = (-1.0, 2.0)  # enough context for causal memory after the pulse
PULSE_ZOOM_S = (-0.30, 0.60)
FILTER_BAND_HZ = (10.0, 16.0)  # wider than 11-14 Hz and much wider than 12.5-13.5 Hz
FILTER_ORDER = 4

FIGURE_PATH = OUTPUT_DIRECTORY / "exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.png"
SUMMARY_PATH = OUTPUT_DIRECTORY / "exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.txt"


# ============================================================
# 1) VERIFY RAW PROVENANCE
# ============================================================

header_text = VHDR_PATH.read_text(encoding="utf-8", errors="replace")
required_header_phrases = [
    "DataFormat=BINARY",
    "DataOrientation=MULTIPLEXED",
    "BinaryFormat=IEEE_FLOAT_32",
    "SamplingInterval=1000",
    "S o f t w a r e  F i l t e r s",
    "Disabled",
]
missing_phrases = [phrase for phrase in required_header_phrases if phrase not in header_text]
if missing_phrases:
    raise RuntimeError(f"Raw header provenance check failed: missing {missing_phrases}")

if "Oz          17                 1" not in header_text or "DC              280              Off" not in header_text:
    raise RuntimeError("Raw header does not confirm Oz DC/280Hz/notch-off acquisition.")

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Channels contain different highpass filters*")
    warnings.filterwarnings("ignore", message="Channels contain different lowpass filters*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels*")
    raw = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
if sfreq != 1000.0:
    raise RuntimeError(f"Expected 1000 Hz raw sampling rate, got {sfreq}.")
if CHANNEL not in raw.ch_names or "stim" not in raw.ch_names:
    raise RuntimeError("Raw recording is missing required Oz or stim channel.")


# ============================================================
# 2) EXTRACT ONE 100% RAW PULSE
# ============================================================

stim_v = raw.copy().pick(["stim"]).get_data()[0]
stim_envelope = np.abs(hilbert(stim_v))
stim_threshold = float(np.max(stim_envelope)) * STIM_THRESHOLD_FRACTION
pulse_onsets = np.where(np.diff(stim_envelope > stim_threshold).astype(int) == 1)[0]

expected_pulses = 10 * PULSES_PER_INTENSITY
if pulse_onsets.size < expected_pulses:
    raise RuntimeError(f"Expected at least {expected_pulses} pulses, found {len(pulse_onsets)}.")

intensity_start_index = (INTENSITY_PCT // 10 - 1) * PULSES_PER_INTENSITY
pulse_sample = int(pulse_onsets[intensity_start_index + PULSE_INDEX_WITHIN_INTENSITY])

window_start_sample = pulse_sample + int(round(RAW_WINDOW_S[0] * sfreq))
window_stop_sample = pulse_sample + int(round(RAW_WINDOW_S[1] * sfreq))
if window_start_sample < 0 or window_stop_sample > raw.n_times:
    raise RuntimeError("Requested raw slice exceeds recording bounds.")

channel_index = raw.ch_names.index(CHANNEL)
raw_trace_v = raw.get_data(picks=[channel_index], start=window_start_sample, stop=window_stop_sample)[0]
time_s = (np.arange(raw_trace_v.size) + window_start_sample - pulse_sample) / sfreq
raw_trace_uv = raw_trace_v * 1e6


# ============================================================
# 3) RUN CAUSAL AND FILTFILT FILTERS
# ============================================================

sos = butter(FILTER_ORDER, FILTER_BAND_HZ, btype="bandpass", fs=sfreq, output="sos")
first_section = sos[0]
b0, b1, b2, a0, a1, a2 = [float(value) for value in first_section]

# Causal path: initialize to the first sample so the slice edge does not inject
# an artificial zero step. This still preserves forward-only artifact spreading.
zi = sosfilt_zi(sos) * raw_trace_v[0]
causal_v, _ = sosfilt(sos, raw_trace_v, zi=zi)
filtfilt_v = sosfiltfilt(sos, raw_trace_v)

section_input_v = raw_trace_v
section_output_v = np.zeros_like(section_input_v)
for sample_index in range(section_input_v.size):
    x0 = section_input_v[sample_index]
    x1 = section_input_v[sample_index - 1] if sample_index >= 1 else section_input_v[0]
    x2 = section_input_v[sample_index - 2] if sample_index >= 2 else section_input_v[0]
    y1 = section_output_v[sample_index - 1] if sample_index >= 1 else 0.0
    y2 = section_output_v[sample_index - 2] if sample_index >= 2 else 0.0
    section_output_v[sample_index] = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

equation_index = int(np.argmin(np.abs(time_s - 0.001)))
equation_terms_uv = {
    "b0*x[n]": b0 * section_input_v[equation_index] * 1e6,
    "b1*x[n-1]": b1 * section_input_v[equation_index - 1] * 1e6,
    "b2*x[n-2]": b2 * section_input_v[equation_index - 2] * 1e6,
    "-a1*y[n-1]": -a1 * section_output_v[equation_index - 1] * 1e6,
    "-a2*y[n-2]": -a2 * section_output_v[equation_index - 2] * 1e6,
}
equation_output_uv = float(sum(equation_terms_uv.values()))


# ============================================================
# 4) COMPUTE IMPULSE RESPONSE AND SUMMARY METRICS
# ============================================================

b, a = sos2tf(sos)
impulse_times = np.arange(0, 1.5, 1 / sfreq)
_, impulse_response = dimpulse((b, a, 1 / sfreq), n=impulse_times.size)
impulse_response = np.squeeze(impulse_response)
impulse_response /= np.max(np.abs(impulse_response))

zoom_mask = (time_s >= PULSE_ZOOM_S[0]) & (time_s <= PULSE_ZOOM_S[1])
pre_mask = (time_s >= -0.25) & (time_s <= -0.02)
post_mask = (time_s >= 0.02) & (time_s <= 0.50)

causal_uv = causal_v * 1e6
filtfilt_uv = filtfilt_v * 1e6
causal_pre_rms_uv = float(np.sqrt(np.mean(causal_uv[pre_mask] ** 2)))
filtfilt_pre_rms_uv = float(np.sqrt(np.mean(filtfilt_uv[pre_mask] ** 2)))
causal_post_rms_uv = float(np.sqrt(np.mean(causal_uv[post_mask] ** 2)))
filtfilt_post_rms_uv = float(np.sqrt(np.mean(filtfilt_uv[post_mask] ** 2)))


# ============================================================
# 5) MAKE CLAIM-FIRST DRIL FIGURE
# ============================================================

fig, axes = plt.subplots(2, 2, figsize=(12.4, 8.9), constrained_layout=False)
fig.suptitle(
    "Causal 10-16 Hz filtering is safer than filtfilt here because it does not ring backward",
    fontsize=14.8,
    fontweight="bold",
)


def style_time_axis(axis, ylabel):
    axis.axvline(0.0, color="#222222", lw=1.0, ls="--")
    axis.axvspan(-0.02, 0.04, color="#f2c94c", alpha=0.18, lw=0)
    axis.set_ylabel(ylabel)
    axis.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.55)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


raw_centered_uv = raw_trace_uv - np.median(raw_trace_uv[time_s < -0.2])
strike_index = int(np.argmin(raw_centered_uv))

ax = axes[0, 0]
ax.plot(time_s[zoom_mask], raw_centered_uv[zoom_mask], color="#4d4d4d", lw=1.15)
style_time_axis(ax, "Raw Oz\nuV from local median")
ax.set_title("1. Raw input: one measured 100% pulse is the strike", loc="left", fontsize=10.2)
ax.annotate(
    "artifact enters both filters",
    xy=(time_s[strike_index], raw_centered_uv[strike_index]),
    xytext=(0.12, np.nanpercentile(raw_centered_uv[zoom_mask], 20)),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#4d4d4d"},
    color="#4d4d4d",
    fontsize=9.2,
)
ax.set_xlabel("Time from pulse onset (s)")

ax = axes[0, 1]
ax.plot(impulse_times, impulse_response, color="#1f77b4", lw=1.3)
ax.axhline(0.0, color="#222222", lw=0.8)
ax.set_title("2. Wider bandpass has shorter memory: Q = 13/6 = 2.17", loc="left", fontsize=10.2)
ax.set_ylabel("Normalized impulse response")
ax.set_xlabel("Time after an impulse (s)")
ax.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.55)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.annotate(
    "still rings, but less like a narrow 13 Hz resonator",
    xy=(0.17, impulse_response[int(0.17 * sfreq)]),
    xytext=(0.40, 0.62),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#1f77b4"},
    color="#1f77b4",
    fontsize=9.1,
)

ax = axes[1, 0]
ax.plot(time_s[zoom_mask], causal_uv[zoom_mask], color="#1f77b4", lw=1.3)
style_time_axis(ax, "Causal sosfilt\n10-16 Hz (uV)")
ax.set_title("3. Causal filter: artifact energy spreads only forward in real time", loc="left", fontsize=10.2)
ax.text(
    -0.285,
    np.nanpercentile(causal_uv[zoom_mask], 86),
    f"pre-pulse RMS {causal_pre_rms_uv:.1f} uV",
    color="#1f77b4",
    fontsize=9.0,
)
ax.annotate(
    "post-pulse ringing remains",
    xy=(0.12, causal_uv[np.argmin(np.abs(time_s - 0.12))]),
    xytext=(0.24, np.nanpercentile(causal_uv[zoom_mask], 18)),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#1f77b4"},
    color="#1f77b4",
    fontsize=9.2,
)
ax.set_xlabel("Time from pulse onset (s)")

ax = axes[1, 1]
ax.plot(time_s[zoom_mask], filtfilt_uv[zoom_mask], color="#d62728", lw=1.35)
style_time_axis(ax, "filtfilt\n10-16 Hz (uV)")
ax.set_title("4. filtfilt: the same filter also spreads artifact backward", loc="left", fontsize=10.2)
ax.text(
    -0.285,
    np.nanpercentile(filtfilt_uv[zoom_mask], 86),
    f"pre-pulse RMS {filtfilt_pre_rms_uv:.1f} uV",
    color="#d62728",
    fontsize=9.0,
)
ax.annotate(
    "backward ringing before the pulse",
    xy=(-0.06, filtfilt_uv[np.argmin(np.abs(time_s + 0.06))]),
    xytext=(-0.27, np.nanpercentile(filtfilt_uv[zoom_mask], 28)),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#d62728"},
    color="#d62728",
    fontsize=9.2,
)
ax.set_xlabel("Time from pulse onset (s)")

figure_note = (
    "Measured figure. Source: original BrainVision VHDR/EEG, Oz, first 100% pulse. "
    "Header check: 1000 Hz, amplifier DC/280 Hz/notch-off, software filters disabled. "
    "Both filters use the same Butterworth 10-16 Hz order-4 design; only processing direction differs."
)
fig.text(0.01, 0.028, textwrap.fill(figure_note, width=170), fontsize=8.2, color="#4d4d4d")
fig.tight_layout(rect=(0, 0.08, 1, 0.94))
fig.savefig(FIGURE_PATH, dpi=220)
plt.close(fig)


# ============================================================
# 6) SAVE NUMERIC DRILL SUMMARY
# ============================================================

with open(SUMMARY_PATH, "w", encoding="utf-8") as summary_file:
    summary_file.write("EXP08 DRIL: CAUSAL 10-16 HZ VS FILTFILT\n")
    summary_file.write("=" * 80 + "\n\n")
    summary_file.write(f"Input raw file: {VHDR_PATH}\n")
    summary_file.write("Provenance: raw BrainVision VHDR/EEG, software filters disabled, no epochs, no averaging\n")
    summary_file.write(f"Channel: {CHANNEL}\n")
    summary_file.write(f"Selected pulse: {INTENSITY_PCT}% index {PULSE_INDEX_WITHIN_INTENSITY}; absolute sample {pulse_sample}\n")
    summary_file.write(f"Raw slice samples: start={window_start_sample}, stop={window_stop_sample}, n={raw_trace_v.size}\n")
    summary_file.write(f"Filter: Butterworth band-pass {FILTER_BAND_HZ[0]:.1f}-{FILTER_BAND_HZ[1]:.1f} Hz, order {FILTER_ORDER}, Q={13.0 / 6.0:.3f}\n")
    summary_file.write("\nExecuted first-section equation at t=0.001 s:\n")
    summary_file.write("y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]\n")
    for term_name, term_value in equation_terms_uv.items():
        summary_file.write(f"{term_name}: {term_value:.9f} uV\n")
    summary_file.write(f"sum -> y[n]: {equation_output_uv:.9f} uV\n\n")
    summary_file.write("RMS in pre/post windows:\n")
    summary_file.write(f"causal_pre_rms_uV (-0.25 to -0.02 s): {causal_pre_rms_uv:.6f}\n")
    summary_file.write(f"filtfilt_pre_rms_uV (-0.25 to -0.02 s): {filtfilt_pre_rms_uv:.6f}\n")
    summary_file.write(f"causal_post_rms_uV (0.02 to 0.50 s): {causal_post_rms_uv:.6f}\n")
    summary_file.write(f"filtfilt_post_rms_uV (0.02 to 0.50 s): {filtfilt_post_rms_uv:.6f}\n")
    summary_file.write(f"\nFigure: {FIGURE_PATH}\n")

print(f"Saved figure: {FIGURE_PATH}")
print(f"Saved summary: {SUMMARY_PATH}")
print(f"Causal pre RMS: {causal_pre_rms_uv:.3f} uV")
print(f"Filtfilt pre RMS: {filtfilt_pre_rms_uv:.3f} uV")
print(f"Causal post RMS: {causal_post_rms_uv:.3f} uV")
print(f"Filtfilt post RMS: {filtfilt_post_rms_uv:.3f} uV")
