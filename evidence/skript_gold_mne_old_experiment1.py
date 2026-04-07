"""Compare baseline vs stim Cz with one time-window plot and one PSD summary."""

import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\old\Experiment_1")
BASELINE_VHDR_PATH = DATA_DIRECTORY / "baseline-pre-STIM-not-turned-off.vhdr"
STIM_VHDR_PATH = DATA_DIRECTORY / "STIM_SP_01_notTurnedOff.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\evidence\skript_gold_mne_old_experiment1_outputs")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Cz is the fixed scout channel because this example is about one readable
# single-channel comparison, not a multichannel search.
CHANNEL_NAME = "Cz"

# Show the first 20 s because that window already contains a visible stim-vs-
# baseline contrast in this old dataset without forcing the reader into a long trace.
WINDOW_START_S = 0.0
WINDOW_DURATION_S = 20.0

# Five-second epochs give a stable Welch PSD while staying easy to compare
# across recordings of different total duration.
PSD_EPOCH_DURATION_S = 5.0

# Keep the passband broad enough for a simple overview plot; this is not a
# narrowband analysis and should stay easy to interpret.
FILTER_RANGE_HZ = (0.5, 40.0)
PSD_RANGE_HZ = (1.0, 40.0)


# ===== Load ===================================================================
for warning_message in (
    "No coordinate information found for channels*",
    "Channels contain different highpass filters*",
    "Channels contain different lowpass filters*",
    "Not setting positions of 2 misc channels found in montage*",
):
    warnings.filterwarnings("ignore", message=warning_message)

baseline_raw = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)
stim_raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if CHANNEL_NAME not in baseline_raw.ch_names or CHANNEL_NAME not in stim_raw.ch_names:
    raise ValueError(f"Missing {CHANNEL_NAME} in one of the recordings.")

baseline_sfreq = float(baseline_raw.info["sfreq"])
stim_sfreq = float(stim_raw.info["sfreq"])
if not np.isclose(baseline_sfreq, stim_sfreq):
    raise RuntimeError(f"Sampling rates differ: baseline={baseline_sfreq}, stim={stim_sfreq}")

sfreq = baseline_sfreq
print(
    f"Loaded recordings: baseline={baseline_raw.n_times / sfreq:.1f}s "
    f"stim={stim_raw.n_times / sfreq:.1f}s sfreq={sfreq:.0f} Hz"
)


# ===== Prepare Cz =============================================================
# Keep this script MNE-native: the filtering is simple, used once, and easier
# to understand inline than through a repo helper.
baseline_cz = baseline_raw.copy().pick([CHANNEL_NAME])
stim_cz = stim_raw.copy().pick([CHANNEL_NAME])
baseline_cz.filter(*FILTER_RANGE_HZ, verbose=False)
stim_cz.filter(*FILTER_RANGE_HZ, verbose=False)

baseline_cz_uv = baseline_cz.get_data()[0] * 1e6
stim_cz_uv = stim_cz.get_data()[0] * 1e6

window_start_sample = int(round(WINDOW_START_S * sfreq))
window_duration_samples = int(round(WINDOW_DURATION_S * sfreq))
window_stop_sample = window_start_sample + window_duration_samples
window_limit_samples = min(baseline_cz.n_times, stim_cz.n_times)
if window_stop_sample > window_limit_samples:
    raise RuntimeError(
        f"Requested window {WINDOW_START_S:.1f}-{WINDOW_START_S + WINDOW_DURATION_S:.1f}s exceeds one recording."
    )

baseline_window_uv = baseline_cz_uv[window_start_sample:window_stop_sample]
stim_window_uv = stim_cz_uv[window_start_sample:window_stop_sample]
print(
    f"Window check: {CHANNEL_NAME} baseline={baseline_window_uv.shape} "
    f"stim={stim_window_uv.shape} window={WINDOW_START_S:.1f}-{WINDOW_START_S + WINDOW_DURATION_S:.1f}s"
)


# ===== PSD ====================================================================
# Use MNE's fixed-length epoching and PSD methods directly so the spectral logic
# stays visible in the script instead of disappearing into a helper.
baseline_epochs = mne.make_fixed_length_epochs(
    baseline_raw.copy().pick([CHANNEL_NAME]),
    duration=PSD_EPOCH_DURATION_S,
    overlap=0.0,
    preload=True,
    verbose=False,
)
stim_epochs = mne.make_fixed_length_epochs(
    stim_raw.copy().pick([CHANNEL_NAME]),
    duration=PSD_EPOCH_DURATION_S,
    overlap=0.0,
    preload=True,
    verbose=False,
)
if len(baseline_epochs) < 1 or len(stim_epochs) < 1:
    raise RuntimeError("Need at least one fixed-length epoch in each recording.")

