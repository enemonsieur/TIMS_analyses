"""Show the raw full-cycle waveform that scales most clearly with run02 intensity."""

from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import plot_helpers
import preprocessing


# ============================================================
# CONFIG
# ============================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"  # measured run02 stimulation recording
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")  # explicit output folder
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]  # run02 dose order
BLOCK_CYCLES_PER_INTENSITY = 20  # cycles per dose block
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}  # keep the run02 EEG set aligned with the SSD scripts
RUN02_STIM_THRESHOLD_FRACTION = 0.08  # recover the weak first block

CANDIDATE_CHANNELS = ["O2", "O1", "Oz", "Pz", "P4", "P3"]  # posterior channels to test as raw references
INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]  # ordered dose ramp
FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_cycle.png"  # full-cycle reference figure
FIXED_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_cycle_fixed200.png"  # fixed-scale comparison figure


# ============================================================
# 1) LOAD THE RUN02 RECORDING
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channel: stim.")

sfreq = float(raw_stim_full.info["sfreq"])
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]
raw_eeg = raw_stim_full.copy().drop_channels(
    [
        channel_name
        for channel_name in raw_stim_full.ch_names
        if channel_name.lower() in {"stim", "ground_truth"}
        or channel_name.startswith("STI")
        or channel_name in EXCLUDED_CHANNELS
    ]
)
if len(raw_eeg.ch_names) == 0:
    raise RuntimeError("No retained EEG channels remain after removing stim, GT, and excluded channels.")


