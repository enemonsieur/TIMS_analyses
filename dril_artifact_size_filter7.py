"""DRIL how artifact size alone drives one causal 13 Hz Butterworth filter."""

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
from scipy.signal import butter, dimpulse, find_peaks, sos2tf, sosfilt


# ============================================================
# CONFIG
# ============================================================

data_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
stim_path = data_directory / "exp08-STIM-pulse_run01_10-100.vhdr"
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
output_directory.mkdir(parents=True, exist_ok=True)

channel_name = "Oz"
first_pulse_sample = 20530
inter_pulse_interval_s = 5.0
pulses_per_intensity = 20
target_intensity_pct = 100
target_pulse_index = 10  # pulse 11

baseline_ms = (-100, -10)
artifact_start_ms = -25
min_end_ms = 20
max_end_ms = 200
threshold_sd = 5.0
peak_fraction = 0.02

filter_band_hz = (11.0, 14.0)
filter_order = 2
display_window_s = (-0.5, 2.0)
equation_time_s = 0.001
artifact_scales = {
    "no artifact": 0.0,
    "mid artifact": 0.25,
    "huge artifact": 1.0,
}

figure_path = output_directory / "exp08_artifact_size_13hz_filter_dril_oz_100pct_pulse11.png"
summary_path = output_directory / "exp08_artifact_size_13hz_filter_dril_oz_100pct_pulse11.txt"


# ============================================================
# 1) LOAD RAW AND BUILD ARTIFACT-SIZE VERSIONS
# ============================================================

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    raw = mne.io.read_raw_brainvision(str(stim_path), preload=True, verbose=False)

sampling_rate_hz = float(raw.info["sfreq"])
if channel_name not in raw.ch_names:
    raise RuntimeError(f"Missing requested channel: {channel_name}")

raw_signal_v = raw.get_data(picks=[channel_name])[0]
ipi_samples = int(round(inter_pulse_interval_s * sampling_rate_hz))
intensity_index = target_intensity_pct // 10 - 1
pulse_sample = int(first_pulse_sample + (intensity_index * pulses_per_intensity + target_pulse_index) * ipi_samples)


def ms_to_samples(milliseconds: float) -> int:
    return int(round(milliseconds / 1000.0 * sampling_rate_hz))


def detect_artifact_end(signal: np.ndarray, pulse: int) -> tuple[int, float, np.ndarray, float, float]:
    baseline_idx = np.arange(pulse + ms_to_samples(baseline_ms[0]), pulse + ms_to_samples(baseline_ms[1]))
    slope, intercept = np.polyfit((baseline_idx - pulse) / sampling_rate_hz, signal[baseline_idx], 1)
    drift_v = slope * ((np.arange(signal.size) - pulse) / sampling_rate_hz) + intercept
    noise_std = float(np.std(signal[baseline_idx] - drift_v[baseline_idx]))
    artifact_amp = np.abs(signal - drift_v)
    peak_amp = float(np.max(artifact_amp[pulse : pulse + ms_to_samples(20)]))
    recovery_threshold_v = max(threshold_sd * noise_std, peak_fraction * peak_amp)
    search_start = pulse + ms_to_samples(min_end_ms)
    search_stop = pulse + ms_to_samples(max_end_ms)
    above_threshold_peaks, _ = find_peaks(artifact_amp[search_start:search_stop], height=recovery_threshold_v)
    recovery_sample = search_start + above_threshold_peaks[-1] if len(above_threshold_peaks) else search_start
    return int(recovery_sample), float(recovery_threshold_v), drift_v, noise_std, peak_amp


def interpolate_artifact(signal: np.ndarray, pulse: int, recovery_sample: int, drift_v: np.ndarray) -> np.ndarray:
    interp_start = pulse + ms_to_samples(artifact_start_ms)
    artifact_region = np.arange(interp_start, recovery_sample)
    cleaned = signal.copy()
    cleaned[artifact_region] = np.linspace(
        drift_v[interp_start],
        drift_v[recovery_sample],
        artifact_region.size,
        endpoint=False,
    )
    return cleaned


recovery_sample, recovery_threshold_v, drift_v, noise_std_v, peak_amp_v = detect_artifact_end(raw_signal_v, pulse_sample)
clean_signal_v = interpolate_artifact(raw_signal_v, pulse_sample, recovery_sample, drift_v)
artifact_residual_v = raw_signal_v - clean_signal_v

