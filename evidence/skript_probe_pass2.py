"""Compare baseline vs stim Cz in the old Experiment_1 dataset."""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import preprocessing


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\old\Experiment_1")
BASELINE_VHDR_PATH = DATA_DIRECTORY / "baseline-pre-STIM-not-turned-off.vhdr"
STIM_VHDR_PATH = DATA_DIRECTORY / "STIM_SP_01_notTurnedOff.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\evidence\skript_probe_pass2_outputs")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

CZ_CHANNEL = "Cz"
WINDOW_START_S = 0.0
VIEW_WINDOW_S = 20.0
PSD_EPOCH_DURATION_S = 5.0
PSD_RANGE_HZ = (1.0, 40.0)
FILTER_RANGE_HZ = (0.5, 40.0)


# ===== Load ===================================================================
baseline_raw = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)
stim_raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if CZ_CHANNEL not in baseline_raw.ch_names or CZ_CHANNEL not in stim_raw.ch_names:
    raise ValueError(f"Missing {CZ_CHANNEL} in one of the recordings.")

baseline_sfreq = float(baseline_raw.info["sfreq"])
stim_sfreq = float(stim_raw.info["sfreq"])
if not np.isclose(baseline_sfreq, stim_sfreq):
    raise RuntimeError(f"Sampling rates differ: baseline={baseline_sfreq}, stim={stim_sfreq}")

sfreq = baseline_sfreq
print(f"Loaded recordings: baseline={baseline_raw.times[-1]:.1f}s stim={stim_raw.times[-1]:.1f}s sfreq={sfreq:.0f} Hz")


# ===== Prepare Cz =============================================================
# Cz is the fixed scout channel for this probe because the task is only to
# compare one continuous trace and one PSD summary between the two recordings.
baseline_cz_raw = baseline_raw.copy().pick([CZ_CHANNEL])
stim_cz_raw = stim_raw.copy().pick([CZ_CHANNEL])
baseline_cz_uv = preprocessing.filter_signal(
    baseline_cz_raw.get_data()[0],
    sampling_rate_hz=sfreq,
    low_hz=FILTER_RANGE_HZ[0],
    high_hz=FILTER_RANGE_HZ[1],
) * 1e6
stim_cz_uv = preprocessing.filter_signal(
    stim_cz_raw.get_data()[0],
    sampling_rate_hz=sfreq,
    low_hz=FILTER_RANGE_HZ[0],
    high_hz=FILTER_RANGE_HZ[1],
) * 1e6

window_start_sample = int(round(WINDOW_START_S * sfreq))
window_samples = int(round(VIEW_WINDOW_S * sfreq))
if window_samples < 1:
    raise RuntimeError("VIEW_WINDOW_S produced an empty window.")
window_stop_sample = window_start_sample + window_samples
window_limit_samples = min(baseline_cz_uv.size, stim_cz_uv.size)
if window_stop_sample > window_limit_samples:
    raise RuntimeError(
        f"Requested window {WINDOW_START_S:.1f}-{WINDOW_START_S + VIEW_WINDOW_S:.1f}s exceeds one recording."
    )
baseline_window_uv = baseline_cz_uv[window_start_sample:window_stop_sample]
stim_window_uv = stim_cz_uv[window_start_sample:window_stop_sample]
print(
    f"Window check: {CZ_CHANNEL} baseline={baseline_window_uv.shape} stim={stim_window_uv.shape} "
    f"window={WINDOW_START_S:.1f}-{WINDOW_START_S + VIEW_WINDOW_S:.1f}s"
)


# ===== Fig 1: Continuous view =================================================
time_axis_seconds = np.arange(window_samples, dtype=float) / sfreq + WINDOW_START_S
fig1, (ax_trace, ax_psd) = plt.subplots(2, 1, figsize=(11, 6.5), constrained_layout=True)
ax_trace.plot(time_axis_seconds, baseline_window_uv, color="gray", lw=1.1, label="baseline")
ax_trace.plot(time_axis_seconds, stim_window_uv, color="steelblue", lw=1.1, label="stim")
ax_trace.set_xlabel("Time from record start (s)")
ax_trace.set_ylabel("Cz (uV)")
ax_trace.set_title("Cz continuous window: baseline vs stim")
ax_trace.legend(loc="upper right")
ax_trace.grid(alpha=0.2)


# ===== PSD comparison =========================================================
baseline_epochs = mne.make_fixed_length_epochs(
    baseline_raw.copy().pick([CZ_CHANNEL]),
    duration=PSD_EPOCH_DURATION_S,
    overlap=0.0,
    preload=True,
    verbose=False,
)
stim_epochs = mne.make_fixed_length_epochs(
    stim_raw.copy().pick([CZ_CHANNEL]),
    duration=PSD_EPOCH_DURATION_S,
    overlap=0.0,
    preload=True,
    verbose=False,
)
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

ax_psd.plot(baseline_psd.freqs, 10.0 * np.log10(baseline_psd_mean + 1e-30), color="gray", lw=1.5, label="baseline")
ax_psd.plot(stim_psd.freqs, 10.0 * np.log10(stim_psd_mean + 1e-30), color="steelblue", lw=1.5, label="stim")
ax_psd.axvspan(*PSD_RANGE_HZ, color="moccasin", alpha=0.15)
ax_psd.set_xlim(PSD_RANGE_HZ)
ax_psd.set_xlabel("Frequency (Hz)")
ax_psd.set_ylabel("Power (dB)")
ax_psd.set_title("Average Cz PSD across fixed-length epochs")
ax_psd.legend(loc="upper right")
ax_psd.grid(alpha=0.2)

figure_path = OUTPUT_DIRECTORY / "cz_baseline_vs_stim.png"
fig1.savefig(figure_path, dpi=220)
plt.close(fig1)
print(f"Saved -> {figure_path}")


# ===== Summary ================================================================
summary_path = OUTPUT_DIRECTORY / "cz_baseline_vs_stim_summary.txt"
summary_lines = [
    "Cz baseline vs stim probe",
    f"baseline_duration_s={baseline_raw.times[-1]:.3f}",
    f"stim_duration_s={stim_raw.times[-1]:.3f}",
    f"window_duration_s={VIEW_WINDOW_S:.3f}",
    f"window_start_s={WINDOW_START_S:.3f}",
    f"window_stop_s={WINDOW_START_S + VIEW_WINDOW_S:.3f}",
    f"window_samples={window_samples}",
    f"baseline_window_mean_uv={float(np.mean(baseline_window_uv)):.6f}",
    f"stim_window_mean_uv={float(np.mean(stim_window_uv)):.6f}",
    f"baseline_window_std_uv={float(np.std(baseline_window_uv)):.6f}",
    f"stim_window_std_uv={float(np.std(stim_window_uv)):.6f}",
    f"baseline_psd_peak_hz={baseline_peak_hz:.6f}",
    f"stim_psd_peak_hz={stim_peak_hz:.6f}",
    f"filter_range_hz=({FILTER_RANGE_HZ[0]:.3f}, {FILTER_RANGE_HZ[1]:.3f})",
    f"psd_range_hz=({PSD_RANGE_HZ[0]:.3f}, {PSD_RANGE_HZ[1]:.3f})",
    f"baseline_psd_epochs={len(baseline_epochs)}",
    f"stim_psd_epochs={len(stim_epochs)}",
]
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
