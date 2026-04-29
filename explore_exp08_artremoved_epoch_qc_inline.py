"""Show individual EXP08 run01 artremoved epochs for one editable channel/intensity QC check."""

import os
from pathlib import Path

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import matplotlib.pyplot as plt
import mne
import numpy as np


# ============================================================
# CONFIG
# ============================================================

EPOCH_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY = EPOCH_DIRECTORY  # inline-only by default; kept explicit for repo convention
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

INTENSITY_PCT = 100  # edit to 10, 20, ..., 100
CHANNELS_TO_SHOW = ["Oz"]  # edit to one or more retained EEG channels

DISPLAY_WINDOW_S = (-0.10, 0.60)  # pulse-centered QC window shown in the plot
ARTIFACT_CUT_WINDOW_S = (-0.010, 0.020)  # run01 interpolation window from wiki validation
POST_PULSE_SUMMARY_WINDOW_S = (0.020, 0.600)  # residual post-pulse amplitude summary
Y_LIMIT_UV = None  # set e.g. (-100, 100) when inspecting small residuals

APPLY_DISPLAY_FILTER = True  # plot-only smoothing; source data and residual stats stay unfiltered
DISPLAY_FILTER_HZ = (None, 45.0)  # (high-pass, low-pass); use (1.0, 45.0) for band-pass view
DISPLAY_FILTER_IIR_PARAMS = dict(order=4, ftype="butter")  # simple short-epoch-friendly filter
DISPLAY_FILTER_PHASE = "forward"  # causal view avoids zero-phase back-smearing around the pulse

CENTER_EACH_EPOCH_FOR_DISPLAY = True
CENTER_WINDOW_S = (-0.100, -0.020)  # quiet pre-pulse baseline; avoids the interpolated artifact

SHOW_RAW_COMPARISON = False  # keep False for default artremoved-only QC

COLOR_CLEAN = "#2176ae"
COLOR_RAW = "#8a8a8a"
COLOR_PULSE = "#d62828"
COLOR_CUT = "#f2cc8f"


# ============================================================
# PIPELINE OVERVIEW
# ============================================================
#
# EXP08 run01 artremoved epochs
#   -> choose intensity and channel(s)
#   -> load exp08_epochs_{pct}pct_on_artremoved-epo.fif
#   -> extract individual epochs without averaging
#   -> keep residual summaries unfiltered; optionally filter only the displayed traces
#   -> convert Volts to uV only for plotting and summaries
#   -> center each epoch/channel for display around pre-pulse zero
#   -> plot every epoch trace with pulse/removal-window markers
#   -> print per-epoch residual amplitude summaries


# ============================================================
# 1) LOAD ARTREMOVED EPOCHS
# ============================================================

clean_path = EPOCH_DIRECTORY / f"exp08_epochs_{INTENSITY_PCT}pct_on_artremoved-epo.fif"
if clean_path.name.startswith("exp08t_"):
    raise RuntimeError("Invalid source: exp08t_* files belong to triplet run02, not EXP08 run01.")
if not clean_path.exists():
    raise FileNotFoundError(f"Missing artremoved run01 epoch file: {clean_path}")

clean_epochs = mne.read_epochs(clean_path, preload=True, verbose=False)
raw_epochs = None

if SHOW_RAW_COMPARISON:
    raw_path = EPOCH_DIRECTORY / f"exp08_epochs_{INTENSITY_PCT}pct_on-epo.fif"
    if raw_path.name.startswith("exp08t_"):
        raise RuntimeError("Invalid source: exp08t_* files belong to triplet run02, not EXP08 run01.")
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing raw run01 epoch file: {raw_path}")
    raw_epochs = mne.read_epochs(raw_path, preload=True, verbose=False)
    if raw_epochs.ch_names != clean_epochs.ch_names or len(raw_epochs) != len(clean_epochs):
        raise RuntimeError("Raw and artremoved epoch files do not match in channels or epoch count.")

missing_channels = [channel for channel in CHANNELS_TO_SHOW if channel not in clean_epochs.ch_names]
if missing_channels:
    raise RuntimeError(f"Requested channels are missing from artremoved epochs: {missing_channels}")

