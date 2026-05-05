"""What short clean pre/post pulse-locked Exp04 data should be exported for downstream topography and comparison?"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.optimize import curve_fit


# ============================================================
# CONFIG
# ============================================================
INPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-stim-mod-50hz-pulse-run01.vhdr"

OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP04_TEP_analysis\exp04_topo_video")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

PROCESSED_EPOCHS_PRE_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_pre-epo.fif"
PROCESSED_EPOCHS_POST_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_post-epo.fif"
PROCESSED_EVOKEDS_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_pre_post-ave.fif"
TIMECOURSE_FIGURE_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_time_course.png"
SUMMARY_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_summary.txt"

BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]

PULSE_ONSET_OFFSET_SAMPLES = 1008  # block start -> actual pulse onset in the stim run
EPOCH_TMIN_S = -3.0  # wide source epoch that contains baseline, pre, and post windows
EPOCH_TMAX_S = 1.0
BASELINE_WINDOW_S = (-2.0, -1.85)  # match the Exp04 joint-triptych baseline
PRE_WINDOW_S = (-1.8, -1.3)  # clean pre-OFF comparison segment
POST_WINDOW_S = (0.08, 0.508)  # clean post edge excluded through +0.08 s
LOWPASS_FREQ_HZ = 42.0


# ============================================================
# PIPELINE SKETCH
# ============================================================
# stim recording
#   -> detect pulse onsets from CP6 derivative
#   -> build wide pulse-locked epochs (-3 to +1 s)
#   -> baseline inside the clean OFF segment
#   -> split short clean pre and post windows
#   -> low-pass each segment independently
#   -> subtract the slow post decay with a per-channel exponential fit
#   -> save epochs, evokeds, and simple GFP QC


# ============================================================
# 1) LOAD STIMULATION RECORDING
# ============================================================
raw_stim = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)
raw_stim.pick_types(eeg=True).drop_channels(BAD_CHANNELS)

sfreq = float(raw_stim.info["sfreq"])
print(f"Loaded stim recording: {raw_stim.n_times / sfreq:.1f} s, sfreq={sfreq:.0f} Hz")
print(f"Retained EEG channels: {len(raw_stim.ch_names)}")


# ============================================================
# 2) DETECT PULSE ONSETS FROM CP6
# ============================================================
# Match the existing Exp04 scripts: CP6 has the clearest derivative jump.
cp6_data = raw_stim.copy().pick(["CP6"]).get_data()[0]
cp6_data = cp6_data - np.mean(cp6_data[:10000])

candidate_onsets = np.where(np.abs(np.diff(cp6_data)) > 0.01)[0] + 1
if candidate_onsets.size == 0:
    raise ValueError("Pulse detection found no candidates.")

stim_block_onsets_samples = [int(candidate_onsets[0])]
for sample_index in candidate_onsets[1:]:
    if sample_index - stim_block_onsets_samples[-1] > 1200:
        stim_block_onsets_samples.append(int(sample_index))
stim_block_onsets_samples = np.asarray(stim_block_onsets_samples, dtype=int)

stim_pulse_onsets_samples = stim_block_onsets_samples + PULSE_ONSET_OFFSET_SAMPLES
print(f"Detected stimulation pulses: {len(stim_pulse_onsets_samples)}")


# ============================================================
# 3) BUILD WIDE PULSE-LOCKED EVENTS
# ============================================================
pre_margin_samples = int(np.ceil(abs(EPOCH_TMIN_S) * sfreq))
post_margin_samples = int(np.ceil(EPOCH_TMAX_S * sfreq))
valid_mask = (
    (stim_pulse_onsets_samples >= pre_margin_samples)
    & (stim_pulse_onsets_samples + post_margin_samples < raw_stim.n_times)
)
valid_pulses = stim_pulse_onsets_samples[valid_mask]
if valid_pulses.size == 0:
    raise ValueError("No valid pulses remain for the requested -3 s to +1 s window.")

events_stim = np.column_stack(
    [valid_pulses, np.zeros(valid_pulses.size, dtype=int), np.ones(valid_pulses.size, dtype=int)]
).astype(int)
print(f"Valid pulses (full source epoch): {len(valid_pulses)}")


# ============================================================
# 4) BUILD WIDE EPOCHS AND APPLY BASELINE
# ============================================================
epochs_stim = mne.Epochs(
    raw_stim,
    events_stim,
    event_id={"pulse": 1},
    tmin=EPOCH_TMIN_S,
    tmax=EPOCH_TMAX_S,
    baseline=None,
    preload=True,
    verbose=False,
)
epochs_stim.apply_baseline(BASELINE_WINDOW_S)
print(f"Retained pulse-locked epochs: {len(epochs_stim)}")


# ============================================================
# 5) SPLIT CLEAN PRE AND POST WINDOWS
# ============================================================
epochs_pre = epochs_stim.copy().crop(tmin=PRE_WINDOW_S[0], tmax=PRE_WINDOW_S[1])
epochs_post = epochs_stim.copy().crop(tmin=POST_WINDOW_S[0], tmax=POST_WINDOW_S[1])

# Never filter across the stimulation boundary.
epochs_pre.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)
epochs_post.filter(l_freq=None, h_freq=LOWPASS_FREQ_HZ, verbose=False)

pre_n_samples = int(epochs_pre.get_data(copy=False).shape[-1])
post_n_samples = int(epochs_post.get_data(copy=False).shape[-1])
print(f"Exported window samples: pre={pre_n_samples}, post={post_n_samples}")


# ============================================================
# 6) REMOVE THE SLOW POST-PULSE DECAY
# ============================================================
# Match the earlier Exp04 TEP branch: fit the post evoked decay per channel,
# then subtract that fitted curve from every post epoch of that channel.
post_evoked_for_decay = epochs_post.average()
post_time_seconds = post_evoked_for_decay.times
post_fit_mask = post_time_seconds > 0.02
if not np.any(post_fit_mask):
    raise ValueError("Post decay fit window is empty.")

for channel_index in range(len(post_evoked_for_decay.ch_names)):
    channel_trace = post_evoked_for_decay.data[channel_index]
    fit_parameters, _ = curve_fit(
        lambda t, amplitude, tau, offset: amplitude * np.exp(-t / tau) + offset,
        post_time_seconds[post_fit_mask],
        channel_trace[post_fit_mask],
        maxfev=10000,
    )
    fitted_decay = (
        fit_parameters[0] * np.exp(-post_time_seconds / fit_parameters[1]) + fit_parameters[2]
    )
    epochs_post._data[:, channel_index, :] -= fitted_decay[np.newaxis, :]


# ============================================================
# 7) AVERAGE AND SAVE THE EXPORTED DATA
# ============================================================
epochs_pre.save(str(PROCESSED_EPOCHS_PRE_PATH), overwrite=True)
epochs_post.save(str(PROCESSED_EPOCHS_POST_PATH), overwrite=True)

evoked_pre = epochs_pre.average()
evoked_post = epochs_post.average()
evoked_pre.comment = "pre"
evoked_post.comment = "post"

mne.write_evokeds(str(PROCESSED_EVOKEDS_PATH), [evoked_pre, evoked_post], overwrite=True)
print(f"Saved pre epochs -> {PROCESSED_EPOCHS_PRE_PATH}")
print(f"Saved post epochs -> {PROCESSED_EPOCHS_POST_PATH}")
print(f"Saved processed evokeds -> {PROCESSED_EVOKEDS_PATH}")


# ============================================================
# 8) SAVE A SHORT-WINDOW GFP QC FIGURE
# ============================================================
gfp_pre_uv = np.std(evoked_pre.data, axis=0) * 1e6
gfp_post_uv = np.std(evoked_post.data, axis=0) * 1e6

fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
for axis, evoked, gfp_uv, title, color in zip(
    axes,
    (evoked_pre, evoked_post),
    (gfp_pre_uv, gfp_post_uv),
    ("PRE (-1.8 to -1.3 s)", "POST (+0.08 to +0.508 s)"),
    ("tab:blue", "tab:red"),
):
    axis.plot(evoked.times, gfp_uv, color=color, linewidth=1.8)
    axis.axvline(0.0, color="black", linestyle="--", linewidth=0.9)
    axis.set_title(title)
    axis.set_xlabel("Time (s)")
    axis.grid(alpha=0.25)

axes[0].set_ylabel("GFP (uV)")
fig.suptitle("EXP04 exported clean pre/post pulse windows")
fig.tight_layout()
fig.savefig(TIMECOURSE_FIGURE_PATH, dpi=220, bbox_inches="tight")
plt.close(fig)
print(f"Saved time-course QC -> {TIMECOURSE_FIGURE_PATH}")


# ============================================================
# 9) SAVE A SHORT SUMMARY
# ============================================================
summary_lines = [
    "EXP04 topo-video export summary",
    f"stim_vhdr_path={STIM_VHDR_PATH}",
    f"processed_epochs_pre_path={PROCESSED_EPOCHS_PRE_PATH}",
    f"processed_epochs_post_path={PROCESSED_EPOCHS_POST_PATH}",
    f"processed_evokeds_path={PROCESSED_EVOKEDS_PATH}",
    f"timecourse_figure_path={TIMECOURSE_FIGURE_PATH}",
    f"sampling_rate_hz={sfreq:.6f}",
    f"retained_channels={len(raw_stim.ch_names)}",
    f"detected_pulses={len(stim_pulse_onsets_samples)}",
    f"valid_pulses={len(valid_pulses)}",
    f"baseline_window_s={BASELINE_WINDOW_S}",
    f"pre_window_s={PRE_WINDOW_S}",
    f"post_window_s={POST_WINDOW_S}",
    f"pre_samples={pre_n_samples}",
    f"post_samples={post_n_samples}",
    f"lowpass_hz={LOWPASS_FREQ_HZ}",
    "post_decay_subtraction=per-channel exponential fit on post evoked",
]
SUMMARY_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved summary -> {SUMMARY_PATH}")
