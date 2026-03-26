"""Correct exp05 artifact timing and compare 30% vs 100% cTBS artifact size."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import hilbert

import plot_helpers
import preprocessing


# ============================================================
# FIXED INPUTS
# ============================================================
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
BASELINE_VHDR = DATA_DIR / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
STIM_100_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-GT-cTBS-run01.vhdr"
STIM_30_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP_05\artifact_characterization")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

REFERENCE_CHANNEL = "Cz"
COMPARE_CHANNELS = ["Fp1", "F3", "Cz", "C4", "Pz", "O1"]
EPOCH_PRE_S = 0.5


# ============================================================
# 1) LOAD DATA
# ============================================================
raw_base = mne.io.read_raw_brainvision(str(BASELINE_VHDR), preload=True, verbose=False)
raw_100 = mne.io.read_raw_brainvision(str(STIM_100_VHDR), preload=True, verbose=False)
raw_30 = mne.io.read_raw_brainvision(str(STIM_30_VHDR), preload=True, verbose=False)
sfreq = float(raw_100.info["sfreq"])


# ============================================================
# 2) EXTRACT STIM CHANNEL AND DETECT BLOCKS
# ============================================================
stim_marker_100 = raw_100.copy().pick(["stim"]).get_data()[0]
stim_marker_30 = raw_30.copy().pick(["stim"]).get_data()[0]

block_onsets_100, block_offsets_100 = preprocessing.detect_stim_blocks(stim_marker_100, sfreq)
block_onsets_30, block_offsets_30 = preprocessing.detect_stim_blocks(stim_marker_30, sfreq)

on_durations_100_s = (block_offsets_100 - block_onsets_100) / sfreq
on_durations_30_s = (block_offsets_30 - block_onsets_30) / sfreq
off_durations_100_s = (block_onsets_100[1:] - block_offsets_100[:-1]) / sfreq
off_durations_30_s = (block_onsets_30[1:] - block_offsets_30[:-1]) / sfreq

median_on_100_s = float(np.median(on_durations_100_s))
median_on_30_s = float(np.median(on_durations_30_s))
median_off_100_s = float(np.median(off_durations_100_s))
median_off_30_s = float(np.median(off_durations_30_s))
median_cycle_100_s = median_on_100_s + median_off_100_s
median_cycle_30_s = median_on_30_s + median_off_30_s
max_cycle_s = max(median_cycle_100_s, median_cycle_30_s)

# The protocol script gates cTBS in 1.995 s ON / 3.0 s OFF cycles.
expected_on_s = 1.995
expected_off_s = 3.0
expected_cycle_s = expected_on_s + expected_off_s

peak_stim_100 = float(np.max(np.abs(stim_marker_100)))
peak_stim_30 = float(np.max(np.abs(stim_marker_30)))
active_mask_100 = np.abs(stim_marker_100) >= 0.1 * peak_stim_100
active_mask_30 = np.abs(stim_marker_30) >= 0.1 * peak_stim_30
active_rms_100 = float(np.sqrt(np.mean(stim_marker_100[active_mask_100] ** 2)))
active_rms_30 = float(np.sqrt(np.mean(stim_marker_30[active_mask_30] ** 2)))

summary_lines = [
    "exp05 artifact characterization",
    "",
    "Protocol reference from ctbs_like_v1_amp5hz_mod50hz_triplets.py",
    f"expected_on_s={expected_on_s:.3f}",
    f"expected_off_s={expected_off_s:.3f}",
    f"expected_cycle_s={expected_cycle_s:.3f}",
    "",
    "Measured STIM timing",
    f"100_blocks={len(block_onsets_100)}",
    f"100_on_median_s={median_on_100_s:.3f}",
    f"100_on_range_s=[{on_durations_100_s.min():.3f}, {on_durations_100_s.max():.3f}]",
    f"100_off_median_s={median_off_100_s:.3f}",
    f"100_off_range_s=[{off_durations_100_s.min():.3f}, {off_durations_100_s.max():.3f}]",
    f"100_cycle_median_s={median_cycle_100_s:.3f}",
    f"30_blocks={len(block_onsets_30)}",
    f"30_on_median_s={median_on_30_s:.3f}",
    f"30_on_range_s=[{on_durations_30_s.min():.3f}, {on_durations_30_s.max():.3f}]",
    f"30_off_median_s={median_off_30_s:.3f}",
    f"30_off_range_s=[{off_durations_30_s.min():.3f}, {off_durations_30_s.max():.3f}]",
    f"30_cycle_median_s={median_cycle_30_s:.3f}",
    "",
    "Measured STIM intensity",
    f"100_peak={peak_stim_100:.6f}",
    f"30_peak={peak_stim_30:.6f}",
    f"peak_ratio_30_over_100={peak_stim_30 / (peak_stim_100 + 1e-12):.3f}",
    f"100_active_rms={active_rms_100:.6f}",
    f"30_active_rms={active_rms_30:.6f}",
    f"active_rms_ratio_30_over_100={active_rms_30 / (active_rms_100 + 1e-12):.3f}",
]

print("=== PROTOCOL REFERENCE ===")
print(f"Expected gate from protocol: ON={expected_on_s:.3f} s  OFF={expected_off_s:.3f} s  cycle={expected_cycle_s:.3f} s")
print("\n=== STIM CHANNEL BLOCK TIMING ===")
print(f"100%: {len(block_onsets_100)} blocks | ON={median_on_100_s:.3f} s  OFF={median_off_100_s:.3f} s  cycle={median_cycle_100_s:.3f} s")
print(f" 30%: {len(block_onsets_30)} blocks | ON={median_on_30_s:.3f} s  OFF={median_off_30_s:.3f} s  cycle={median_cycle_30_s:.3f} s")
print(f"ON range 100%: [{on_durations_100_s.min():.3f}, {on_durations_100_s.max():.3f}] s")
print(f"ON range  30%: [{on_durations_30_s.min():.3f}, {on_durations_30_s.max():.3f}] s")
print("\n=== STIM CHANNEL INTENSITY ===")
print(f"100% peak amplitude: {peak_stim_100:.6f}")
print(f" 30% peak amplitude: {peak_stim_30:.6f}")
print(f"Peak ratio 30%/100%: {peak_stim_30 / (peak_stim_100 + 1e-12):.3f}")
print(f"100% active RMS:     {active_rms_100:.6f}")
print(f" 30% active RMS:     {active_rms_30:.6f}")
print(f"RMS ratio 30%/100%:  {active_rms_30 / (active_rms_100 + 1e-12):.3f}")


# ============================================================
# 3) BUILD EPOCHS AROUND MEASURED BLOCK ONSETS
# ============================================================
reference_signal_100 = raw_100.copy().pick([REFERENCE_CHANNEL]).get_data()[0]
reference_signal_30 = raw_30.copy().pick([REFERENCE_CHANNEL]).get_data()[0]
reference_signal_base = raw_base.copy().pick([REFERENCE_CHANNEL]).get_data()[0]

pre_samples = int(round(EPOCH_PRE_S * sfreq))
post_samples = int(round(max_cycle_s * sfreq))
epoch_time_seconds = np.arange(-pre_samples, post_samples) / sfreq

epochs_100_v, valid_onsets_100 = plot_helpers.epoch_1d(reference_signal_100, block_onsets_100, pre_samples, post_samples)
epochs_30_v, valid_onsets_30 = plot_helpers.epoch_1d(reference_signal_30, block_onsets_30, pre_samples, post_samples)

baseline_stride_samples = int(round(max_cycle_s * sfreq))
baseline_start_sample = int(round(2.0 * sfreq))
baseline_stop_sample = len(reference_signal_base) - int(round(1.0 * sfreq))
baseline_pseudo_onsets = np.arange(baseline_start_sample, baseline_stop_sample, baseline_stride_samples, dtype=int)
epochs_base_v, valid_onsets_base = plot_helpers.epoch_1d(reference_signal_base, baseline_pseudo_onsets, pre_samples, post_samples)

epochs_100_uv = epochs_100_v * 1e6
epochs_30_uv = epochs_30_v * 1e6
epochs_base_uv = epochs_base_v * 1e6

summary_lines.extend([
    "",
    "Epoch counts",
    f"baseline_epochs={len(epochs_base_uv)}",
    f"30_epochs={len(epochs_30_uv)}",
    f"100_epochs={len(epochs_100_uv)}",
])

print(f"\nEpoch counts: baseline={len(epochs_base_uv)}  30%={len(epochs_30_uv)}  100%={len(epochs_100_uv)}")


# ============================================================
# 4) FIGURE 1: Cz MEAN WAVEFORM
# ============================================================
fig1, ax1 = plt.subplots(figsize=(12, 5))
ax1.axvspan(0.0, median_on_100_s, color="salmon", alpha=0.12, label=f"100% ON ({median_on_100_s:.2f} s)")
if abs(median_on_30_s - median_on_100_s) > (1.0 / sfreq):
    ax1.axvspan(0.0, median_on_30_s, color="cornflowerblue", alpha=0.08, label=f"30% ON ({median_on_30_s:.2f} s)")
ax1.plot(epoch_time_seconds, np.mean(epochs_base_uv, axis=0), "k", lw=1.2, label=f"baseline (n={len(epochs_base_uv)})")
ax1.plot(epoch_time_seconds, np.mean(epochs_30_uv, axis=0), "C0", lw=1.2, label=f"30% (n={len(epochs_30_uv)})")
ax1.plot(epoch_time_seconds, np.mean(epochs_100_uv, axis=0), "C3", lw=1.2, label=f"100% (n={len(epochs_100_uv)})")
ax1.set_xlim(-EPOCH_PRE_S, max_cycle_s)
ax1.set_xlabel("Time relative to STIM-defined ON-block onset (s)")
ax1.set_ylabel("Amplitude (uV)")
ax1.set_title("exp05: Mean Cz waveform aligned to STIM-defined block onset")
ax1.legend(fontsize=9)
fig1.tight_layout()
fig1.savefig(OUTPUT_DIRECTORY / "fig1_mean_cz_waveform.png", dpi=200)
plt.close(fig1)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig1_mean_cz_waveform.png'}")


# ============================================================
# 5) FIGURE 2: SELECTED-CHANNEL ENVELOPE COMPARISON
# ============================================================
available_channels = [channel_name for channel_name in COMPARE_CHANNELS if channel_name in raw_30.ch_names and channel_name in raw_100.ch_names]
fig2, axes2 = plt.subplots(len(available_channels), 1, figsize=(12, 2.5 * len(available_channels)), sharex=True)
axes2 = np.atleast_1d(axes2)

for ax, channel_name in zip(axes2, available_channels):
    channel_signal_100 = raw_100.copy().pick([channel_name]).get_data()[0]
    channel_signal_30 = raw_30.copy().pick([channel_name]).get_data()[0]
    epochs_channel_100_v, _ = plot_helpers.epoch_1d(channel_signal_100, block_onsets_100, pre_samples, post_samples)
    epochs_channel_30_v, _ = plot_helpers.epoch_1d(channel_signal_30, block_onsets_30, pre_samples, post_samples)

    envelope_db_100 = 20.0 * np.log10(np.abs(hilbert(epochs_channel_100_v, axis=-1)) + 1e-12)
    envelope_db_30 = 20.0 * np.log10(np.abs(hilbert(epochs_channel_30_v, axis=-1)) + 1e-12)

    ax.axvspan(0.0, median_on_100_s, color="salmon", alpha=0.12)
    ax.fill_between(epoch_time_seconds, np.percentile(envelope_db_30, 25, axis=0), np.percentile(envelope_db_30, 75, axis=0), color="C0", alpha=0.15)
    ax.fill_between(epoch_time_seconds, np.percentile(envelope_db_100, 25, axis=0), np.percentile(envelope_db_100, 75, axis=0), color="C3", alpha=0.15)
    ax.plot(epoch_time_seconds, np.median(envelope_db_30, axis=0), "C0", lw=1.2, label="30%")
    ax.plot(epoch_time_seconds, np.median(envelope_db_100, axis=0), "C3", lw=1.2, label="100%")
    ax.set_xlim(-EPOCH_PRE_S, max_cycle_s)
    ax.set_ylabel(f"{channel_name}\n(dB re V)")
    ax.grid(True, alpha=0.2)
    ax.legend(fontsize=7, loc="upper right")

axes2[-1].set_xlabel("Time relative to STIM-defined ON-block onset (s)")
fig2.suptitle("exp05: Broadband envelope per selected channel", fontsize=13)
fig2.tight_layout()
fig2.savefig(OUTPUT_DIRECTORY / "fig2_envelope_db.png", dpi=200)
plt.close(fig2)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig2_envelope_db.png'}")


# ============================================================
# 6) BUILD ALL-CHANNEL EPOCHS FOR SCALP-WIDE SUMMARY
# ============================================================
all_channels = [
    channel_name
    for channel_name in raw_100.ch_names
    if channel_name in raw_30.ch_names
    and channel_name.lower() not in ("stim", "ground_truth")
    and not channel_name.startswith("STI")
]
all_signal_100_uv = raw_100.copy().pick(all_channels).get_data() * 1e6
all_signal_30_uv = raw_30.copy().pick(all_channels).get_data() * 1e6
epochs_all_100_uv = np.array([
    all_signal_100_uv[:, onset_sample - pre_samples:onset_sample + post_samples]
    for onset_sample in block_onsets_100
    if onset_sample - pre_samples >= 0 and onset_sample + post_samples <= all_signal_100_uv.shape[1]
])
epochs_all_30_uv = np.array([
    all_signal_30_uv[:, onset_sample - pre_samples:onset_sample + post_samples]
    for onset_sample in block_onsets_30
    if onset_sample - pre_samples >= 0 and onset_sample + post_samples <= all_signal_30_uv.shape[1]
])


# ============================================================
# 7) FIGURE 3: POST-ON DECAY FIT
# ============================================================
fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
fit_results = []
for ax, label, epochs_all_uv, on_duration_s, off_duration_s, color in [
    (ax3a, "30%", epochs_all_30_uv, median_on_30_s, median_off_30_s, "C0"),
    (ax3b, "100%", epochs_all_100_uv, median_on_100_s, median_off_100_s, "C3"),
]:
    decay_start_s = on_duration_s + 0.05
    decay_end_s = on_duration_s + max(0.1, off_duration_s - 0.5)
    decay_mask = (epoch_time_seconds >= decay_start_s) & (epoch_time_seconds <= decay_end_s)
    t_decay_seconds = epoch_time_seconds[decay_mask] - on_duration_s
    mean_envelope_uv = np.mean(np.abs(hilbert(epochs_all_uv, axis=-1)), axis=(0, 1))[decay_mask]

    try:
        fit_params, _ = curve_fit(
            lambda time_s, amplitude_uv, tau_s, offset_uv: amplitude_uv * np.exp(-time_s / tau_s) + offset_uv,
            t_decay_seconds,
            mean_envelope_uv,
            p0=[mean_envelope_uv[0], 0.5, mean_envelope_uv[-1]],
            maxfev=10000,
        )
        fit_curve_uv = fit_params[0] * np.exp(-t_decay_seconds / fit_params[1]) + fit_params[2]
        ax.plot(t_decay_seconds, mean_envelope_uv, color=color, lw=1.5, label="data")
        ax.plot(t_decay_seconds, fit_curve_uv, "k--", lw=1.2, label=f"fit: tau={fit_params[1]:.3f} s")
        fit_results.append(f"{label}_tau_s={fit_params[1]:.3f}")
        fit_results.append(f"{label}_fit_amp_uv={fit_params[0]:.3f}")
        fit_results.append(f"{label}_fit_offset_uv={fit_params[2]:.3f}")
    except RuntimeError:
        ax.plot(t_decay_seconds, mean_envelope_uv, color=color, lw=1.5, label="data (fit failed)")
        fit_results.append(f"{label}_tau_s=fit_failed")

    ax.set_xlabel("Time after STIM-defined block offset (s)")
    ax.set_title(f"{label} post-ON decay (all-channel mean)")
    ax.legend(fontsize=8)

ax3a.set_ylabel("Envelope (uV)")
fig3.suptitle("exp05: Exponential decay after measured ON-block end (all-channel mean)", fontsize=13)
fig3.tight_layout()
fig3.savefig(OUTPUT_DIRECTORY / "fig3_decay_fit.png", dpi=200)
plt.close(fig3)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig3_decay_fit.png'}")


# ============================================================
# 8) SUMMARY METRICS
# ============================================================
comparison_on_s = min(median_on_100_s, median_on_30_s)
comparison_off_s = min(median_off_100_s, median_off_30_s)
pre_mask = (epoch_time_seconds >= -EPOCH_PRE_S) & (epoch_time_seconds < 0.0)
on_mask = (epoch_time_seconds >= 0.0) & (epoch_time_seconds < comparison_on_s)
off_mask = (epoch_time_seconds >= comparison_on_s) & (epoch_time_seconds < comparison_on_s + comparison_off_s)
post1_mask = (epoch_time_seconds >= comparison_on_s) & (epoch_time_seconds < comparison_on_s + 1.0)

print("\n--- DC offset (uV, common comparison window) ---")
for label, epochs_uv in [("baseline", epochs_base_uv), ("30%", epochs_30_uv), ("100%", epochs_100_uv)]:
    dc_pre_uv = float(np.mean(epochs_uv[:, pre_mask]))
    dc_on_uv = float(np.mean(epochs_uv[:, on_mask]))
    dc_off_uv = float(np.mean(epochs_uv[:, off_mask]))
    print(f"{label:>10s}  pre={dc_pre_uv:+.3f}  ON={dc_on_uv:+.3f}  OFF={dc_off_uv:+.3f} uV")
    summary_lines.extend([
        f"{label}_dc_pre_uv={dc_pre_uv:.3f}",
        f"{label}_dc_on_uv={dc_on_uv:.3f}",
        f"{label}_dc_off_uv={dc_off_uv:.3f}",
    ])

print("\n--- RMS (uV, common comparison window) ---")
for label, epochs_uv in [("baseline", epochs_base_uv), ("30%", epochs_30_uv), ("100%", epochs_100_uv)]:
    rms_on_uv = float(np.sqrt(np.mean(epochs_uv[:, on_mask] ** 2)))
    rms_off_uv = float(np.sqrt(np.mean(epochs_uv[:, off_mask] ** 2)))
    rms_post1_uv = float(np.sqrt(np.mean(epochs_uv[:, post1_mask] ** 2)))
    print(f"{label:>10s}  ON={rms_on_uv:.3f}  OFF={rms_off_uv:.3f}  first1s={rms_post1_uv:.3f} uV")
    summary_lines.extend([
        f"{label}_rms_on_uv={rms_on_uv:.3f}",
        f"{label}_rms_off_uv={rms_off_uv:.3f}",
        f"{label}_rms_post1_uv={rms_post1_uv:.3f}",
    ])


# ============================================================
# 9) CROSS-CHANNEL SUMMARY
# ============================================================
channel_rms_on_100_uv = np.sqrt(np.mean(epochs_all_100_uv[:, :, on_mask] ** 2, axis=(0, 2)))
channel_rms_on_30_uv = np.sqrt(np.mean(epochs_all_30_uv[:, :, on_mask] ** 2, axis=(0, 2)))
channel_rms_post1_100_uv = np.sqrt(np.mean(epochs_all_100_uv[:, :, post1_mask] ** 2, axis=(0, 2)))
channel_rms_post1_30_uv = np.sqrt(np.mean(epochs_all_30_uv[:, :, post1_mask] ** 2, axis=(0, 2)))
channel_on_ratio_30_over_100 = channel_rms_on_30_uv / (channel_rms_on_100_uv + 1e-12)
channel_post1_ratio_30_over_100 = channel_rms_post1_30_uv / (channel_rms_post1_100_uv + 1e-12)
cz_index = all_channels.index(REFERENCE_CHANNEL)

print("\n--- Cross-channel RMS summary ---")
print(f"30% < 100% in ON window:      {int(np.sum(channel_rms_on_30_uv < channel_rms_on_100_uv))}/{len(all_channels)} channels")
print(f"30% < 100% in first 1 s OFF:  {int(np.sum(channel_rms_post1_30_uv < channel_rms_post1_100_uv))}/{len(all_channels)} channels")
print(f"Median channel ratio 30/100 ON:     {np.median(channel_on_ratio_30_over_100):.3f}")
print(f"Median channel ratio 30/100 first1s:{np.median(channel_post1_ratio_30_over_100):.3f}")
print(f"Cz ratio 30/100 ON:                 {channel_on_ratio_30_over_100[cz_index]:.3f}")
print(f"Cz ratio 30/100 first1s:            {channel_post1_ratio_30_over_100[cz_index]:.3f}")

summary_lines.extend([
    "",
    "Cross-channel comparison",
    f"channels_30_lt_100_on={int(np.sum(channel_rms_on_30_uv < channel_rms_on_100_uv))}",
    f"channels_30_lt_100_post1={int(np.sum(channel_rms_post1_30_uv < channel_rms_post1_100_uv))}",
    f"median_channel_on_ratio_30_over_100={np.median(channel_on_ratio_30_over_100):.3f}",
    f"median_channel_post1_ratio_30_over_100={np.median(channel_post1_ratio_30_over_100):.3f}",
    f"Cz_on_ratio_30_over_100={channel_on_ratio_30_over_100[cz_index]:.3f}",
    f"Cz_post1_ratio_30_over_100={channel_post1_ratio_30_over_100[cz_index]:.3f}",
])

summary_lines.extend([
    "",
    "Common comparison window",
    f"comparison_on_s={comparison_on_s:.3f}",
    f"comparison_off_s={comparison_off_s:.3f}",
    f"post1_window_s=1.000",
    "",
    "Decay fit",
    *fit_results,
])

summary_path = OUTPUT_DIRECTORY / "artifact_summary.txt"
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