times_s = np.asarray(clean_epochs.times, dtype=float)
display_mask = (times_s >= DISPLAY_WINDOW_S[0]) & (times_s <= DISPLAY_WINDOW_S[1])
cut_mask = (times_s >= ARTIFACT_CUT_WINDOW_S[0]) & (times_s <= ARTIFACT_CUT_WINDOW_S[1])
post_mask = (times_s >= POST_PULSE_SUMMARY_WINDOW_S[0]) & (times_s <= POST_PULSE_SUMMARY_WINDOW_S[1])
center_mask = (times_s >= CENTER_WINDOW_S[0]) & (times_s <= CENTER_WINDOW_S[1])

if not np.any(display_mask):
    raise RuntimeError("DISPLAY_WINDOW_S does not overlap the epoch time axis.")
if not np.any(cut_mask):
    raise RuntimeError("ARTIFACT_CUT_WINDOW_S does not overlap the epoch time axis.")
if not np.any(post_mask):
    raise RuntimeError("POST_PULSE_SUMMARY_WINDOW_S does not overlap the epoch time axis.")
if CENTER_EACH_EPOCH_FOR_DISPLAY and not np.any(center_mask):
    raise RuntimeError("CENTER_WINDOW_S does not overlap the epoch time axis.")

if APPLY_DISPLAY_FILTER:
    low_hz, high_hz = DISPLAY_FILTER_HZ
    if low_hz is None and high_hz is None:
        raise RuntimeError("DISPLAY_FILTER_HZ must set at least one frequency when filtering is enabled.")
    if low_hz is not None and high_hz is not None and not (0.0 < low_hz < high_hz):
        raise RuntimeError("DISPLAY_FILTER_HZ must satisfy 0 < high-pass < low-pass.")

print(
    f"Loaded {clean_path.name}: {len(clean_epochs)} epochs, "
    f"{len(clean_epochs.ch_names)} channels, {clean_epochs.info['sfreq']:.0f} Hz"
)
print("No averaging applied. Residual stats use unfiltered artremoved data converted to uV for QC only.")
if APPLY_DISPLAY_FILTER:
    filter_low_label = "DC" if DISPLAY_FILTER_HZ[0] is None else f"{DISPLAY_FILTER_HZ[0]:g} Hz"
    filter_high_label = "Nyquist" if DISPLAY_FILTER_HZ[1] is None else f"{DISPLAY_FILTER_HZ[1]:g} Hz"
    print(
        f"Plot traces use a display-only {DISPLAY_FILTER_PHASE} IIR filter: "
        f"{filter_low_label} to {filter_high_label}."
    )
else:
    print("Plot traces are unfiltered.")
if CENTER_EACH_EPOCH_FOR_DISPLAY:
    print(
        f"Plot traces are display-centered per epoch/channel using median "
        f"{CENTER_WINDOW_S[0]:.3f} to {CENTER_WINDOW_S[1]:.3f} s."
    )


# ============================================================
# 2) PRINT RESIDUAL AMPLITUDE SUMMARIES
# ============================================================

clean_data_v = clean_epochs.get_data(picks=CHANNELS_TO_SHOW)
# -> (n_epochs, n_channels, n_samples), still in Volts from the FIF file
clean_data_uv = clean_data_v * 1e6

clean_display_epochs = clean_epochs.copy().pick(CHANNELS_TO_SHOW)
if APPLY_DISPLAY_FILTER:
    clean_display_epochs.filter(
        l_freq=DISPLAY_FILTER_HZ[0],
        h_freq=DISPLAY_FILTER_HZ[1],
        method="iir",
        iir_params=DISPLAY_FILTER_IIR_PARAMS,
        phase=DISPLAY_FILTER_PHASE,
        verbose=False,
    )
clean_display_data_uv = clean_display_epochs.get_data() * 1e6

if CENTER_EACH_EPOCH_FOR_DISPLAY:
    clean_center_uv = np.median(clean_data_uv[:, :, center_mask], axis=2, keepdims=True)
    clean_summary_uv = clean_data_uv - clean_center_uv
    clean_display_center_uv = np.median(clean_display_data_uv[:, :, center_mask], axis=2, keepdims=True)
    clean_plot_uv = clean_display_data_uv - clean_display_center_uv
else:
    clean_summary_uv = clean_data_uv
    clean_plot_uv = clean_display_data_uv

