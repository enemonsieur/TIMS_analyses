"""Show one zero-phase band-pass filter on one raw EXP08 pulse from the BrainVision file."""

import os
from pathlib import Path
import textwrap

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import butter, hilbert, sosfilt, sosfilt_zi, sosfiltfilt


# ============================================================
# CONFIG
# ============================================================

VHDR_PATH = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp08-STIM-pulse_run01_10-100.vhdr")
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

CHANNEL = "Oz"  # raw EEG channel to inspect
INTENSITY_PCT = 100
PULSES_PER_INTENSITY = 20
PULSE_INDEX_WITHIN_INTENSITY = 0  # first 100% pulse, one real pulse only
STIM_THRESHOLD_FRACTION = 0.08  # same raw-stim threshold used in explore_exp08_pulses.py

RAW_WINDOW_S = (-1.0, 2.0)  # direct continuous slice around the detected pulse
PULSE_ZOOM_S = (-0.25, 0.45)
EDGE_ZOOM_S = (-1.030, -0.930)
FILTER_BAND_HZ = (11.0, 14.0)
FILTER_ORDER = 4

FIGURE_PATH = OUTPUT_DIRECTORY / "exp08_raw_vhdr_filtfilt_step_drill_oz_100pct_single_pulse.png"
DATAVIZ_FIGURE_PATH = OUTPUT_DIRECTORY / "exp08_raw_vhdr_filtfilt_dataviz_oz_100pct_single_pulse.png"
SUMMARY_PATH = OUTPUT_DIRECTORY / "exp08_raw_vhdr_filtfilt_step_drill_oz_100pct_single_pulse.txt"


# ============================================================
# 1) VERIFY RAW PROVENANCE BEFORE TOUCHING THE SIGNAL
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

if "Low Cutoff [s]   High Cutoff [Hz]   Notch [Hz]" not in header_text:
    raise RuntimeError("Raw header does not expose amplifier cutoff/notch columns.")
if "Oz          17                 1" not in header_text or "DC              280              Off" not in header_text:
    raise RuntimeError("Raw header does not confirm Oz DC/280Hz/notch-off acquisition.")

raw = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)
sfreq = float(raw.info["sfreq"])
if sfreq != 1000.0:
    raise RuntimeError(f"Expected 1000 Hz raw sampling rate, got {sfreq}.")
if CHANNEL not in raw.ch_names or "stim" not in raw.ch_names:
    raise RuntimeError("Raw recording is missing required Oz or stim channel.")


# ============================================================
# 2) DETECT PULSES FROM CONTINUOUS RAW STIM CHANNEL
# ============================================================

stim_v = raw.copy().pick(["stim"]).get_data()[0]

# Match the recent EXP08 extraction script: detect pulse starts from the raw
# stim envelope, then assign sequential blocks to 10%, 20%, ..., 100%.
stim_envelope = np.abs(hilbert(stim_v))
stim_threshold = float(np.max(stim_envelope)) * STIM_THRESHOLD_FRACTION
pulse_onsets = np.where(np.diff(stim_envelope > stim_threshold).astype(int) == 1)[0]

expected_pulses = 10 * PULSES_PER_INTENSITY
if pulse_onsets.size < expected_pulses:
    raise RuntimeError(f"Expected at least {expected_pulses} pulses, found {len(pulse_onsets)}.")

