"""Explore exp05 baseline-first SSD transfer with FC1 as the fixed scout channel."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import hilbert
import plot_helpers
import preprocessing
def compute_itpc_curve(epoch_array, gt_epoch_array, band_hz, sfreq):
    """Compute GT-locked ITPC across matched epochs in one frequency band."""
    n_epochs = min(len(epoch_array), len(gt_epoch_array))
    eeg_band = preprocessing.filter_signal(epoch_array[:n_epochs], sfreq, band_hz[0], band_hz[1])
    gt_band = preprocessing.filter_signal(gt_epoch_array[:n_epochs], sfreq, band_hz[0], band_hz[1])
    phase_diff = np.angle(hilbert(eeg_band, axis=-1)) - np.angle(hilbert(gt_band, axis=-1))
    return np.abs(np.mean(np.exp(1j * phase_diff), axis=0)), n_epochs
# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
BASELINE_VHDR_PATH = DATA_DIRECTORY / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
STIM_30_VHDR_PATH = DATA_DIRECTORY / "exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP05_explore_fc1_baseline_ssd")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
CANDIDATE_CHANNELS = ["FC1", "P3", "CP1", "CP2"]
FOCUS_CHANNEL = "FC1"
GT_SEARCH_RANGE_HZ = (4.0, 12.0)
PSD_VIEW_RANGE_HZ = (5.0, 15.0)
SIGNAL_HALF_WIDTH_HZ = 0.5
BASELINE_EVENT_START_S = 2.0
BASELINE_STRIDE_S = 1.0
WINDOW_DURATION_S = 1.2
ON_WINDOW_S = (0.3, 1.5)
LATE_OFF_WINDOW_S = (1.5, 2.7)
N_COMP = 6

# ===== Load ===================================================================
raw_base_full = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)
raw_30_full = mne.io.read_raw_brainvision(str(STIM_30_VHDR_PATH), preload=True, verbose=False)
sfreq = float(raw_base_full.info["sfreq"])
if sfreq != float(raw_30_full.info["sfreq"]):
    raise RuntimeError("Baseline and 30% recordings must share the same sampling rate.")
ground_truth_base = raw_base_full.copy().pick(["ground_truth"]).get_data()[0]
ground_truth_30 = raw_30_full.copy().pick(["ground_truth"]).get_data()[0]
stim_marker_30 = raw_30_full.copy().pick(["stim"]).get_data()[0]
drop_base = [ch for ch in raw_base_full.ch_names if ch.lower() in ("stim", "ground_truth") or ch.startswith("STI")]
drop_30 = [ch for ch in raw_30_full.ch_names if ch.lower() in ("stim", "ground_truth") or ch.startswith("STI")]
raw_base_eeg = raw_base_full.copy().drop_channels(drop_base)
raw_30_eeg = raw_30_full.copy().drop_channels(drop_30)
common_channels = [ch for ch in raw_base_eeg.ch_names if ch in raw_30_eeg.ch_names]
raw_base_eeg.pick(common_channels).set_montage("standard_1020", on_missing="ignore", verbose=False)
raw_30_eeg.pick(common_channels).set_montage("standard_1020", on_missing="ignore", verbose=False)
if FOCUS_CHANNEL not in common_channels or any(ch not in common_channels for ch in CANDIDATE_CHANNELS):
    raise ValueError("Required FC1/P3/CP1/CP2 channels are not available in both recordings.")

# ===== Fig 1: Baseline channel scout ==========================================
gt_peak_frequency_hz = preprocessing.find_psd_peak_frequency(ground_truth_base, sfreq, GT_SEARCH_RANGE_HZ)
signal_band_hz = (gt_peak_frequency_hz - SIGNAL_HALF_WIDTH_HZ, gt_peak_frequency_hz + SIGNAL_HALF_WIDTH_HZ)
epochs_scout = mne.make_fixed_length_epochs(raw_base_eeg.copy().pick(CANDIDATE_CHANNELS), duration=5.0, overlap=0.0, preload=True, verbose=False)
psd_scout = epochs_scout.compute_psd(method="welch", fmin=PSD_VIEW_RANGE_HZ[0], fmax=PSD_VIEW_RANGE_HZ[1], n_fft=int(round(5.0 * sfreq)), verbose=False)
epochs_scout_band = mne.make_fixed_length_epochs(raw_base_eeg.copy().pick(CANDIDATE_CHANNELS).filter(*signal_band_hz, verbose=False), duration=5.0, overlap=0.0, preload=True, verbose=False)
fig1, axes1 = plt.subplots(2, len(CANDIDATE_CHANNELS), figsize=(14, 5.6), constrained_layout=True)
psd_scout_db = 10.0 * np.log10(psd_scout.get_data().mean(axis=0) + 1e-30)
temporal_scout_uv = epochs_scout_band.get_data().mean(axis=0) * 1e6
for i, channel_name in enumerate(CANDIDATE_CHANNELS):
    axes1[0, i].plot(psd_scout.freqs, psd_scout_db[i], color="black", lw=1.4)
    axes1[0, i].axvline(gt_peak_frequency_hz, color="darkorange", ls="--", lw=1.0)
    axes1[0, i].axvspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.8)
    axes1[0, i].set(title=channel_name, xlim=PSD_VIEW_RANGE_HZ); axes1[0, i].grid(alpha=0.2)
    axes1[1, i].plot(epochs_scout_band.times, temporal_scout_uv[i], color="steelblue", lw=1.2)
    axes1[1, i].axhline(0.0, color="gray", ls="--", lw=0.8); axes1[1, i].set_xlabel("Time (s)"); axes1[1, i].grid(alpha=0.2)
axes1[0, 0].set_ylabel("PSD (dB)"); axes1[1, 0].set_ylabel("Amplitude (uV)")
fig1.suptitle(f"exp05 baseline scout | fixed focus={FOCUS_CHANNEL} | GT peak={gt_peak_frequency_hz:.2f} Hz", fontsize=12)
fig1.savefig(OUTPUT_DIRECTORY / "fig1_baseline_channel_scout.png", dpi=220); plt.close(fig1)
# Optional auto-rank:
# candidate_scores = [(signal_band_hz[0] <= preprocessing.find_psd_peak_frequency(raw_base_eeg.copy().pick([ch]).get_data()[0], sfreq, PSD_VIEW_RANGE_HZ) <= signal_band_hz[1],
#                      preprocessing.compute_band_peak_ratio(raw_base_eeg.copy().pick([ch]).get_data()[0], sfreq, signal_band_hz, flank_width_hz=1.0, flank_gap_hz=0.5), ch)
#                     for ch in CANDIDATE_CHANNELS]
# print("Optional auto-rank winner:", max(candidate_scores)[-1])

# ===== Events and timing ======================================================
window_samples = int(round(WINDOW_DURATION_S * sfreq))
baseline_starts = np.arange(int(round(BASELINE_EVENT_START_S * sfreq)), raw_base_eeg.n_times - window_samples + 1, int(round(BASELINE_STRIDE_S * sfreq)), dtype=int)
events_base = np.column_stack([baseline_starts, np.zeros(len(baseline_starts), dtype=int), np.ones(len(baseline_starts), dtype=int)])
block_onsets_30, block_offsets_30 = preprocessing.detect_stim_blocks(stim_marker_30, sfreq)
on_starts_30 = block_onsets_30 + int(round(ON_WINDOW_S[0] * sfreq))
off_starts_30 = block_offsets_30[:-1] + int(round(LATE_OFF_WINDOW_S[0] * sfreq))
events_30_on = np.column_stack([on_starts_30[on_starts_30 + window_samples <= block_offsets_30], np.zeros(np.sum(on_starts_30 + window_samples <= block_offsets_30), dtype=int), np.ones(np.sum(on_starts_30 + window_samples <= block_offsets_30), dtype=int)])
events_30_off = np.column_stack([off_starts_30[off_starts_30 + window_samples <= block_onsets_30[1:]], np.zeros(np.sum(off_starts_30 + window_samples <= block_onsets_30[1:]), dtype=int), np.ones(np.sum(off_starts_30 + window_samples <= block_onsets_30[1:]), dtype=int)])
if min(len(events_base), len(events_30_on), len(events_30_off)) < 1:
    raise RuntimeError("Baseline, 30% ON, and 30% late-OFF events must all be non-empty.")
time_start = int(round(5.0 * sfreq)); time_stop = min(time_start + int(round(35.0 * sfreq)), raw_30_eeg.n_times)
time_axis_s = np.arange(time_stop - time_start, dtype=float) / sfreq + time_start / sfreq
focus_trace_uv = raw_30_eeg.copy().pick([FOCUS_CHANNEL]).get_data(start=time_start, stop=time_stop)[0] * 1e6
fig2, (ax_stim, ax_eeg) = plt.subplots(2, 1, figsize=(12, 5), sharex=True, constrained_layout=True)
ax_stim.plot(time_axis_s, stim_marker_30[time_start:time_stop], color="black", lw=1.0)
ax_eeg.plot(time_axis_s, focus_trace_uv, color="steelblue", lw=0.8)
for onset, offset in zip(block_onsets_30, block_offsets_30):
    if time_start <= onset < time_stop:
        ax_stim.axvspan(onset / sfreq, offset / sfreq, color="gray", alpha=0.25); ax_eeg.axvspan(onset / sfreq, offset / sfreq, color="gray", alpha=0.25)
for start_sample in events_30_off[:, 0]:
    if time_start <= start_sample < time_stop:
        ax_stim.axvspan(start_sample / sfreq, (start_sample + window_samples) / sfreq, color="cyan", alpha=0.35)
        ax_eeg.axvspan(start_sample / sfreq, (start_sample + window_samples) / sfreq, color="cyan", alpha=0.35)
ax_stim.set_ylabel("STIM (V)"); ax_eeg.set_ylabel(f"{FOCUS_CHANNEL} (uV)"); ax_eeg.set_xlabel("Time from record start (s)")
ax_stim.set_title("30% timing sanity: measured ON blocks and valid late-OFF windows"); ax_stim.grid(alpha=0.2); ax_eeg.grid(alpha=0.2)
fig2.savefig(OUTPUT_DIRECTORY / "fig2_timing_sanity.png", dpi=220); plt.close(fig2)

# ===== Baseline-first SSD =====================================================
n_comp = min(N_COMP, len(common_channels))
W_train, patterns_train, evals_train = plot_helpers.run_ssd(raw_base_eeg, events_base, signal_band_hz, PSD_VIEW_RANGE_HZ, n_comp=n_comp, epoch_duration_s=WINDOW_DURATION_S)
epochs_view_base, component_epochs_base = plot_helpers.build_ssd_component_epochs(raw_base_eeg, events_base, W_train, PSD_VIEW_RANGE_HZ, WINDOW_DURATION_S)
epochs_view_30_on, component_epochs_30_on = plot_helpers.build_ssd_component_epochs(raw_30_eeg, events_30_on, W_train, PSD_VIEW_RANGE_HZ, WINDOW_DURATION_S)
epochs_view_30_off, component_epochs_30_off = plot_helpers.build_ssd_component_epochs(raw_30_eeg, events_30_off, W_train, PSD_VIEW_RANGE_HZ, WINDOW_DURATION_S)
gt_epochs = {
    "base": np.asarray([ground_truth_base[s:s + window_samples] for s in events_base[:, 0]], dtype=float),
    "on": np.asarray([ground_truth_30[s:s + window_samples] for s in events_30_on[:, 0]], dtype=float),
    "off": np.asarray([ground_truth_30[s:s + window_samples] for s in events_30_off[:, 0]], dtype=float),
}
gt_band_epochs = {key: preprocessing.filter_signal(gt_epochs[key], sfreq, signal_band_hz[0], signal_band_hz[1]) for key in ("base", "off")}
component_metrics = []
for component_index in range(n_comp):
    component_view_epochs = component_epochs_base[component_index]
    component_band_epochs = preprocessing.filter_signal(component_view_epochs, sfreq, signal_band_hz[0], signal_band_hz[1])
    component_view_vector, component_band_vector, gt_band_vector = component_view_epochs.reshape(-1), component_band_epochs.reshape(-1), gt_band_epochs["base"].reshape(-1)
    phase_samples = preprocessing.sample_phase_differences(gt_band_vector, component_band_vector, sfreq, gt_peak_frequency_hz)
    peak_frequency_hz = preprocessing.find_psd_peak_frequency(component_view_vector, sfreq, PSD_VIEW_RANGE_HZ)
    component_metrics.append({"peak_in_band": signal_band_hz[0] <= peak_frequency_hz <= signal_band_hz[1], "peak_frequency_hz": peak_frequency_hz, "peak_ratio": preprocessing.compute_band_peak_ratio(component_view_vector, sfreq, signal_band_hz, flank_width_hz=1.0, flank_gap_hz=0.5), "coherence": preprocessing.compute_coherence_band(component_band_vector, gt_band_vector, sfreq, signal_band_hz[0], signal_band_hz[1]), "plv": float(np.abs(np.mean(np.exp(1j * phase_samples)))), "lambda": float(evals_train[component_index])})
selection_pool = [idx for idx, row in enumerate(component_metrics) if row["peak_in_band"]] or list(range(n_comp)); selection_mode = "target_band_candidates" if any(row["peak_in_band"] for row in component_metrics) else "fallback_all_components"
selected_component_index = max(selection_pool, key=lambda idx: tuple(component_metrics[idx][key] for key in ("peak_ratio", "coherence", "plv", "lambda")))
selected_component_number = selected_component_index + 1
selected_pattern = patterns_train[:, selected_component_index].copy()
selected_epochs = {"base": component_epochs_base[selected_component_index].copy(), "on": component_epochs_30_on[selected_component_index].copy(), "off": component_epochs_30_off[selected_component_index].copy()}
selected_band = {key: preprocessing.filter_signal(selected_epochs[key], sfreq, signal_band_hz[0], signal_band_hz[1]) for key in selected_epochs}
if np.corrcoef(selected_band["base"].reshape(-1), gt_band_epochs["base"].reshape(-1))[0, 1] < 0:
    selected_pattern *= -1.0
    for key in selected_epochs:
        selected_epochs[key] *= -1.0
    selected_band = {key: preprocessing.filter_signal(selected_epochs[key], sfreq, signal_band_hz[0], signal_band_hz[1]) for key in selected_epochs}
metrics_summary = {}
for label, epoch_key, gt_key in [("baseline", "base", "base"), ("30pct_late_off", "off", "off")]:
    phase_samples = preprocessing.sample_phase_differences(gt_band_epochs[gt_key].reshape(-1), selected_band[epoch_key].reshape(-1), sfreq, gt_peak_frequency_hz)
    metrics_summary[label] = {"peak_frequency_hz": preprocessing.find_psd_peak_frequency(selected_epochs[epoch_key].reshape(-1), sfreq, PSD_VIEW_RANGE_HZ), "peak_ratio": preprocessing.compute_band_peak_ratio(selected_epochs[epoch_key].reshape(-1), sfreq, signal_band_hz, flank_width_hz=1.0, flank_gap_hz=0.5), "coherence": preprocessing.compute_coherence_band(selected_band[epoch_key].reshape(-1), gt_band_epochs[gt_key].reshape(-1), sfreq, signal_band_hz[0], signal_band_hz[1]), "plv": float(np.abs(np.mean(np.exp(1j * phase_samples))))}

# ===== Fig 3: Selected-component transfer summary =============================
psd_base, freqs_base = mne.time_frequency.psd_array_welch(selected_epochs["base"], sfreq, fmin=PSD_VIEW_RANGE_HZ[0], fmax=PSD_VIEW_RANGE_HZ[1], n_fft=window_samples, verbose=False)
psd_off, freqs_off = mne.time_frequency.psd_array_welch(selected_epochs["off"], sfreq, fmin=PSD_VIEW_RANGE_HZ[0], fmax=PSD_VIEW_RANGE_HZ[1], n_fft=window_samples, verbose=False)
mean_psd_base, mean_psd_off = psd_base.mean(axis=0), psd_off.mean(axis=0)
mean_psd_base /= max(float(np.max(mean_psd_base)), 1e-30); mean_psd_off /= max(float(np.max(mean_psd_off)), 1e-30)
trace_base = selected_band["base"].mean(axis=0); trace_off = selected_band["off"].mean(axis=0)
trace_base_z = (trace_base - np.mean(trace_base)) / (np.std(trace_base) + 1e-12); trace_off_z = (trace_off - np.mean(trace_off)) / (np.std(trace_off) + 1e-12)
fig3, axes3 = plt.subplots(2, 2, figsize=(11.5, 7.0), constrained_layout=True)
mne.viz.plot_topomap(selected_pattern, epochs_view_base.info, ch_type="eeg", axes=axes3[0, 0], show=False, cmap=plot_helpers.TIMS_TOPO_CMAP)
axes3[0, 0].set_title(f"Comp {selected_component_number} | lambda={evals_train[selected_component_index]:.2f}")
axes3[0, 1].plot(freqs_base, mean_psd_base, color="gray", lw=1.8, label="baseline")
axes3[0, 1].plot(freqs_off, mean_psd_off, color="steelblue", lw=1.8, label="30% late-OFF")
axes3[0, 1].axvspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.8)
axes3[0, 1].axvline(gt_peak_frequency_hz, color="darkorange", ls="--", lw=1.0); axes3[0, 1].set(xlabel="Frequency (Hz)", ylabel="Relative PSD", xlim=PSD_VIEW_RANGE_HZ)
axes3[0, 1].legend(fontsize=8, loc="upper right"); axes3[0, 1].grid(alpha=0.2)
axes3[1, 0].plot(epochs_view_base.times, trace_base_z, color="gray", lw=1.6, label="baseline")
axes3[1, 0].plot(epochs_view_30_off.times, trace_off_z, color="steelblue", lw=1.6, label="30% late-OFF")
axes3[1, 0].set(xlabel="Time within window (s)", ylabel="Mean trace (z)"); axes3[1, 0].legend(fontsize=8, loc="upper right"); axes3[1, 0].grid(alpha=0.2)
axes3[1, 1].axis("off")
axes3[1, 1].text(0.0, 1.0, "\n".join([f"focus_channel={FOCUS_CHANNEL}", f"selected_component={selected_component_number}", f"gt_peak_hz={gt_peak_frequency_hz:.3f}", f"signal_band_hz=({signal_band_hz[0]:.3f}, {signal_band_hz[1]:.3f})", f"baseline_peak_hz={metrics_summary['baseline']['peak_frequency_hz']:.3f}", f"baseline_peak_ratio={metrics_summary['baseline']['peak_ratio']:.3f}", f"baseline_coherence={metrics_summary['baseline']['coherence']:.3f}", f"baseline_plv={metrics_summary['baseline']['plv']:.3f}", f"30pct_peak_hz={metrics_summary['30pct_late_off']['peak_frequency_hz']:.3f}", f"30pct_peak_ratio={metrics_summary['30pct_late_off']['peak_ratio']:.3f}", f"30pct_coherence={metrics_summary['30pct_late_off']['coherence']:.3f}", f"30pct_plv={metrics_summary['30pct_late_off']['plv']:.3f}"]), va="top", family="monospace")
fig3.suptitle("exp05 selected baseline-trained SSD component", fontsize=12)
fig3.savefig(OUTPUT_DIRECTORY / "fig3_selected_component_summary.png", dpi=220); plt.close(fig3)

# ===== Fig 4: TFR + phase consistency ========================================
tmp_tfr_path = OUTPUT_DIRECTORY / "_tmp_tfr_panel.png"
plot_helpers.plot_ssd_component_tfr(epochs=epochs_view_30_off, component_epochs=selected_epochs["off"][np.newaxis, :, :], spectral_ratios=[float(evals_train[selected_component_index])], condition_name="30% late-OFF selected SSD component", output_path=tmp_tfr_path, n_components=1, frequency_range_hz=PSD_VIEW_RANGE_HZ, display_window_s=(0.0, WINDOW_DURATION_S), reference_frequency_hz=gt_peak_frequency_hz, component_numbers=[selected_component_number], time_offset_s=LATE_OFF_WINDOW_S[0])
itpc_on, n_on = compute_itpc_curve(selected_epochs["on"], gt_epochs["on"], signal_band_hz, sfreq)
itpc_off, n_off = compute_itpc_curve(selected_epochs["off"], gt_epochs["off"], signal_band_hz, sfreq)
fig4, axes4 = plt.subplots(1, 2, figsize=(12.5, 4.5), constrained_layout=True)
axes4[0].imshow(plt.imread(tmp_tfr_path)); axes4[0].axis("off"); axes4[0].set_title("30% late-OFF selected-component TFR")
axes4[1].plot(epochs_view_30_on.times, itpc_on, color="firebrick", lw=1.8, label="30% mid-ON")
axes4[1].plot(epochs_view_30_off.times, itpc_off, color="steelblue", lw=1.8, label="30% late-OFF")
axes4[1].axhline(1.0 / np.sqrt(min(n_on, n_off)), color="gray", ls=":", lw=1.0, label=f"chance={1.0 / np.sqrt(min(n_on, n_off)):.2f}")
axes4[1].set(xlabel="Time within window (s)", ylabel="ITPC", ylim=(0.0, 1.0)); axes4[1].set_title(f"GT-locked phase consistency ({signal_band_hz[0]:.1f}-{signal_band_hz[1]:.1f} Hz)")
axes4[1].legend(fontsize=8, loc="upper right"); axes4[1].grid(alpha=0.2)
fig4.savefig(OUTPUT_DIRECTORY / "fig4_tfr_and_phase_consistency.png", dpi=220); plt.close(fig4)
tmp_tfr_path.unlink(missing_ok=True)

# ===== Summary ================================================================
summary_path = OUTPUT_DIRECTORY / "summary.txt"
summary_lines = [
    "exp05 fc1 baseline-first ssd exploratory", f"focus_channel={FOCUS_CHANNEL}", f"candidate_channels={CANDIDATE_CHANNELS}", f"selection_mode={selection_mode}",
    f"gt_peak_frequency_hz={gt_peak_frequency_hz:.6f}", f"signal_band_hz=({signal_band_hz[0]:.6f}, {signal_band_hz[1]:.6f})",
    f"baseline_events={len(events_base)}", f"events_30_on={len(events_30_on)}", f"events_30_late_off={len(events_30_off)}",
    f"selected_component={selected_component_number}", f"selected_lambda={evals_train[selected_component_index]:.6f}",
    f"baseline_peak_frequency_hz={metrics_summary['baseline']['peak_frequency_hz']:.6f}", f"baseline_peak_ratio={metrics_summary['baseline']['peak_ratio']:.6f}",
    f"baseline_coherence={metrics_summary['baseline']['coherence']:.6f}", f"baseline_plv={metrics_summary['baseline']['plv']:.6f}",
    f"late_off_peak_frequency_hz={metrics_summary['30pct_late_off']['peak_frequency_hz']:.6f}", f"late_off_peak_ratio={metrics_summary['30pct_late_off']['peak_ratio']:.6f}",
    f"late_off_coherence={metrics_summary['30pct_late_off']['coherence']:.6f}", f"late_off_plv={metrics_summary['30pct_late_off']['plv']:.6f}",
    f"itpc_on_epochs={n_on}", f"itpc_off_epochs={n_off}",
]
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig1_baseline_channel_scout.png'}")
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig2_timing_sanity.png'}")
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig3_selected_component_summary.png'}")
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig4_tfr_and_phase_consistency.png'}")
print(f"Saved -> {summary_path}")
