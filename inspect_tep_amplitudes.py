"""Inspect min/max amplitudes in 10-20% vs 30%+ to diagnose file size explosion."""

from pathlib import Path
import numpy as np
import mne
import preprocessing

# ============================================================
# CONFIG
# ============================================================
FIF_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
BAD_CHANNELS = ['F7', 'FT9', 'FC5', 'FC1', 'C3', 'T7', 'Pz', 'O1', 'O2', 'CP6', 'T8', 'FT10', 'FC2']
INTENSITIES = [10, 20, 30, 40, 50, 100]
DECAY_FIT_START_S = 0.020
OUTLIER_THRESHOLD_V = 0.01
LOWPASS_HZ = 42.0
PRE_WINDOW_S = (-0.8, -0.3)
POST_WINDOW_S = (0.020, 0.5)


# ============================================================
# LOAD & INSPECT PER INTENSITY
# ============================================================
print("=" * 80)
print("TEP AMPLITUDE ANALYSIS (after bad channel removal)")
print("=" * 80)

results = {}

for pct in INTENSITIES:
    fif_path = FIF_DIR / f"exp08_epochs_{pct}pct_on-epo.fif"
    epochs = mne.read_epochs(str(fif_path), preload=True, verbose=False)
    epochs.drop_channels(BAD_CHANNELS, on_missing="ignore")

    # Apply decay removal
    epochs = preprocessing.subtract_exponential_decay(
        epochs,
        fit_start_s=DECAY_FIT_START_S,
        outlier_threshold_v=OUTLIER_THRESHOLD_V,
    )

    # Filter
    epochs.filter(l_freq=None, h_freq=LOWPASS_HZ, verbose=False)

    # Get PRE and POST evoked
    epochs_pre = epochs.copy().crop(*PRE_WINDOW_S)
    epochs_post = epochs.copy().crop(*POST_WINDOW_S)
    evoked_pre = epochs_pre.average()
    evoked_post = epochs_post.average()

    # Get global min/max across all channels
    pre_data_uv = evoked_pre.data * 1e6
    post_data_uv = evoked_post.data * 1e6

    pre_min = pre_data_uv.min()
    pre_max = pre_data_uv.max()
    pre_range = pre_max - pre_min

    post_min = post_data_uv.min()
    post_max = post_data_uv.max()
    post_range = post_max - post_min

    # Compute global field power for each
    pre_gfp = np.sqrt(np.mean(pre_data_uv ** 2, axis=0))
    post_gfp = np.sqrt(np.mean(post_data_uv ** 2, axis=0))

    pre_gfp_min = pre_gfp.min()
    pre_gfp_max = pre_gfp.max()
    post_gfp_min = post_gfp.min()
    post_gfp_max = post_gfp.max()

    results[pct] = {
        'pre_min': pre_min,
        'pre_max': pre_max,
        'pre_range': pre_range,
        'post_min': post_min,
        'post_max': post_max,
        'post_range': post_range,
        'pre_gfp_max': pre_gfp_max,
        'post_gfp_max': post_gfp_max,
    }

    print(f"\n{pct}% INTENSITY:")
    print(f"  PRE window:")
    print(f"    min={pre_min:8.2f} µV  max={pre_max:8.2f} µV  range={pre_range:8.2f} µV")
    print(f"    GFP max: {pre_gfp_max:6.2f} µV")
    print(f"  POST window:")
    print(f"    min={post_min:8.2f} µV  max={post_max:8.2f} µV  range={post_range:8.2f} µV")
    print(f"    GFP max: {post_gfp_max:6.2f} µV")

# ============================================================
# COMPARE 10% vs 20% vs 30%+
# ============================================================
print(f"\n" + "=" * 80)
print("COMPARISON: 10-20% (workable) vs 30%+ (large files)")
print("=" * 80)

for window_name in ['PRE', 'POST']:
    print(f"\n{window_name} WINDOW:")
    for pct in INTENSITIES:
        r = results[pct]
        if window_name == 'PRE':
            range_uv = r['pre_range']
            gfp_max = r['pre_gfp_max']
        else:
            range_uv = r['post_range']
            gfp_max = r['post_gfp_max']

        status = "OK" if pct <= 20 else "LARGE"
        print(f"  {pct:3d}% : range={range_uv:7.2f} µV  GFP_max={gfp_max:6.2f} µV  [{status}]")