intensity_start_index = (INTENSITY_PCT // 10 - 1) * PULSES_PER_INTENSITY
selected_pulse_index = intensity_start_index + PULSE_INDEX_WITHIN_INTENSITY
pulse_sample = int(pulse_onsets[selected_pulse_index])


# ============================================================
# 3) EXTRACT ONE RAW CONTINUOUS SLICE BY SAMPLE INDEX
# ============================================================

window_start_sample = pulse_sample + int(round(RAW_WINDOW_S[0] * sfreq))
window_stop_sample = pulse_sample + int(round(RAW_WINDOW_S[1] * sfreq))
if window_start_sample < 0 or window_stop_sample > raw.n_times:
    raise RuntimeError("Requested raw slice exceeds recording bounds.")

channel_index = raw.ch_names.index(CHANNEL)
raw_trace_v = raw.get_data(picks=[channel_index], start=window_start_sample, stop=window_stop_sample)[0]
stim_trace_v = raw.get_data(picks=["stim"], start=window_start_sample, stop=window_stop_sample)[0]
time_s = (np.arange(raw_trace_v.size) + window_start_sample - pulse_sample) / sfreq
raw_trace_uv = raw_trace_v * 1e6
stim_trace_uv = stim_trace_v * 1e6


# ============================================================
# 4) RUN ONE FILTER AND KEEP THE INTERMEDIATE ARRAYS
# ============================================================

sos = butter(
    FILTER_ORDER,
    FILTER_BAND_HZ,
    btype="bandpass",
    fs=sfreq,
    output="sos",
)
first_section = sos[0]
b0, b1, b2, a0, a1, a2 = [float(value) for value in first_section]

n_sections = sos.shape[0]
padlen = 3 * (2 * n_sections + 1)
if raw_trace_v.size <= padlen:
    raise RuntimeError("Raw slice is too short for the requested filtfilt padding length.")

left_pad = 2 * raw_trace_v[0] - raw_trace_v[1:padlen + 1][::-1]
right_pad = 2 * raw_trace_v[-1] - raw_trace_v[-padlen - 1:-1][::-1]
padded_trace_v = np.concatenate([left_pad, raw_trace_v, right_pad])
padded_time_s = (np.arange(padded_trace_v.size) - padlen) / sfreq + time_s[0]

zi_forward = sosfilt_zi(sos) * padded_trace_v[0]
forward_v, _ = sosfilt(sos, padded_trace_v, zi=zi_forward)

reversed_forward_v = forward_v[::-1]
reversed_real_time_s = padded_time_s[::-1]
processing_index = np.arange(reversed_forward_v.size)
pulse_padded_index = int(np.argmin(np.abs(padded_time_s - 0.0)))
pulse_processing_index = reversed_forward_v.size - 1 - pulse_padded_index

zi_backward = sosfilt_zi(sos) * reversed_forward_v[0]
backward_reversed_v, _ = sosfilt(sos, reversed_forward_v, zi=zi_backward)

manual_filtfilt_v = backward_reversed_v[::-1][padlen:-padlen]
scipy_filtfilt_v = sosfiltfilt(sos, raw_trace_v, padtype="odd", padlen=padlen)
max_abs_difference_uv = float(np.max(np.abs((manual_filtfilt_v - scipy_filtfilt_v) * 1e6)))


# ============================================================
# 5) EXECUTE ONE EQUATION SAMPLE FOR THE SUMMARY
# ============================================================

section_input_v = padded_trace_v
section_output_v = np.zeros_like(section_input_v)
for sample_index in range(section_input_v.size):
    x0 = section_input_v[sample_index]
    x1 = section_input_v[sample_index - 1] if sample_index >= 1 else 0.0
    x2 = section_input_v[sample_index - 2] if sample_index >= 2 else 0.0
    y1 = section_output_v[sample_index - 1] if sample_index >= 1 else 0.0
    y2 = section_output_v[sample_index - 2] if sample_index >= 2 else 0.0
    section_output_v[sample_index] = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

equation_index = int(np.argmin(np.abs(padded_time_s - 0.001)))
equation_terms_uv = {
    "b0*x[n]": b0 * section_input_v[equation_index] * 1e6,
    "b1*x[n-1]": b1 * section_input_v[equation_index - 1] * 1e6,
    "b2*x[n-2]": b2 * section_input_v[equation_index - 2] * 1e6,
    "-a1*y[n-1]": -a1 * section_output_v[equation_index - 1] * 1e6,
    "-a2*y[n-2]": -a2 * section_output_v[equation_index - 2] * 1e6,
}
equation_output_uv = float(sum(equation_terms_uv.values()))


# ============================================================
# 6) MAKE CLAIM-FIRST FIGURE
# ============================================================

fig, axes = plt.subplots(6, 1, figsize=(12, 14), constrained_layout=False)
fig.suptitle(
    "Raw VHDR only: one pulse enters filtfilt, then the processing order reverses",
    fontsize=15,
    fontweight="bold",
)

def style_axis(axis, title, ylabel="uV"):
    axis.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
    axis.set_ylabel(ylabel)
    axis.grid(True, axis="y", color="#dddddd", lw=0.5, alpha=0.65)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


pulse_mask = (time_s >= PULSE_ZOOM_S[0]) & (time_s <= PULSE_ZOOM_S[1])
padded_pulse_mask = (padded_time_s >= PULSE_ZOOM_S[0]) & (padded_time_s <= PULSE_ZOOM_S[1])
edge_mask = (padded_time_s >= EDGE_ZOOM_S[0]) & (padded_time_s <= EDGE_ZOOM_S[1])
real_edge_mask = (time_s >= EDGE_ZOOM_S[0]) & (time_s <= EDGE_ZOOM_S[1])
processing_mask = (
    (processing_index >= pulse_processing_index - int(0.45 * sfreq))
    & (processing_index <= pulse_processing_index + int(0.25 * sfreq))
)

ax = axes[0]
ax.plot(time_s[pulse_mask], raw_trace_uv[pulse_mask], color="#4d4d4d", lw=1.2)
stim_scaled = stim_trace_uv[pulse_mask] / max(np.max(np.abs(stim_trace_uv[pulse_mask])), 1.0)
stim_scaled *= 0.15 * np.ptp(raw_trace_uv[pulse_mask])
stim_scaled += np.nanpercentile(raw_trace_uv[pulse_mask], 8)
ax.plot(time_s[pulse_mask], stim_scaled, color="#c44e52", lw=0.9, label="stim timing only")
ax.axvline(0.0, color="black", lw=0.9, ls="--")
ax.axvspan(-0.02, 0.04, color="#f2c94c", alpha=0.18, lw=0)
style_axis(ax, "1. Raw input is one continuous VHDR slice: no epochs, no averaging")
ax.text(0.42, np.nanpercentile(raw_trace_uv[pulse_mask], 95), r"$x[n]$", ha="right", fontsize=11)
ax.legend(frameon=False, loc="lower right")

ax = axes[1]
ax.plot(padded_time_s[edge_mask], padded_trace_v[edge_mask] * 1e6, color="#7f7f7f", lw=1.2, label="padded sequence")
ax.plot(time_s[real_edge_mask], raw_trace_uv[real_edge_mask], color="#222222", lw=1.6, label="real raw samples")
ax.axvspan(padded_time_s[0], time_s[0], color="#c44e52", alpha=0.16, lw=0)
ax.axvline(time_s[0], color="black", lw=0.9, ls="--")
style_axis(ax, "2. Padding is synthetic and only exists at the slice edge")
ax.text(padded_time_s[3], np.nanpercentile(padded_trace_v[edge_mask] * 1e6, 92), "synthetic left pad", color="#c44e52", fontsize=10)
ax.legend(frameon=False, loc="lower right")

ax = axes[2]
ax.plot(padded_time_s[padded_pulse_mask], forward_v[padded_pulse_mask] * 1e6, color="#1f77b4", lw=1.3)
ax.axvline(0.0, color="black", lw=0.9, ls="--")
ax.axvspan(-0.02, 0.04, color="#f2c94c", alpha=0.18, lw=0)
style_axis(ax, "3. Forward pass: causal memory makes the pulse ring after it")
ax.text(
    PULSE_ZOOM_S[0] + 0.02,
    np.nanpercentile(forward_v[padded_pulse_mask] * 1e6, 8),
    r"$y[n]=b_0x[n]+b_1x[n-1]+b_2x[n-2]-a_1y[n-1]-a_2y[n-2]$",
    color="#1f77b4",
    fontsize=10.5,
)

ax = axes[3]
ax.plot(processing_index[processing_mask], reversed_forward_v[processing_mask] * 1e6, color="#9467bd", lw=1.3)
ax.axvline(pulse_processing_index, color="black", lw=0.9, ls="--")
style_axis(ax, "4. Reverse means processing order flips: index increases while real time moves backward")
ax.set_xlabel("Processing index after reverse")
ax.text(
    processing_index[processing_mask][-1],
    np.nanpercentile(reversed_forward_v[processing_mask] * 1e6, 92),
    f"left-to-right processing now goes from real t={reversed_real_time_s[processing_mask][0]:.2f}s to {reversed_real_time_s[processing_mask][-1]:.2f}s",
    ha="right",
    color="#9467bd",
    fontsize=10,
)

ax = axes[4]
ax.plot(processing_index[processing_mask], backward_reversed_v[processing_mask] * 1e6, color="#ff7f0e", lw=1.3)
ax.axvline(pulse_processing_index, color="black", lw=0.9, ls="--")
style_axis(ax, "5. Backward pass: same causal rule, but later real time is now the past")
ax.set_xlabel("Processing index after reverse")
ax.text(
    processing_index[processing_mask][0],
    np.nanpercentile(backward_reversed_v[processing_mask] * 1e6, 8),
    r"$y_b[n]=F(reverse(y_f))[n]$",
    color="#ff7f0e",
    fontsize=11,
)

ax = axes[5]
ax.plot(time_s[pulse_mask], manual_filtfilt_v[pulse_mask] * 1e6, color="#d62728", lw=1.3, label="manual")
ax.plot(time_s[pulse_mask], scipy_filtfilt_v[pulse_mask] * 1e6, color="black", lw=0.8, alpha=0.55, ls="--", label="SciPy check")
ax.axvline(0.0, color="black", lw=0.9, ls="--")
ax.axvspan(-0.02, 0.04, color="#f2c94c", alpha=0.18, lw=0)
style_axis(ax, "6. Flip back and trim: ringing is now visible before and after the pulse")
ax.set_xlabel("Time relative to detected pulse onset (s)")
ax.legend(frameon=False, loc="lower right")

fig.text(
    0.01,
    0.018,
    "Source is the original BrainVision VHDR/EEG. Header check: binary float32, 1000 Hz, amplifier DC/280 Hz/notch-off, software filters disabled. "
    "No MNE Epochs or saved FIF files are used.",
    fontsize=8.4,
    color="#4d4d4d",
)
fig.tight_layout(rect=(0, 0.04, 1, 0.985))
fig.savefig(FIGURE_PATH, dpi=220)
plt.close(fig)


# ============================================================
# 7) MAKE CLAIM-FIRST DATAVIZ FIGURE
# ============================================================

fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.8), constrained_layout=False)
fig.suptitle(
    "The EXP08 pulse rings because the 11-14 Hz filter has output memory",
    fontsize=15,
    fontweight="bold",
)


