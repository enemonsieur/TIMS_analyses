"""How do the exported clean Exp04 pre/post pulse windows look as separate animations without showing the stimulation gap?"""

from pathlib import Path
import shutil

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, PillowWriter, writers
import mne
import numpy as np


# ============================================================
# CONFIG
# ============================================================
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP04_TEP_analysis\exp04_topo_video")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

PROCESSED_EVOKEDS_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_pre_post-ave.fif"
PRE_VIDEO_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_pre.mp4"
POST_VIDEO_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_post.mp4"
PRE_GIF_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_pre.gif"
POST_GIF_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_post.gif"
TOPOMAP_STRIP_PATH = OUTPUT_DIRECTORY / "exp04_topo_video_topomap_strip.png"

EXPECTED_SEGMENTS = ("pre", "post")
DURATION_S = 8.0
N_FRAMES_PER_SEGMENT = 8
FRAME_RATE_FPS = int(round(N_FRAMES_PER_SEGMENT / DURATION_S))
N_STRIP_FRAMES = 8
DISPLAY_YLIM_UV = 6.0
DISPLAY_VMIN_UV = -6.0
DISPLAY_VMAX_UV = 6.0


# ============================================================
# PIPELINE SKETCH
# ============================================================
# saved pre/post evokeds
#   -> load the processed data exported by export_exp04_topo_video_data.py
#   -> validate that both segments share channels and sampling rate
#   -> choose valid frame times inside each clean segment
#   -> animate pre and post separately
#   -> save two MP4 or GIF outputs without showing the stimulation gap


# ============================================================
# 1) LOAD THE SAVED PRE/POST EPOCHED DATA
# ============================================================
if not PROCESSED_EVOKEDS_PATH.exists():
    raise FileNotFoundError(
        f"Missing processed evokeds: {PROCESSED_EVOKEDS_PATH}. "
        "Run export_exp04_topo_video_data.py first."
    )

saved_evokeds = mne.read_evokeds(str(PROCESSED_EVOKEDS_PATH), condition=None, verbose=False)
evokeds_by_comment = {str(evoked.comment).lower(): evoked for evoked in saved_evokeds}
missing_segments = [segment for segment in EXPECTED_SEGMENTS if segment not in evokeds_by_comment]
if missing_segments:
    raise ValueError(f"Saved evokeds are missing required segments: {missing_segments}")

evoked_pre = evokeds_by_comment["pre"]
evoked_post = evokeds_by_comment["post"]

if evoked_pre.ch_names != evoked_post.ch_names:
    raise ValueError("Saved pre/post evokeds do not share the same channel order.")
if not np.isclose(float(evoked_pre.info["sfreq"]), float(evoked_post.info["sfreq"])):
    raise ValueError("Saved pre/post evokeds do not share the same sampling rate.")
if evoked_pre.data.shape[0] < 2:
    raise ValueError("Need at least two EEG channels to animate topomaps.")

# ============================================================
# 2) CHOOSE VALID FRAME TIMES INSIDE EACH CLEAN SEGMENT
# ============================================================
pre_frame_times_s = np.linspace(float(evoked_pre.times[0]), float(evoked_pre.times[-1]), N_FRAMES_PER_SEGMENT)
post_frame_times_s = np.linspace(float(evoked_post.times[0]), float(evoked_post.times[-1]), N_FRAMES_PER_SEGMENT)