display_start = pulse_sample + int(round(display_window_s[0] * sampling_rate_hz))
display_stop = pulse_sample + int(round(display_window_s[1] * sampling_rate_hz))
if display_start < 0 or display_stop > raw_signal_v.size:
    raise RuntimeError("Requested display window exceeds raw recording bounds.")

time_s = (np.arange(display_stop - display_start) + display_start - pulse_sample) / sampling_rate_hz
base_v = clean_signal_v[display_start:display_stop]
artifact_v = artifact_residual_v[display_start:display_stop]
input_versions_v = {
    label: base_v + scale * artifact_v
    for label, scale in artifact_scales.items()
}


# ============================================================
# 2) CONSTRUCT AND APPLY ONE FILTER
# ============================================================

sos = butter(filter_order, filter_band_hz, btype="bandpass", fs=sampling_rate_hz, output="sos")
filtered_versions_v = {label: sosfilt(sos, signal_v) for label, signal_v in input_versions_v.items()}

section_versions_v: dict[str, list[np.ndarray]] = {}
for label, signal_v in input_versions_v.items():
    section_input_v = signal_v.copy()
    section_versions_v[label] = []
    for section in sos:
        section_output_v = sosfilt(section[np.newaxis, :], section_input_v)
        section_versions_v[label].append(section_output_v)
        section_input_v = section_output_v

first_section = sos[0]
b0, b1, b2, a0, a1, a2 = [float(value) for value in first_section]
if not np.isclose(a0, 1.0):
    raise RuntimeError("Expected normalized SOS coefficients with a0=1.")

# Execute the first SOS equation for the huge-artifact input.
huge_input_v = input_versions_v["huge artifact"]
equation_output_v = np.zeros_like(huge_input_v)
for sample_index in range(huge_input_v.size):
    x0 = huge_input_v[sample_index]
    x1 = huge_input_v[sample_index - 1] if sample_index >= 1 else 0.0
    x2 = huge_input_v[sample_index - 2] if sample_index >= 2 else 0.0
    y1 = equation_output_v[sample_index - 1] if sample_index >= 1 else 0.0
    y2 = equation_output_v[sample_index - 2] if sample_index >= 2 else 0.0
    equation_output_v[sample_index] = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

equation_index = int(np.argmin(np.abs(time_s - equation_time_s)))
equation_terms_uv = {
    "b0*x[n]": b0 * huge_input_v[equation_index] * 1e6,
    "b1*x[n-1]": b1 * huge_input_v[equation_index - 1] * 1e6,
    "b2*x[n-2]": b2 * huge_input_v[equation_index - 2] * 1e6,
    "-a1*y[n-1]": -a1 * equation_output_v[equation_index - 1] * 1e6,
    "-a2*y[n-2]": -a2 * equation_output_v[equation_index - 2] * 1e6,
}
equation_sum_uv = float(sum(equation_terms_uv.values()))


# ============================================================
# 3) FILTER MEMORY AND SCALE METRICS
# ============================================================

b, a = sos2tf(sos)
impulse_times_s = np.arange(0.0, 1.2, 1.0 / sampling_rate_hz)
_, impulse_response = dimpulse((b, a, 1.0 / sampling_rate_hz), n=impulse_times_s.size)
impulse_response = np.squeeze(impulse_response)
impulse_response = impulse_response / np.max(np.abs(impulse_response))

input_versions_uv = {label: signal_v * 1e6 for label, signal_v in input_versions_v.items()}
filtered_versions_uv = {label: signal_v * 1e6 for label, signal_v in filtered_versions_v.items()}
section_versions_uv = {
    label: [section_output_v * 1e6 for section_output_v in section_outputs]
    for label, section_outputs in section_versions_v.items()
}

zoom_ylim = (-10.0, 10.0)

artifact_window_mask = (time_s >= artifact_start_ms / 1000.0) & (time_s <= (recovery_sample - pulse_sample) / sampling_rate_hz)
post_mask = (time_s >= 0.02) & (time_s <= 0.50)
summary_rows = []
for label in artifact_scales:
    input_peak_uv = float(np.max(np.abs(input_versions_uv[label][artifact_window_mask])))
    output_peak_uv = float(np.max(np.abs(filtered_versions_uv[label][post_mask])))
    output_rms_uv = float(np.sqrt(np.mean(filtered_versions_uv[label][post_mask] ** 2)))
    summary_rows.append((label, artifact_scales[label], input_peak_uv, output_peak_uv, output_rms_uv))