def style_claim_axis(axis, ylabel):
    axis.set_ylabel(ylabel)
    axis.axvline(0.0, color="#222222", lw=1.0, ls="--")
    axis.axvspan(-0.02, 0.04, color="#f2c94c", alpha=0.20, lw=0)
    axis.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.55)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


forward_trimmed_uv = forward_v[padlen:-padlen] * 1e6
final_filtfilt_uv = manual_filtfilt_v * 1e6

ax = axes[0, 0]
raw_centered_uv = raw_trace_uv - np.median(raw_trace_uv[time_s < -0.2])
strike_sample_index = int(np.argmin(raw_centered_uv))
ax.plot(time_s[pulse_mask], raw_centered_uv[pulse_mask], color="#4d4d4d", lw=1.25)
style_claim_axis(ax, "Raw Oz\nuV from local median")
ax.set_title("1. The measured pulse is the strike", loc="left", fontsize=10.5)
ax.annotate(
    "raw artifact enters the filter",
    xy=(time_s[strike_sample_index], raw_centered_uv[strike_sample_index]),
    xytext=(0.10, np.nanpercentile(raw_centered_uv[pulse_mask], 24)),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#4d4d4d"},
    fontsize=9.5,
    color="#4d4d4d",
)
ax.set_xlabel("Time from pulse onset (s)")