strip_pre_indices = np.linspace(0, pre_frame_times_s.size - 1, N_STRIP_FRAMES // 2, dtype=int)
strip_post_indices = np.linspace(0, post_frame_times_s.size - 1, N_STRIP_FRAMES // 2, dtype=int)
strip_pre_times_s = pre_frame_times_s[strip_pre_indices]
strip_post_times_s = post_frame_times_s[strip_post_indices]


# ============================================================
# 3) SAVE A STATIC TOPOGRAPHY STRIP
# ============================================================
fig, axes = plt.subplots(2, N_STRIP_FRAMES // 2, figsize=(12, 6))
for row_index, (segment_name, evoked, strip_times) in enumerate(
    (("pre", evoked_pre, strip_pre_times_s), ("post", evoked_post, strip_post_times_s))
):
    evoked.plot_topomap(
        times=strip_times,
        ch_type="eeg",
        time_unit="s",
        outlines="head",
        colorbar=False,
        vlim=(DISPLAY_VMIN_UV, DISPLAY_VMAX_UV),
        axes=axes[row_index].tolist(),
        show=False,
    )
    axes[row_index, 0].text(
        -0.20,
        0.50,
        segment_name.upper(),
        transform=axes[row_index, 0].transAxes,
        ha="right",
        va="center",
        fontsize=11,
        fontweight="bold",
    )

fig.suptitle("EXP04 clean pre/post pulse-window topography")
fig.tight_layout()
fig.savefig(TOPOMAP_STRIP_PATH, dpi=220, bbox_inches="tight")
plt.close(fig)


# ============================================================
# 4) BUILD AND SAVE THE SEPARATE VIDEOS
# ============================================================
if writers.is_available("ffmpeg"):
    ffmpeg_path = shutil.which("ffmpeg")
    writer_name = "ffmpeg"
elif writers.is_available("pillow"):
    ffmpeg_path = None
    writer_name = "pillow"
else:
    raise RuntimeError(
        "No supported animation writer is available. Install ffmpeg for MP4 output "
        "or Pillow support for GIF output."
    )

saved_outputs = []
for segment_name, evoked, frame_times_s, video_path, gif_path in (
    ("pre", evoked_pre, pre_frame_times_s, PRE_VIDEO_PATH, PRE_GIF_PATH),
    ("post", evoked_post, post_frame_times_s, POST_VIDEO_PATH, POST_GIF_PATH),
):
    figure, animation = evoked.animate_topomap(
        ch_type="eeg",
        times=frame_times_s,
        frame_rate=FRAME_RATE_FPS,
        butterfly=True,
        blit=False,
        show=False,
        time_unit="s",
        vmin=DISPLAY_VMIN_UV,
        vmax=DISPLAY_VMAX_UV,
    )
    figure.suptitle(f"EXP04 {segment_name} pulse-locked topography and time course")
    if len(figure.axes) >= 2:
        figure.axes[1].set_ylim(-DISPLAY_YLIM_UV, DISPLAY_YLIM_UV)

    if writer_name == "ffmpeg":
        writer = FFMpegWriter(
            fps=FRAME_RATE_FPS,
            codec="libx264",
            bitrate=1800,
            metadata={"title": f"EXP04 topo video {segment_name}"},
        )
        output_path = video_path
    else:
        writer = PillowWriter(fps=FRAME_RATE_FPS)
        output_path = gif_path

    animation.save(str(output_path), writer=writer, dpi=160)
    plt.close(figure)
    saved_outputs.append((segment_name, output_path))


# ============================================================
# 5) SUMMARY
# ============================================================
print(f"Loaded segments: {sorted(evokeds_by_comment)}")
print(f"Retained EEG channels: {len(evoked_pre.ch_names)}")
print(f"Export source: C:\\Users\\njeuk\\OneDrive\\Documents\\Charite Berlin\\TIMS\\TIMS_data_sync\\pilot\\doseresp\\exp04-sub01-stim-mod-50hz-pulse-run01.vhdr")
print(f"Pre window in source time: {evoked_pre.times[0]:.3f} to {evoked_pre.times[-1]:.3f} s")
print(f"Post window in source time: {evoked_post.times[0]:.3f} to {evoked_post.times[-1]:.3f} s")
print(f"Frames per segment: {N_FRAMES_PER_SEGMENT}")
print(f"Display ylim: +/-{DISPLAY_YLIM_UV:.1f} uV")
print(f"Topomap color limits: {DISPLAY_VMIN_UV:.1f} to {DISPLAY_VMAX_UV:.1f} uV")
print(f"Saved topomap strip -> {TOPOMAP_STRIP_PATH}")
for segment_name, output_path in saved_outputs:
    print(f"Saved {segment_name} animation -> {output_path}")
print(f"Writer: {writer_name}")
print(f"ffmpeg: {ffmpeg_path}")
