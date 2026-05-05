"""DRIL one artremoved EXP08 epoch through one causal 13 Hz Butterworth bandpass."""

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
from scipy.signal import butter, dimpulse, sos2tf, sosfilt


# ============================================================
# CONFIG
# ============================================================

epoch_path = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08\exp08_epochs_100pct_on_artremoved-epo.fif")
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
output_directory.mkdir(parents=True, exist_ok=True)

channel_name = "Oz"  # same posterior channel used in the recent QC plot
filter_band_hz = (11.0, 14.0)  # 13 Hz phase-view band from the recent QC path
filter_order = 2
artifact_check_window_s = (-0.1, 0.8)
display_window_s = (-0.5, 2.0)
equation_time_s = 0.001

figure_path = output_directory / "exp08_epoch_13hz_bandpass_step_dril_oz_100pct.png"
summary_path = output_directory / "exp08_epoch_13hz_bandpass_step_dril_oz_100pct.txt"


# ============================================================
# 1) LOAD ONE ARTREMOVED EPOCH
# ============================================================

epochs = mne.read_epochs(epoch_path, preload=True, verbose=False)
times_s = np.asarray(epochs.times, dtype=float)
sampling_rate_hz = float(epochs.info["sfreq"])
if channel_name not in epochs.ch_names:
    raise RuntimeError(f"Missing requested channel: {channel_name}")

# Epochs -> Oz matrix in Volts. Demeaning matches the recent QC view.
epoch_matrix = epochs.get_data(picks=[channel_name])[:, 0, :]
epoch_matrix = epoch_matrix - epoch_matrix.mean(axis=1, keepdims=True)

artifact_mask = (times_s >= artifact_check_window_s[0]) & (times_s <= artifact_check_window_s[1])
display_mask = (times_s >= display_window_s[0]) & (times_s <= display_window_s[1])
if not np.any(artifact_mask) or not np.any(display_mask):
    raise RuntimeError("Configured time windows do not overlap the epoch axis.")

# Pick the same kind of worst epoch: largest residual before any filtering.
worst_epoch = int(np.argmax(np.max(np.abs(epoch_matrix[:, artifact_mask]), axis=1)))
input_v = np.asarray(epoch_matrix[worst_epoch], dtype=float)


# ============================================================
# 2) EXECUTE ONE CAUSAL FILTER STEP BY STEP
# ============================================================

sos = butter(filter_order, filter_band_hz, btype="bandpass", fs=sampling_rate_hz, output="sos")
filtered_v = sosfilt(sos, input_v)

# Run each SOS section separately so the figure can show where the artifact grows.
section_outputs = []
section_input = input_v.copy()
for section_index, section in enumerate(sos):
    section_output = sosfilt(section[np.newaxis, :], section_input)
    section_outputs.append(section_output)
    section_input = section_output

manual_filtered_v = section_outputs[-1]
max_difference_uv = float(np.max(np.abs((manual_filtered_v - filtered_v) * 1e6)))


# ============================================================
# 3) EXECUTE ONE FILTER EQUATION SAMPLE
# ============================================================

first_section = sos[0]
b0, b1, b2, a0, a1, a2 = [float(value) for value in first_section]
if not np.isclose(a0, 1.0):
    raise RuntimeError("Expected normalized SOS coefficients with a0=1.")

# Direct-form I view of the first section. This is for the DRIL equation, not
# for replacing scipy.signal.sosfilt in the analysis path.
equation_output_v = np.zeros_like(input_v)
for sample_index in range(input_v.size):
    x0 = input_v[sample_index]
    x1 = input_v[sample_index - 1] if sample_index >= 1 else 0.0
    x2 = input_v[sample_index - 2] if sample_index >= 2 else 0.0
    y1 = equation_output_v[sample_index - 1] if sample_index >= 1 else 0.0
    y2 = equation_output_v[sample_index - 2] if sample_index >= 2 else 0.0
    equation_output_v[sample_index] = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

equation_index = int(np.argmin(np.abs(times_s - equation_time_s)))
equation_terms_uv = {
    "b0*x[n]": b0 * input_v[equation_index] * 1e6,
    "b1*x[n-1]": b1 * input_v[equation_index - 1] * 1e6,
    "b2*x[n-2]": b2 * input_v[equation_index - 2] * 1e6,
    "-a1*y[n-1]": -a1 * equation_output_v[equation_index - 1] * 1e6,
    "-a2*y[n-2]": -a2 * equation_output_v[equation_index - 2] * 1e6,
}
equation_sum_uv = float(sum(equation_terms_uv.values()))