ax = axes[0, 1]
input_terms_uv = float(
    equation_terms_uv["b0*x[n]"] + equation_terms_uv["b1*x[n-1]"] + equation_terms_uv["b2*x[n-2]"]
)
memory_terms_uv = float(equation_terms_uv["-a1*y[n-1]"] + equation_terms_uv["-a2*y[n-2]"])
bar_labels = ["recent raw\nx terms", "previous output\nmemory terms", "current output\ny[n]"]
bar_values = [input_terms_uv, memory_terms_uv, equation_output_uv]
bar_colors = ["#8c8c8c", "#1f77b4", "#d62728"]
bars = ax.bar(bar_labels, bar_values, color=bar_colors, width=0.62)
ax.axhline(0.0, color="#222222", lw=0.8)
ax.set_title("2. One executed equation: memory dominates the next output", loc="left", fontsize=10.5)
ax.set_ylabel("First SOS contribution at t=0.001 s (uV)")
ax.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.55)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for bar, value in zip(bars, bar_values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        value + 0.0012,
        f"{value:.5f}",
        ha="center",
        va="bottom",
        fontsize=8.6,
        color="#222222",
    )
ax.text(
    0.02,
    0.93,
    "y[n] = raw input terms + previous-output memory",
    transform=ax.transAxes,
    fontsize=9.3,
    color="#4d4d4d",
    va="top",
)

