"""DRIL how a causal 13 Hz Butterworth filter transforms samples left to right."""

import os
from pathlib import Path
import textwrap
import warnings

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import matplotlib
#matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import butter, find_peaks, sosfilt


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
target_pulse_index = 10

baseline_ms = (-100, -10)
artifact_start_ms = -25
min_end_ms = 20
max_end_ms = 200
threshold_sd = 5.0
peak_fraction = 0.02

filter_band_hz = (11.0, 14.0)
filter_order = 2
step_times_s = [-0.300, -0.220, -0.140, -0.060, -0.020, 0.000, 0.040, 0.160]
display_window_s = (-0.32, 0.75)
zoom_ylim_uv = (-500.0, 500.0)

figure_path = output_directory / "exp08_causal_filter_sample_step_dril_oz_100pct_pulse11.png"
summary_path = output_directory / "exp08_causal_filter_sample_step_dril_oz_100pct_pulse11.txt"


# ============================================================
# 1) LOAD RAW AND BUILD ONE HUGE-ARTIFACT INPUT
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


def detect_artifact_end(signal: np.ndarray, pulse: int) -> tuple[int, np.ndarray]:
    baseline_idx = np.arange(pulse + ms_to_samples(baseline_ms[0]), pulse + ms_to_samples(baseline_ms[1]))
    slope, intercept = np.polyfit((baseline_idx - pulse) / sampling_rate_hz, signal[baseline_idx], 1)
    drift_v = slope * ((np.arange(signal.size) - pulse) / sampling_rate_hz) + intercept
    noise_std = float(np.std(signal[baseline_idx] - drift_v[baseline_idx]))
    artifact_amp = np.abs(signal - drift_v)
    peak_amp = float(np.max(artifact_amp[pulse : pulse + ms_to_samples(20)]))
    recovery_threshold_v = max(threshold_sd * noise_std, peak_fraction * peak_amp)
    search_start = pulse + ms_to_samples(min_end_ms)
    search_stop = pulse + ms_to_samples(max_end_ms)
    peaks, _ = find_peaks(artifact_amp[search_start:search_stop], height=recovery_threshold_v)
    recovery_sample = search_start + peaks[-1] if len(peaks) else search_start
    return int(recovery_sample), drift_v


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


recovery_sample, drift_v = detect_artifact_end(raw_signal_v, pulse_sample)
clean_signal_v = interpolate_artifact(raw_signal_v, pulse_sample, recovery_sample, drift_v)

# Huge-artifact input: measured background plus the measured artifact residual.
artifact_residual_v = raw_signal_v - clean_signal_v
huge_signal_v = clean_signal_v + artifact_residual_v

display_start = pulse_sample + int(round(display_window_s[0] * sampling_rate_hz))
display_stop = pulse_sample + int(round(display_window_s[1] * sampling_rate_hz))
if display_start < 0 or display_stop > raw_signal_v.size:
    raise RuntimeError("Requested display window exceeds raw recording bounds.")

input_v = huge_signal_v[display_start:display_stop].copy()
time_s = (np.arange(input_v.size) + display_start - pulse_sample) / sampling_rate_hz


# ============================================================
# 2) CONSTRUCT THE FILTER AND EXECUTE IT SAMPLE BY SAMPLE
# ============================================================

sos = butter(filter_order, filter_band_hz, btype="bandpass", fs=sampling_rate_hz, output="sos")
reference_output_v = sosfilt(sos, input_v)

# Manual cascade with one direct-form II transposed state per SOS section.
section_states = np.zeros((sos.shape[0], 2), dtype=float)
manual_output_v = np.zeros_like(input_v)
snapshots: dict[int, dict[str, np.ndarray | float]] = {}
step_indices = [int(np.argmin(np.abs(time_s - step_time_s))) for step_time_s in step_times_s]

for sample_index, x_n in enumerate(input_v):
    section_input = float(x_n)
    section_terms = []

    for section_index, section in enumerate(sos):
        b0, b1, b2, a0, a1, a2 = [float(value) for value in section]
        state_0, state_1 = section_states[section_index]

        # SciPy SOS uses direct-form II transposed:
        # y[n] = b0*x[n] + state_0
        # state_0_next = b1*x[n] - a1*y[n] + state_1
        # state_1_next = b2*x[n] - a2*y[n]
        y_n = b0 * section_input + state_0
        next_state_0 = b1 * section_input - a1 * y_n + state_1
        next_state_1 = b2 * section_input - a2 * y_n
        section_states[section_index] = [next_state_0, next_state_1]

        section_terms.append(
            {
                "section": section_index + 1,
                "input_v": section_input,
                "state_0_v": state_0,
                "state_1_v": state_1,
                "output_v": y_n,
                "next_state_0_v": next_state_0,
                "next_state_1_v": next_state_1,
            }
        )
        section_input = y_n

    manual_output_v[sample_index] = section_input
    if sample_index in step_indices:
        snapshots[sample_index] = {
            "output_so_far_v": manual_output_v.copy(),
            "terms": section_terms,
            "states_v": section_states.copy(),
        }