print(f"Epoch check: baseline={len(baseline_epochs)} stim={len(stim_epochs)} epochs")

baseline_psd = baseline_epochs.compute_psd(
    method="welch",
    fmin=PSD_RANGE_HZ[0],
    fmax=PSD_RANGE_HZ[1],
    n_fft=int(round(PSD_EPOCH_DURATION_S * sfreq)),
    verbose=False,
)
stim_psd = stim_epochs.compute_psd(
    method="welch",
    fmin=PSD_RANGE_HZ[0],
    fmax=PSD_RANGE_HZ[1],
    n_fft=int(round(PSD_EPOCH_DURATION_S * sfreq)),
    verbose=False,
)
baseline_psd_mean = baseline_psd.get_data().mean(axis=(0, 1))
stim_psd_mean = stim_psd.get_data().mean(axis=(0, 1))
baseline_peak_hz = float(baseline_psd.freqs[int(np.argmax(baseline_psd_mean))])
stim_peak_hz = float(stim_psd.freqs[int(np.argmax(stim_psd_mean))])


# ===== Fig 1: Cz window + PSD =================================================
time_axis_seconds = np.arange(window_duration_samples, dtype=float) / sfreq + WINDOW_START_S
figure, (trace_axis, psd_axis) = plt.subplots(2, 1, figsize=(11, 6.5), constrained_layout=True)

trace_axis.plot(time_axis_seconds, baseline_window_uv, color="gray", lw=1.1, label="baseline")
trace_axis.plot(time_axis_seconds, stim_window_uv, color="steelblue", lw=1.1, label="stim")
trace_axis.set_xlabel("Time from record start (s)")
trace_axis.set_ylabel("Cz (uV)")
trace_axis.set_title("Cz continuous window: baseline vs stim")
trace_axis.legend(loc="upper right")
trace_axis.grid(alpha=0.2)

psd_axis.plot(baseline_psd.freqs, 10.0 * np.log10(baseline_psd_mean + 1e-30), color="gray", lw=1.5, label="baseline")
psd_axis.plot(stim_psd.freqs, 10.0 * np.log10(stim_psd_mean + 1e-30), color="steelblue", lw=1.5, label="stim")
psd_axis.axvspan(*PSD_RANGE_HZ, color="moccasin", alpha=0.15)
psd_axis.set_xlim(PSD_RANGE_HZ)
psd_axis.set_xlabel("Frequency (Hz)")
psd_axis.set_ylabel("Power (dB)")
psd_axis.set_title("Average Cz PSD across fixed-length epochs")
psd_axis.legend(loc="upper right")
psd_axis.grid(alpha=0.2)

figure_path = OUTPUT_DIRECTORY / "cz_baseline_vs_stim.png"
figure.savefig(figure_path, dpi=220)
plt.close(figure)
print(f"Saved -> {figure_path}")


# ===== Summary ================================================================
summary_path = OUTPUT_DIRECTORY / "cz_baseline_vs_stim_summary.txt"
summary_lines = [
    "Cz baseline vs stim gold example",
    f"baseline_duration_s={baseline_raw.n_times / sfreq:.3f}",
    f"stim_duration_s={stim_raw.n_times / sfreq:.3f}",
    f"channel_name={CHANNEL_NAME}",
    f"window_start_s={WINDOW_START_S:.3f}",
    f"window_duration_s={WINDOW_DURATION_S:.3f}",
    f"filter_range_hz=({FILTER_RANGE_HZ[0]:.3f}, {FILTER_RANGE_HZ[1]:.3f})",
    f"psd_range_hz=({PSD_RANGE_HZ[0]:.3f}, {PSD_RANGE_HZ[1]:.3f})",
    f"baseline_window_mean_uv={float(np.mean(baseline_window_uv)):.6f}",
    f"stim_window_mean_uv={float(np.mean(stim_window_uv)):.6f}",
    f"baseline_window_std_uv={float(np.std(baseline_window_uv)):.6f}",
    f"stim_window_std_uv={float(np.std(stim_window_uv)):.6f}",
    f"baseline_psd_peak_hz={baseline_peak_hz:.6f}",
    f"stim_psd_peak_hz={stim_peak_hz:.6f}",
    f"baseline_psd_epochs={len(baseline_epochs)}",
    f"stim_psd_epochs={len(stim_epochs)}",
]
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