# ============================================================
# 2) RECOVER RUN02 CYCLE TIMING
# ============================================================
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace,
    sfreq,
    threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION,
)
required_block_count = len(RUN02_INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY
if len(block_onsets_samples) < required_block_count:
    raise RuntimeError(
        f"Need at least {required_block_count} measured ON blocks to analyze run02, "
        f"but found {len(block_onsets_samples)}."
    )

median_on_s = float(np.median((block_offsets_samples - block_onsets_samples) / sfreq))
median_cycle_samples = int(round(float(np.median(np.diff(block_onsets_samples)))))
median_cycle_s = median_cycle_samples / sfreq


# ============================================================
# 3) PICK THE RAW CHANNEL THAT SCALES MOST CLEARLY
# ============================================================
available_candidates = [channel_name for channel_name in CANDIDATE_CHANNELS if channel_name in raw_eeg.ch_names]
if not available_candidates:
    raise RuntimeError("None of the candidate raw channels are present in the retained EEG set.")

candidate_scores = []
for channel_name in available_candidates:
    raw_trace = raw_eeg.copy().pick([channel_name]).get_data()[0]
    block_mean_abs_uv = []
    for intensity_index in range(len(RUN02_INTENSITY_LABELS)):
        block_start_index = intensity_index * BLOCK_CYCLES_PER_INTENSITY
        block_stop_index = block_start_index + BLOCK_CYCLES_PER_INTENSITY
        dose_onsets = block_onsets_samples[block_start_index:block_stop_index]
        cycle_keep = np.ones(dose_onsets.shape[0], dtype=bool)
        cycle_keep[:-1] = dose_onsets[:-1] + median_cycle_samples <= dose_onsets[1:]
        cycle_keep[-1] = dose_onsets[-1] + median_cycle_samples <= raw_eeg.n_times
        cycle_epochs = preprocessing.extract_event_windows(
            raw_trace,
            dose_onsets[cycle_keep],
            median_cycle_samples,
        )
        block_mean_trace = cycle_epochs.mean(axis=0)
        block_mean_abs_uv.append(float(np.mean(np.abs(block_mean_trace)) * 1e6))

    diffs = np.diff(np.asarray(block_mean_abs_uv, dtype=float))
    candidate_scores.append(
        {
            "channel": channel_name,
            "monotonic": bool(np.all(diffs >= -1e-9)),
            "growth_uv": float(block_mean_abs_uv[-1] - block_mean_abs_uv[0]),
            "block_mean_abs_uv": block_mean_abs_uv,
        }
    )

monotonic_candidates = [row for row in candidate_scores if row["monotonic"]]
selection_pool = monotonic_candidates if monotonic_candidates else candidate_scores
selected_candidate = max(selection_pool, key=lambda row: row["growth_uv"])
selected_channel = str(selected_candidate["channel"])
selected_trace = raw_eeg.copy().pick([selected_channel]).get_data()[0]


# ============================================================
# 4) BUILD THE PER-INTENSITY RAW FULL-CYCLE WAVEFORMS
# ============================================================
panel_rows = []

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    block_start_index = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    block_stop_index = block_start_index + BLOCK_CYCLES_PER_INTENSITY
    dose_onsets = block_onsets_samples[block_start_index:block_stop_index]
    if len(dose_onsets) != BLOCK_CYCLES_PER_INTENSITY:
        raise RuntimeError(f"{intensity_label} in run02 does not contain the required 20 measured ON blocks.")

    cycle_keep = np.ones(dose_onsets.shape[0], dtype=bool)
    cycle_keep[:-1] = dose_onsets[:-1] + median_cycle_samples <= dose_onsets[1:]
    cycle_keep[-1] = dose_onsets[-1] + median_cycle_samples <= raw_eeg.n_times
    cycle_epochs_v = preprocessing.extract_event_windows(
        selected_trace,
        dose_onsets[cycle_keep],
        median_cycle_samples,
    )
    if cycle_epochs_v.shape[0] < 1:
        raise RuntimeError(f"{intensity_label} does not contain any valid raw full-cycle windows.")

    cycle_epochs_uv = cycle_epochs_v * 1e6
    mean_cycle_uv = np.mean(cycle_epochs_uv, axis=0)
    sem_cycle_uv = np.std(cycle_epochs_uv, axis=0, ddof=1) / np.sqrt(cycle_epochs_uv.shape[0])
    cycle_time_s = np.arange(median_cycle_samples, dtype=float) / sfreq

    panel_rows.append(
        {
            "label": intensity_label,
            "color": INTENSITY_COLORS[intensity_index],
            "event_count": int(cycle_epochs_uv.shape[0]),
            "cycle_time_s": cycle_time_s,
            "cycle_epochs_uv": cycle_epochs_uv,
            "mean_cycle_uv": mean_cycle_uv,
            "sem_cycle_uv": sem_cycle_uv,
        }
    )


# ============================================================
# 5) SAVE THE FULL-CYCLE REFERENCE FIGURE
# ============================================================
def _save_cycle_figure(output_path: Path, fixed_ylim_uv: tuple[float, float] | None, title: str) -> None:
    """Save the stacked full-cycle reference figure, optionally with fixed y-limits."""
    figure, axes = plt.subplots(len(panel_rows), 1, figsize=(9.2, 12.8), constrained_layout=True, sharex=True, sharey=False)

    for axis, row in zip(np.atleast_1d(axes), panel_rows, strict=True):
        if fixed_ylim_uv is None:
            local_values = np.concatenate([row["cycle_epochs_uv"].reshape(-1), row["mean_cycle_uv"]])
            local_ymin = float(np.min(local_values))
            local_ymax = float(np.max(local_values))
            local_ypad = max(5.0, 0.08 * (local_ymax - local_ymin))
            ylim = (local_ymin - local_ypad, local_ymax + local_ypad)
        else:
            ylim = fixed_ylim_uv

        axis.axvspan(0.0, median_on_s, color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.55)
        for epoch_trace_uv in row["cycle_epochs_uv"]:
            axis.plot(row["cycle_time_s"], epoch_trace_uv, color=row["color"], lw=0.6, alpha=0.08)
        axis.fill_between(
            row["cycle_time_s"],
            row["mean_cycle_uv"] - row["sem_cycle_uv"],
            row["mean_cycle_uv"] + row["sem_cycle_uv"],
            color=row["color"],
            alpha=0.18,
        )
        axis.plot(row["cycle_time_s"], row["mean_cycle_uv"], color=row["color"], lw=2.1)
        axis.set_title(f"{row['label']} (n={row['event_count']})", color=row["color"], pad=8)
        axis.set(
            ylabel=f"{selected_channel} (uV)",
            xlim=(0.0, median_cycle_s),
            ylim=ylim,
        )
        plot_helpers.style_clean_axis(axis, grid_alpha=0.10)

    axes = np.atleast_1d(axes)
    axes[0].text(
        0.02,
        0.96,
        f"Shaded = median measured ON interval\nSignal = raw {selected_channel}",
        transform=axes[0].transAxes,
        va="top",
        fontsize=8.0,
        color="0.25",
    )
    axes[-1].set_xlabel("Time from measured ON onset (s)")
    figure.suptitle(title, fontsize=12.2)
    figure.savefig(output_path, dpi=220)
    plt.close(figure)


_save_cycle_figure(
    output_path=FIGURE_PATH,
    fixed_ylim_uv=None,
    title=f"run02 raw {selected_channel} waveforms show how full-cycle amplitude grows with intensity",
)
_save_cycle_figure(
    output_path=FIXED_FIGURE_PATH,
    fixed_ylim_uv=(-200.0, 200.0),
    title=f"run02 raw {selected_channel} waveforms with fixed +/-200 uV scale reveal OFF recovery",
)


# ============================================================
# 6) PRINT SHORT REPORT
# ============================================================
print(f"selected_channel={selected_channel}")
for row in candidate_scores:
    rounded = [round(value, 3) for value in row["block_mean_abs_uv"]]
print(
        f"candidate={row['channel']} | monotonic={int(row['monotonic'])} "
        f"| growth_uv={row['growth_uv']:.3f} | mean_abs_uv={rounded}"
    )
print(f"saved={FIGURE_PATH.name} | panels={len(panel_rows)}")
print(f"saved={FIXED_FIGURE_PATH.name} | ylim_uv=(-200, 200)")
print(f"median_on_s={median_on_s:.3f} | median_cycle_s={median_cycle_s:.3f}")
