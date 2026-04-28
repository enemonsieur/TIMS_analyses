"""Identify channels with extreme values after decay removal; flag for exclusion from TEP averaging."""

from pathlib import Path
import numpy as np
import mne
import preprocessing

# ============================================================
# CONFIG
# ============================================================
FIF_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
INTENSITIES = [10, 20, 30, 40, 50, 100]
DECAY_FIT_START_S = 0.020
OUTLIER_THRESHOLD_V = 0.01  # for decay fitting
LOWPASS_HZ = 42.0
POST_WINDOW_S = (0.020, 0.5)
AMPLITUDE_LIMIT_UV = 8.0  # flag channels exceeding ±8 µV


# ============================================================
# 1) LOAD & PROCESS PER INTENSITY
# ============================================================
print("=" * 70)
print("EXP08 TEP CHANNEL QC")
print("=" * 70)

bad_channels_per_intensity = {}
all_bad_channels = set()

for pct in INTENSITIES:
    fif_path = FIF_DIR / f"exp08_epochs_{pct}pct_on-epo.fif"
    epochs = mne.read_epochs(str(fif_path), preload=True, verbose=False)

    # Apply decay removal
    epochs = preprocessing.subtract_exponential_decay(
        epochs,
        fit_start_s=DECAY_FIT_START_S,
        outlier_threshold_v=OUTLIER_THRESHOLD_V,
    )

    # Filter
    epochs.filter(l_freq=None, h_freq=LOWPASS_HZ, verbose=False)

    # Extract POST window
    epochs_post = epochs.copy().crop(*POST_WINDOW_S)
    evoked_post = epochs_post.average()

    # Find channels with extreme values
    bad_here = []
    print(f"\n{pct}% intensity:")
    for ch_idx, ch_name in enumerate(evoked_post.ch_names):
        ch_data = evoked_post.data[ch_idx]
        ch_min_uv = ch_data.min() * 1e6
        ch_max_uv = ch_data.max() * 1e6
        ch_range = ch_max_uv - ch_min_uv

        if np.abs(ch_min_uv) > AMPLITUDE_LIMIT_UV or np.abs(ch_max_uv) > AMPLITUDE_LIMIT_UV:
            bad_here.append(ch_name)
            all_bad_channels.add(ch_name)
            print(f"  BAD {ch_name:>3s}  min={ch_min_uv:7.2f} uV  max={ch_max_uv:7.2f} uV  range={ch_range:7.2f} uV")

    if not bad_here:
        print(f"  OK - All channels within ±{AMPLITUDE_LIMIT_UV} uV")

    bad_channels_per_intensity[pct] = bad_here

# ============================================================
# 2) SUMMARY & HARDCODED LIST
# ============================================================
print(f"\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

for pct in INTENSITIES:
    bad = bad_channels_per_intensity[pct]
    print(f"{pct}%: {len(bad)} bad channels  {bad if bad else '(none)'}")

print(f"\nChannels to DROP across all intensities: {sorted(all_bad_channels)}")
print(f"\nHardcode in explore_exp08_tep.py:")
print(f"BAD_CHANNELS = {sorted(list(all_bad_channels))}")