for channel_index, channel_name in enumerate(CHANNELS_TO_SHOW):
    channel_uv = clean_summary_uv[:, channel_index, :]
    cut_abs_uv = np.max(np.abs(channel_uv[:, cut_mask]), axis=1)
    post_abs_uv = np.max(np.abs(channel_uv[:, post_mask]), axis=1)

    summary_label = "display-centered, unfiltered" if CENTER_EACH_EPOCH_FOR_DISPLAY else "uncentered, unfiltered"
    print(f"\n{INTENSITY_PCT}% {channel_name} artremoved residuals ({summary_label})")
    print(f"  artifact-cut {ARTIFACT_CUT_WINDOW_S[0]:.3f} to {ARTIFACT_CUT_WINDOW_S[1]:.3f} s:")
    print(
        f"    median={np.median(cut_abs_uv):.1f} uV, "
        f"p95={np.percentile(cut_abs_uv, 95):.1f} uV, max={np.max(cut_abs_uv):.1f} uV"
    )
    print(f"  post-pulse {POST_PULSE_SUMMARY_WINDOW_S[0]:.3f} to {POST_PULSE_SUMMARY_WINDOW_S[1]:.3f} s:")
    print(
        f"    median={np.median(post_abs_uv):.1f} uV, "
        f"p95={np.percentile(post_abs_uv, 95):.1f} uV, max={np.max(post_abs_uv):.1f} uV"
    )


# ============================================================
# 3) PLOT INDIVIDUAL EPOCHS INLINE
# ============================================================

panels_per_channel = 2 if SHOW_RAW_COMPARISON else 1
fig, axes = plt.subplots(
    len(CHANNELS_TO_SHOW) * panels_per_channel,
    1,
    figsize=(11, 3.2 * len(CHANNELS_TO_SHOW) * panels_per_channel),
    sharex=True,
    squeeze=False,
)
axes_flat = axes.ravel()
time_display_s = times_s[display_mask]

panel_index = 0
for channel_index, channel_name in enumerate(CHANNELS_TO_SHOW):
    if SHOW_RAW_COMPARISON:
        raw_display_epochs = raw_epochs.copy().pick([channel_name])
        if APPLY_DISPLAY_FILTER:
            raw_display_epochs.filter(
                l_freq=DISPLAY_FILTER_HZ[0],
                h_freq=DISPLAY_FILTER_HZ[1],
                method="iir",
                iir_params=DISPLAY_FILTER_IIR_PARAMS,
                phase=DISPLAY_FILTER_PHASE,
                verbose=False,
            )
        raw_data_uv = raw_display_epochs.get_data()[:, 0, :] * 1e6
        if CENTER_EACH_EPOCH_FOR_DISPLAY:
            raw_center_uv = np.median(raw_data_uv[:, center_mask], axis=1, keepdims=True)
            raw_data_uv = raw_data_uv - raw_center_uv
        axis = axes_flat[panel_index]
        for trace_uv in raw_data_uv[:, display_mask]:
            axis.plot(time_display_s, trace_uv, color=COLOR_RAW, alpha=0.45, linewidth=0.7)
        axis.set_title(f"{INTENSITY_PCT}% {channel_name} raw epochs (n={len(raw_epochs)})")
        panel_index += 1

    axis = axes_flat[panel_index]
    for trace_uv in clean_plot_uv[:, channel_index, :][:, display_mask]:
        axis.plot(time_display_s, trace_uv, color=COLOR_CLEAN, alpha=0.55, linewidth=0.8)
    axis.set_title(f"{INTENSITY_PCT}% {channel_name} artremoved epochs (n={len(clean_epochs)})")
    panel_index += 1

for axis in axes_flat:
    axis.axvspan(*ARTIFACT_CUT_WINDOW_S, color=COLOR_CUT, alpha=0.35, label="interpolated window")
    axis.axvline(0.0, color=COLOR_PULSE, linestyle="--", linewidth=1.0, label="pulse")
    axis.set_xlim(DISPLAY_WINDOW_S)
    axis.set_ylabel("uV")
    axis.grid(True, alpha=0.2)
    if Y_LIMIT_UV is not None:
        axis.set_ylim(Y_LIMIT_UV)

axes_flat[0].legend(frameon=False, loc="upper right")
axes_flat[-1].set_xlabel("Time from pulse (s)")
filter_title = "display-filtered" if APPLY_DISPLAY_FILTER else "unfiltered"
fig.suptitle(
    f"EXP08 run01 artremoved epoch QC - individual {filter_title} traces, no average",
    fontsize=12,
    fontweight="bold",
)
fig.tight_layout()
plt.show()