# ============================================================
# 4) FILTER MEMORY AND SUMMARY METRICS
# ============================================================

b, a = sos2tf(sos)
impulse_times_s = np.arange(0.0, 1.2, 1.0 / sampling_rate_hz)
_, impulse_response = dimpulse((b, a, 1.0 / sampling_rate_hz), n=impulse_times_s.size)
impulse_response = np.squeeze(impulse_response)
impulse_response = impulse_response / np.max(np.abs(impulse_response))

pre_mask = (times_s >= -0.25) & (times_s <= -0.02)
post_mask = (times_s >= 0.02) & (times_s <= 0.50)
input_uv = input_v * 1e6
filtered_uv = filtered_v * 1e6
pre_rms_uv = float(np.sqrt(np.mean(filtered_uv[pre_mask] ** 2)))
post_rms_uv = float(np.sqrt(np.mean(filtered_uv[post_mask] ** 2)))
peak_input_uv = float(np.max(np.abs(input_uv[artifact_mask])))
peak_output_uv = float(np.max(np.abs(filtered_uv[artifact_mask])))


# ============================================================
# 5) SAVE CLAIM-FIRST DRIL FIGURE
# ============================================================

fig, axes = plt.subplots(3, 2, figsize=(12.8, 10.2), constrained_layout=False)
context_limit_uv = float(
    np.nanmax(
        np.abs(
            np.concatenate(
                [
                    input_uv[display_mask],
                    section_outputs[0][display_mask] * 1e6,
                    section_outputs[-1][display_mask] * 1e6,
                    filtered_uv[display_mask],
                ]
            )
        )
    )
)
filter_limit_uv = float(
    np.nanpercentile(
        np.abs(
            np.concatenate(
                [
                    section_outputs[0][display_mask] * 1e6,
                    section_outputs[-1][display_mask] * 1e6,
                    filtered_uv[display_mask],
                ]
            )
        ),
        99.5,
    )
)
context_ylim = (-1.08 * context_limit_uv, 1.08 * context_limit_uv)
filter_ylim = (-1.25 * filter_limit_uv, 1.25 * filter_limit_uv)

fig.suptitle(
    "One causal 13 Hz Butterworth bandpass can turn residual pulse energy into ringing",
    fontsize=15,
    fontweight="bold",
)


def style_time_axis(axis, ylabel, ylim):
    axis.axvline(0.0, color="#222222", lw=0.9, ls="--")
    axis.axvspan(-0.02, 0.04, color="#f2c94c", alpha=0.18, lw=0)
    axis.set_ylabel(ylabel)
    axis.set_ylim(ylim)
    axis.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