ax = axes[1, 0]
ax.plot(time_s[pulse_mask], forward_trimmed_uv[pulse_mask], color="#1f77b4", lw=1.35)
style_claim_axis(ax, "Forward pass\nuV")
ax.set_title("3. Forward pass: the resonator rings after the strike", loc="left", fontsize=10.5)
ax.annotate(
    "ringing after the pulse",
    xy=(0.11, forward_trimmed_uv[np.argmin(np.abs(time_s - 0.11))]),
    xytext=(0.17, np.nanpercentile(forward_trimmed_uv[pulse_mask], 84)),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#1f77b4"},
    fontsize=9.5,
    color="#1f77b4",
)
ax.set_xlabel("Time from pulse onset (s)")

ax = axes[1, 1]
ax.plot(time_s[pulse_mask], final_filtfilt_uv[pulse_mask], color="#d62728", lw=1.45)
style_claim_axis(ax, "Final filtfilt\nuV")
ax.set_title("4. filtfilt runs the same resonator backward, then flips back", loc="left", fontsize=10.5)
ax.annotate(
    "pre-pulse ringing",
    xy=(-0.055, final_filtfilt_uv[np.argmin(np.abs(time_s + 0.055))]),
    xytext=(-0.23, np.nanpercentile(final_filtfilt_uv[pulse_mask], 85)),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#d62728"},
    fontsize=9.5,
    color="#d62728",
)
ax.annotate(
    "post-pulse ringing",
    xy=(0.10, final_filtfilt_uv[np.argmin(np.abs(time_s - 0.10))]),
    xytext=(0.18, np.nanpercentile(final_filtfilt_uv[pulse_mask], 18)),
    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#d62728"},
    fontsize=9.5,
    color="#d62728",
)
ax.set_xlabel("Time from pulse onset (s)")

figure_note = (
    "Measured figure. Source: original BrainVision VHDR/EEG, Oz, first 100% pulse. "
    "Header check: 1000 Hz, amplifier DC/280 Hz/notch-off, software filters disabled. "
    "Filter: Butterworth 11-14 Hz, order 4, forward-backward sosfiltfilt."
)
fig.text(0.01, 0.026, textwrap.fill(figure_note, width=170), fontsize=8.4, color="#4d4d4d")
fig.tight_layout(rect=(0, 0.08, 1, 0.94))
fig.savefig(DATAVIZ_FIGURE_PATH, dpi=220)
plt.close(fig)


# ============================================================
# 7) WRITE NUMERIC DRILL NOTES
# ============================================================

