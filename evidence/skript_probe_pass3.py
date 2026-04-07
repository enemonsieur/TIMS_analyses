"""Compare baseline vs stim Cz in the old Experiment_1 dataset."""

import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import preprocessing

DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\old\Experiment_1"); BASELINE_VHDR_PATH = DATA_DIRECTORY / "baseline-pre-STIM-not-turned-off.vhdr"; STIM_VHDR_PATH = DATA_DIRECTORY / "STIM_SP_01_notTurnedOff.vhdr"; OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\evidence\skript_probe_pass3_outputs"); OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
CZ_CHANNEL = "Cz"; WINDOW_START_S = 0.0; VIEW_WINDOW_S = 20.0; PSD_EPOCH_DURATION_S = 5.0; FILTER_RANGE_HZ = (0.5, 40.0); PSD_RANGE_HZ = (1.0, 40.0)
for warning_message in ("No coordinate information found for channels*", "Channels contain different highpass filters*", "Channels contain different lowpass filters*", "Not setting positions of 2 misc channels found in montage*"): warnings.filterwarnings("ignore", message=warning_message)
baseline_raw = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False); stim_raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False); sfreq = float(baseline_raw.info["sfreq"])
if not np.isclose(sfreq, float(stim_raw.info["sfreq"])): raise RuntimeError("Sampling rates differ between recordings.")
assert CZ_CHANNEL in baseline_raw.ch_names and CZ_CHANNEL in stim_raw.ch_names, "Cz missing."
print(f"Loaded recordings: baseline={baseline_raw.times[-1]:.1f}s stim={stim_raw.times[-1]:.1f}s sfreq={sfreq:.0f} Hz")
baseline_cz_uv = preprocessing.filter_signal(baseline_raw.copy().pick([CZ_CHANNEL]).get_data()[0], sfreq, *FILTER_RANGE_HZ) * 1e6
stim_cz_uv = preprocessing.filter_signal(stim_raw.copy().pick([CZ_CHANNEL]).get_data()[0], sfreq, *FILTER_RANGE_HZ) * 1e6
window_start_sample = int(round(WINDOW_START_S * sfreq))
window_stop_sample = window_start_sample + int(round(VIEW_WINDOW_S * sfreq))
if window_stop_sample > min(baseline_cz_uv.size, stim_cz_uv.size): raise RuntimeError("Requested window exceeds one recording.")
baseline_window_uv = baseline_cz_uv[window_start_sample:window_stop_sample]
stim_window_uv = stim_cz_uv[window_start_sample:window_stop_sample]
print(f"Window check: {baseline_window_uv.shape=} {stim_window_uv.shape=}")
baseline_epochs = mne.make_fixed_length_epochs(baseline_raw.copy().pick([CZ_CHANNEL]), duration=PSD_EPOCH_DURATION_S, preload=True, verbose=False)
stim_epochs = mne.make_fixed_length_epochs(stim_raw.copy().pick([CZ_CHANNEL]), duration=PSD_EPOCH_DURATION_S, preload=True, verbose=False)
assert len(baseline_epochs) > 0 and len(stim_epochs) > 0, "No PSD epochs."
print(f"Epoch check: baseline={len(baseline_epochs)} stim={len(stim_epochs)}")
baseline_psd = baseline_epochs.compute_psd(method="welch", fmin=PSD_RANGE_HZ[0], fmax=PSD_RANGE_HZ[1], n_fft=int(round(PSD_EPOCH_DURATION_S * sfreq)), verbose=False)
stim_psd = stim_epochs.compute_psd(method="welch", fmin=PSD_RANGE_HZ[0], fmax=PSD_RANGE_HZ[1], n_fft=int(round(PSD_EPOCH_DURATION_S * sfreq)), verbose=False)
baseline_psd_mean = baseline_psd.get_data().mean(axis=(0, 1))
stim_psd_mean = stim_psd.get_data().mean(axis=(0, 1))
baseline_peak_hz = float(baseline_psd.freqs[int(np.argmax(baseline_psd_mean))])
stim_peak_hz = float(stim_psd.freqs[int(np.argmax(stim_psd_mean))])
time_axis_seconds = np.arange(baseline_window_uv.size, dtype=float) / sfreq + WINDOW_START_S
fig, (ax_trace, ax_psd) = plt.subplots(2, 1, figsize=(11, 6.5), constrained_layout=True)
ax_trace.plot(time_axis_seconds, baseline_window_uv, color="gray", lw=1.1, label="baseline")
ax_trace.plot(time_axis_seconds, stim_window_uv, color="steelblue", lw=1.1, label="stim")
ax_trace.set(xlabel="Time from record start (s)", ylabel="Cz (uV)", title="Cz continuous window: baseline vs stim")
ax_trace.legend(loc="upper right"); ax_trace.grid(alpha=0.2)
ax_psd.plot(baseline_psd.freqs, 10.0 * np.log10(baseline_psd_mean + 1e-30), color="gray", lw=1.5, label="baseline")
ax_psd.plot(stim_psd.freqs, 10.0 * np.log10(stim_psd_mean + 1e-30), color="steelblue", lw=1.5, label="stim")
ax_psd.axvspan(*PSD_RANGE_HZ, color="moccasin", alpha=0.15); ax_psd.set(xlim=PSD_RANGE_HZ, xlabel="Frequency (Hz)", ylabel="Power (dB)", title="Average Cz PSD across fixed-length epochs")
ax_psd.legend(loc="upper right"); ax_psd.grid(alpha=0.2)
figure_path = OUTPUT_DIRECTORY / "cz_baseline_vs_stim.png"
fig.savefig(figure_path, dpi=220); plt.close(fig)
print(f"Saved -> {figure_path}")
summary_path = OUTPUT_DIRECTORY / "cz_baseline_vs_stim_summary.txt"
summary_path.write_text("\n".join(("Cz baseline vs stim probe", f"baseline_duration_s={baseline_raw.times[-1]:.3f}", f"stim_duration_s={stim_raw.times[-1]:.3f}", f"window_start_s={WINDOW_START_S:.3f}", f"window_stop_s={WINDOW_START_S + VIEW_WINDOW_S:.3f}", f"baseline_window_mean_uv={float(np.mean(baseline_window_uv)):.6f}", f"stim_window_mean_uv={float(np.mean(stim_window_uv)):.6f}", f"baseline_window_std_uv={float(np.std(baseline_window_uv)):.6f}", f"stim_window_std_uv={float(np.std(stim_window_uv)):.6f}", f"baseline_psd_peak_hz={baseline_peak_hz:.6f}", f"stim_psd_peak_hz={stim_peak_hz:.6f}")) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