ax = axes[0, 0]
ax.plot(times_s[display_mask], input_uv[display_mask], color="#4d4d4d", lw=1.05)
style_time_axis(ax, "Input Oz\nuV", filter_ylim)
ax.set_title("1. Input zoom: residual structure around the pulse is visible", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")

ax = axes[0, 1]
ax.plot(impulse_times_s, impulse_response, color="#1f77b4", lw=1.25)
ax.axhline(0.0, color="#222222", lw=0.8)
ax.set_title("2. Filter memory: the 13 Hz bandpass rings after an impulse", loc="left", fontsize=10.2)
ax.set_ylabel("Normalized impulse response")
ax.set_xlabel("Time after impulse (s)")
ax.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax = axes[1, 0]
first_section_uv = section_outputs[0] * 1e6
ax.plot(times_s[display_mask], first_section_uv[display_mask], color="#1f77b4", lw=1.1)
style_time_axis(ax, "After SOS 1\nuV", filter_ylim)
ax.set_title("3. Section 1: previous-output terms start the 13 Hz resonance", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")

ax = axes[1, 1]
second_section_uv = section_outputs[-1] * 1e6
ax.plot(times_s[display_mask], second_section_uv[display_mask], color="#d62728", lw=1.25)
style_time_axis(ax, "After final SOS\nuV", filter_ylim)
ax.set_title("4. Final section: the pulse now looks like a 13 Hz oscillation", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")

ax = axes[2, 0]
bar_labels = ["recent raw\nx terms", "previous output\nmemory terms", "current output\ny[n]"]
input_terms_uv = equation_terms_uv["b0*x[n]"] + equation_terms_uv["b1*x[n-1]"] + equation_terms_uv["b2*x[n-2]"]
memory_terms_uv = equation_terms_uv["-a1*y[n-1]"] + equation_terms_uv["-a2*y[n-2]"]
bar_values = [input_terms_uv, memory_terms_uv, equation_sum_uv]
bars = ax.bar(bar_labels, bar_values, color=["#8c8c8c", "#1f77b4", "#d62728"], width=0.62)
ax.axhline(0.0, color="#222222", lw=0.8)
ax.set_title("5. One executed equation: output memory is explicit", loc="left", fontsize=10.2)
ax.set_ylabel(f"First SOS at t={times_s[equation_index]:.3f}s (uV)")
ax.grid(True, axis="y", color="#dddddd", lw=0.45, alpha=0.6)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for bar, value in zip(bars, bar_values):
    ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.4f}", ha="center", va="bottom", fontsize=8.5)

ax = axes[2, 1]
ax.plot(times_s[display_mask], input_uv[display_mask], color="#9a9a9a", lw=0.95, label="input")
ax.plot(times_s[display_mask], filtered_uv[display_mask], color="#d62728", lw=1.25, label="filtered")
style_time_axis(ax, "uV", filter_ylim)
ax.set_title("6. Overlay: the interpreted trace is a filtered object", loc="left", fontsize=10.2)
ax.set_xlabel("Time relative to pulse (s)")
ax.legend(frameon=False, loc="lower right")

figure_note = (
    f"Measured DRIL figure. Source: {epoch_path.name}, channel {channel_name}, worst residual epoch {worst_epoch}, "
    f"sampling rate {sampling_rate_hz:.1f} Hz. One filter only: causal Butterworth bandpass "
    f"{filter_band_hz[0]:.1f}-{filter_band_hz[1]:.1f} Hz, order {filter_order}, scipy.signal.sosfilt. "
    "Filter-step panels use a zoomed shared y-limit."
)
fig.text(0.01, 0.022, textwrap.fill(figure_note, width=170), fontsize=8.2, color="#4d4d4d")
fig.tight_layout(rect=(0, 0.07, 1, 0.94))
fig.savefig(figure_path, dpi=220)
plt.close(fig)


# ============================================================
# 6) SAVE NUMERIC DRIL SUMMARY
# ============================================================

with open(summary_path, "w", encoding="utf-8") as summary_file:
    summary_file.write("EXP08 EPOCH 13 HZ BANDPASS STEP DRIL\n")
    summary_file.write("=" * 80 + "\n\n")
    summary_file.write(f"Input epochs: {epoch_path}\n")
    summary_file.write("Representation: saved artremoved MNE epochs; Oz channel; per-epoch demeaned\n")
    summary_file.write(f"Channel: {channel_name}\n")
    summary_file.write(f"Sampling rate: {sampling_rate_hz:.1f} Hz\n")
    summary_file.write(f"Worst epoch index: {worst_epoch}\n")
    summary_file.write(f"Filter: causal Butterworth bandpass {filter_band_hz[0]:.1f}-{filter_band_hz[1]:.1f} Hz, order {filter_order}\n")
    summary_file.write(f"SOS sections: {sos.shape[0]}\n")
    summary_file.write(f"Manual section-vs-sosfilt max abs difference: {max_difference_uv:.9f} uV\n\n")
    summary_file.write("Executed first-section equation:\n")
    summary_file.write("y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]\n")
    summary_file.write(f"sample_index={equation_index}, time={times_s[equation_index]:.6f}s\n")
    for term_name, term_value in equation_terms_uv.items():
        summary_file.write(f"{term_name}: {term_value:.9f} uV\n")
    summary_file.write(f"sum -> y[n]: {equation_sum_uv:.9f} uV\n\n")
    summary_file.write("Filtered-artifact metrics:\n")
    summary_file.write(f"input_peak_abs_uV in {artifact_check_window_s}: {peak_input_uv:.6f}\n")
    summary_file.write(f"filtered_peak_abs_uV in {artifact_check_window_s}: {peak_output_uv:.6f}\n")
    summary_file.write(f"filtered_pre_rms_uV (-0.25 to -0.02 s): {pre_rms_uv:.6f}\n")
    summary_file.write(f"filtered_post_rms_uV (0.02 to 0.50 s): {post_rms_uv:.6f}\n")
    summary_file.write(f"context_ylim_uV_not_plotted: {context_ylim[0]:.6f}, {context_ylim[1]:.6f}\n")
    summary_file.write(f"shared_zoom_ylim_uV: {filter_ylim[0]:.6f}, {filter_ylim[1]:.6f}\n")
    summary_file.write(f"\nFigure: {figure_path}\n")

print(f"Saved figure: {figure_path}")
print(f"Saved summary: {summary_path}")
print(f"Worst epoch: {worst_epoch}")
print(f"Peak input/output in artifact window: {peak_input_uv:.3f} / {peak_output_uv:.3f} uV")