max_difference_uv = float(np.max(np.abs((manual_output_v - reference_output_v) * 1e6)))
if max_difference_uv > 1e-6:
    raise RuntimeError(f"Manual filter differs from scipy sosfilt by {max_difference_uv:.6f} uV.")


# ============================================================
# 3) SAVE LEFT-TO-RIGHT STEP FIGURE
# ============================================================

fig, axes = plt.subplots(4, 2, figsize=(13.0, 12.0), constrained_layout=False, sharex=True, sharey=True)
fig.suptitle(
    "DRIL: a causal Butterworth filter only transforms samples to the left of the current sample",
    fontsize=15,
    fontweight="bold",
)

input_uv = input_v * 1e6
manual_output_uv = manual_output_v * 1e6


def style_axis(axis, title: str, current_time_s: float):
    axis.axvline(0.0, color="#222222", lw=0.9, ls="--")
    axis.axvline(current_time_s, color="#d62728", lw=1.0)
    axis.axvspan(artifact_start_ms / 1000.0, (recovery_sample - pulse_sample) / sampling_rate_hz, color="#f2c94c", alpha=0.15, lw=0)
    axis.set_ylim(zoom_ylim_uv)
    axis.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.set_title(title, loc="left", fontsize=10.0)


for axis, step_index in zip(axes.flat, step_indices):
    current_time_s = float(time_s[step_index])
    output_so_far_uv = np.asarray(snapshots[step_index]["output_so_far_v"], dtype=float) * 1e6
    processed_mask = np.arange(input_v.size) <= step_index
    future_mask = np.arange(input_v.size) > step_index

    axis.plot(time_s[future_mask], input_uv[future_mask], color="#b3b3b3", lw=0.75, label="future input")
    axis.plot(time_s[processed_mask], input_uv[processed_mask], color="#8c8c8c", lw=0.65, alpha=0.75, label="input already read")
    axis.plot(time_s[processed_mask], output_so_far_uv[processed_mask], color="#d62728", lw=1.2, label="filtered output so far")
    style_axis(axis, f"n={step_index}: transformed left side, future still raw", current_time_s)

axes[-1, 0].set_xlabel("Time relative to pulse (s)")
axes[-1, 1].set_xlabel("Time relative to pulse (s)")
for axis in axes[:, 0]:
    axis.set_ylabel("uV")
axes[0, 0].legend(frameon=False, loc="lower right", fontsize=8)

figure_note = (
    f"Source: raw VHDR {stim_path.name}, {channel_name}, {target_intensity_pct}% pulse {target_pulse_index + 1}. "
    f"Filter: causal Butterworth bandpass {filter_band_hz[0]:.1f}-{filter_band_hz[1]:.1f} Hz, order {filter_order}. "
    "The first panels start before the pulse, where the filter behaves normally on background signal. "
    "Each panel freezes processing at one sample n: red is y[0:n], gray right side is x[n+1:end] not processed yet. "
    "Y-limits are fixed at -10 to +10 uV to focus on non-artifact scale."
)
fig.text(0.01, 0.022, textwrap.fill(figure_note, width=170), fontsize=8.2, color="#4d4d4d")
fig.tight_layout(rect=(0, 0.06, 1, 0.94))
fig.savefig(figure_path, dpi=220)
plt.show()
plt.close(fig)


# ============================================================
# 4) SAVE NUMERIC STEP SUMMARY
# ============================================================

with open(summary_path, "w", encoding="utf-8") as summary_file:
    summary_file.write("EXP08 CAUSAL FILTER SAMPLE STEP DRIL\n")
    summary_file.write("=" * 80 + "\n\n")
    summary_file.write(f"Input raw file: {stim_path}\n")
    summary_file.write(f"Channel: {channel_name}\n")
    summary_file.write(f"Sampling rate: {sampling_rate_hz:.1f} Hz\n")
    summary_file.write(f"Pulse: {target_intensity_pct}% pulse {target_pulse_index + 1}, sample {pulse_sample}\n")
    summary_file.write(f"Filter: causal Butterworth bandpass {filter_band_hz[0]:.1f}-{filter_band_hz[1]:.1f} Hz, order {filter_order}\n")
    summary_file.write(f"Manual-vs-scipy max abs difference: {max_difference_uv:.12f} uV\n\n")
    summary_file.write("Filter update rule per SOS section, direct-form II transposed:\n")
    summary_file.write("y[n] = b0*x[n] + z0\n")
    summary_file.write("z0_next = b1*x[n] - a1*y[n] + z1\n")
    summary_file.write("z1_next = b2*x[n] - a2*y[n]\n\n")
    summary_file.write("Selected processing checkpoints:\n")
    for step_index in step_indices:
        terms = snapshots[step_index]["terms"]
        summary_file.write(f"\nstep_index={step_index}, time={time_s[step_index]:.6f}s\n")
        for term in terms:
            summary_file.write(
                "  section {section}: input={input_v:.9e} V, z0={state_0_v:.9e} V, "
                "z1={state_1_v:.9e} V, output={output_v:.9e} V\n".format(**term)
            )
    summary_file.write(f"\nFigure: {figure_path}\n")

print(f"Saved figure: {figure_path}")
print(f"Saved summary: {summary_path}")
print(f"Manual-vs-scipy max abs difference: {max_difference_uv:.12f} uV")