sample_times_s = np.array([-0.050, 0.000, 0.050, 0.100])
sample_rows = []
for sample_time_s in sample_times_s:
    sample_index = int(np.argmin(np.abs(time_s - sample_time_s)))
    sample_rows.append(
        (
            float(time_s[sample_index]),
            int(window_start_sample + sample_index),
            float(raw_trace_v[sample_index] * 1e6),
            float(manual_filtfilt_v[sample_index] * 1e6),
            float(scipy_filtfilt_v[sample_index] * 1e6),
        )
    )

with open(SUMMARY_PATH, "w", encoding="utf-8") as summary_file:
    summary_file.write("EXP08 FILTFILT STEP DRILL: RAW VHDR SINGLE PULSE\n")
    summary_file.write("=" * 80 + "\n\n")
    summary_file.write(f"Input raw file: {VHDR_PATH}\n")
    summary_file.write("Provenance check passed:\n")
    summary_file.write("  DataFormat=BINARY, DataOrientation=MULTIPLEXED, BinaryFormat=IEEE_FLOAT_32\n")
    summary_file.write("  SamplingInterval=1000 us -> 1000 Hz\n")
    summary_file.write("  Amplifier setup: Oz low cutoff DC, high cutoff 280 Hz, notch Off\n")
    summary_file.write("  Software Filters: Disabled\n")
    summary_file.write("  No MNE Epochs, no saved FIF, no averaging\n\n")
    summary_file.write("Pulse timing source: same raw-stim Hilbert envelope threshold used in explore_exp08_pulses.py\n")
    summary_file.write(f"  threshold_fraction={STIM_THRESHOLD_FRACTION}, threshold={stim_threshold:.9g} V, detected_edges={pulse_onsets.size}\n")
    summary_file.write(f"Selected pulse: {INTENSITY_PCT}% index {PULSE_INDEX_WITHIN_INTENSITY}; absolute sample {pulse_sample}\n")
    summary_file.write(f"Raw slice samples: start={window_start_sample}, stop={window_stop_sample}, n={raw_trace_v.size}\n")
    summary_file.write(f"Channel: {CHANNEL}\n")
    summary_file.write(f"Filter: Butterworth band-pass {FILTER_BAND_HZ[0]:.1f}-{FILTER_BAND_HZ[1]:.1f} Hz, order {FILTER_ORDER}\n")
    summary_file.write(f"Padding length: {padlen} samples = {padlen / sfreq:.3f} s each side\n")
    summary_file.write(f"Manual-vs-Scipy max absolute difference: {max_abs_difference_uv:.6f} uV\n\n")
    summary_file.write(f"DATAVIZ figure: {DATAVIZ_FIGURE_PATH}\n\n")
    summary_file.write("First SOS section coefficients:\n")
    summary_file.write(f"b0={b0:.12g}, b1={b1:.12g}, b2={b2:.12g}, a1={a1:.12g}, a2={a2:.12g}\n\n")
    summary_file.write("Executed equation at one sample near pulse onset:\n")
    summary_file.write("y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]\n")
    summary_file.write(f"sample_index={equation_index}, time={padded_time_s[equation_index]:.6f}s\n")
    for term_name, term_value in equation_terms_uv.items():
        summary_file.write(f"{term_name}: {term_value:.9f} uV\n")
    summary_file.write(f"sum -> y[n]: {equation_output_uv:.9f} uV\n")
    summary_file.write(f"stored first-section y[n]: {section_output_v[equation_index] * 1e6:.9f} uV\n\n")
    summary_file.write("Concrete measured values after full forward-backward filter:\n")
    summary_file.write("time_s, absolute_sample, raw_uV, manual_filtfilt_uV, scipy_sosfiltfilt_uV\n")
    for row in sample_rows:
        summary_file.write(f"{row[0]: .3f}, {row[1]}, {row[2]: .6f}, {row[3]: .6f}, {row[4]: .6f}\n")

print(f"Saved: {FIGURE_PATH}")
print(f"Saved: {DATAVIZ_FIGURE_PATH}")
print(f"Saved: {SUMMARY_PATH}")
print(f"Manual-vs-Scipy max abs difference: {max_abs_difference_uv:.6f} uV")