# ============================================================
# 4) SAVE CLAIM-FIRST DRIL FIGURE
# ============================================================

fig, axes = plt.subplots(4, 2, figsize=(13.0, 13.0), constrained_layout=False)
fig.suptitle(
    "DRIL: each Butterworth section carries artifact energy into the 13 Hz output",
    fontsize=15,
    fontweight="bold",
)


def style_time_axis(axis, ylabel):
    axis.axvline(0.0, color="#222222", lw=0.9, ls="--")
    axis.axvspan(artifact_start_ms / 1000.0, (recovery_sample - pulse_sample) / sampling_rate_hz, color="#f2c94c", alpha=0.18, lw=0)
    axis.set_ylabel(ylabel)
    axis.set_ylim(zoom_ylim)
    axis.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


colors = {"no artifact": "#4d4d4d", "mid artifact": "#1f77b4", "huge artifact": "#d62728"}
huge_label = "huge artifact"

ax = axes[0, 0]
ax.plot(time_s, input_versions_uv[huge_label], lw=0.9, color=colors[huge_label], label="huge artifact input")
style_time_axis(ax, "Input Oz\nuV")
ax.set_title("1. Before filtering: huge artifact is clipped so the small signal is visible", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")
ax.legend(frameon=False, loc="lower right")

ax = axes[0, 1]
ax.plot(impulse_times_s, impulse_response, color="#1f77b4", lw=1.25)
ax.axhline(0.0, color="#222222", lw=0.8)
ax.set_title("2. Route: the 13 Hz Butterworth is a ringing system", loc="left", fontsize=10.2)
ax.set_ylabel("Normalized impulse response")
ax.set_xlabel("Time after impulse (s)")
ax.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax = axes[1, 0]
ax.plot(time_s, input_versions_uv[huge_label], lw=0.8, color="#9a9a9a", label="before section 1")
ax.plot(time_s, section_versions_uv[huge_label][0], lw=1.1, color="#1f77b4", label="after section 1")
style_time_axis(ax, "uV")
ax.set_title("3. SOS section 1: convolution starts the 13 Hz ringing", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")
ax.legend(frameon=False, loc="lower right")

ax = axes[1, 1]
ax.plot(time_s, section_versions_uv[huge_label][0], lw=0.85, color="#1f77b4", label="before section 2")
ax.plot(time_s, section_versions_uv[huge_label][1], lw=1.1, color="#d62728", label="after section 2")
style_time_axis(ax, "uV")
ax.set_title("4. SOS section 2: the section-1 output is filtered again", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")
ax.legend(frameon=False, loc="upper left")

ax = axes[2, 0]
for label in artifact_scales:
    ax.plot(time_s, filtered_versions_uv[label], lw=1.05, color=colors[label], label=label)
style_time_axis(ax, "Filtered output\nuV")
ax.set_title("5. Artifact-size check: same filter, larger artifact gives larger ringing", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")
ax.legend(frameon=False, loc="lower right")

ax = axes[2, 1]
labels = [row[0] for row in summary_rows]
output_peaks = [row[3] for row in summary_rows]
x_positions = np.arange(len(labels))
ax.bar(x_positions, output_peaks, width=0.55, color=[colors[label] for label in labels])
ax.set_xticks(x_positions, labels)
ax.set_title("6. Numeric scale check: post-filter peak follows artifact size", loc="left", fontsize=10.2)
ax.set_ylabel("Filtered post-pulse peak (uV)")
ax.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax = axes[3, 0]
input_terms_uv = equation_terms_uv["b0*x[n]"] + equation_terms_uv["b1*x[n-1]"] + equation_terms_uv["b2*x[n-2]"]
memory_terms_uv = equation_terms_uv["-a1*y[n-1]"] + equation_terms_uv["-a2*y[n-2]"]
bar_labels = ["recent raw\nx terms", "previous output\nmemory terms", "current output\ny[n]"]
bar_values = [input_terms_uv, memory_terms_uv, equation_sum_uv]
bars = ax.bar(bar_labels, bar_values, color=["#8c8c8c", "#1f77b4", "#d62728"], width=0.62)
ax.axhline(0.0, color="#222222", lw=0.8)
ax.set_title("7. Execute one sample: previous output is part of the next output", loc="left", fontsize=10.2)
ax.set_ylabel(f"First SOS at t={time_s[equation_index]:.3f}s (uV)")
ax.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for bar, value in zip(bars, bar_values):
    ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.4f}", ha="center", va="bottom", fontsize=8.5)

ax = axes[3, 1]
ax.plot(time_s, input_versions_uv[huge_label], lw=0.75, color="#9a9a9a", label="input to filter")
ax.plot(time_s, filtered_versions_uv[huge_label], lw=1.15, color="#d62728", label="final output")
style_time_axis(ax, "uV")
ax.set_title("8. Before/after: the final trace is filter-created ringing", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")
ax.legend(frameon=False, loc="lower right")

figure_note = (
    f"Measured/synthetic DRIL. Background and artifact shape come from raw VHDR {stim_path.name}, "
    f"{channel_name}, {target_intensity_pct}% pulse {target_pulse_index + 1}. "
    "No/mid/huge versions are clean interpolated signal plus 0%, 25%, or 100% of the measured artifact residual. "
    f"One filter only: causal Butterworth bandpass {filter_band_hz[0]:.1f}-{filter_band_hz[1]:.1f} Hz, order {filter_order}."
    " Time-course y-limits are fixed at -10 to +10 uV to focus on non-artifact data."
)
fig.text(0.01, 0.022, textwrap.fill(figure_note, width=170), fontsize=8.2, color="#4d4d4d")
fig.tight_layout(rect=(0, 0.07, 1, 0.94))
fig.savefig(figure_path, dpi=220)
plt.close(fig)


# ============================================================
# 5) SAVE NUMERIC DRIL SUMMARY
# ============================================================

with open(summary_path, "w", encoding="utf-8") as summary_file:
    summary_file.write("EXP08 ARTIFACT SIZE 13 HZ FILTER DRIL\n")
    summary_file.write("=" * 80 + "\n\n")
    summary_file.write(f"Input raw file: {stim_path}\n")
    summary_file.write(f"Channel: {channel_name}\n")
    summary_file.write(f"Sampling rate: {sampling_rate_hz:.1f} Hz\n")
    summary_file.write(f"Pulse: {target_intensity_pct}% pulse {target_pulse_index + 1}, sample {pulse_sample}\n")
    summary_file.write(f"Recovery sample: {recovery_sample}, recovery_ms={(recovery_sample - pulse_sample) / sampling_rate_hz * 1000:.3f}\n")
    summary_file.write(f"Recovery threshold: {recovery_threshold_v * 1e6:.6f} uV\n")
    summary_file.write(f"Baseline noise SD: {noise_std_v * 1e6:.6f} uV\n")
    summary_file.write(f"First-20ms artifact peak deviation: {peak_amp_v * 1e6:.6f} uV\n")
    summary_file.write(f"Filter: causal Butterworth bandpass {filter_band_hz[0]:.1f}-{filter_band_hz[1]:.1f} Hz, order {filter_order}\n\n")
    summary_file.write("y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]\n")
    summary_file.write(f"sample_index={equation_index}, time={time_s[equation_index]:.6f}s, huge-artifact input\n")
    for term_name, term_value in equation_terms_uv.items():
        summary_file.write(f"{term_name}: {term_value:.9f} uV\n")
    summary_file.write(f"sum -> y[n]: {equation_sum_uv:.9f} uV\n\n")
    summary_file.write("Artifact-size sweep:\n")
    summary_file.write("label, scale, input_artifact_peak_uV, filtered_post_peak_uV, filtered_post_rms_uV\n")
    for row in summary_rows:
        summary_file.write(f"{row[0]}, {row[1]:.3f}, {row[2]:.6f}, {row[3]:.6f}, {row[4]:.6f}\n")
    summary_file.write(f"\nFigure: {figure_path}\n")

print(f"Saved figure: {figure_path}")
print(f"Saved summary: {summary_path}")
for row in summary_rows:
    print(f"{row[0]}: input peak {row[2]:.3f} uV -> filtered post peak {row[3]:.3f} uV")
