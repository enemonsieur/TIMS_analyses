"""Extract per-intensity triplet epoch files from EXP08 run02 (triplet dose-response).

PIPELINE:
  VHDR recording (31 EEG + stim + GT, 1000 Hz, ~1010 s)
  ├─ Detect: triplet onsets via Hilbert envelope + cluster (gap > 100 ms)
  │   Each triplet = 3 half-sine pulses at 0/20/40 ms; inter-triplet interval = 5 s
  ├─ Validate: exactly 200 triplet onsets (20 per intensity × 10 levels)
  ├─ Group: sequential 20-triplet blocks → 10%, 20%, …, 100%
  ├─ Build: ON (-0.6 to +0.7 s) and late-OFF (2.5 to 4.2 s) epochs per intensity
  └─ Save: exp08t_{epochs,gt_epochs,stim_epochs}_{pct}pct_{on,lateoff}-epo.fif
"""

from pathlib import Path
import warnings

import mne
import numpy as np
from scipy.signal import hilbert

import preprocessing


# ============================================================
# CONFIG
# ============================================================

DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
VHDR_PATH = DATA_DIR / "exp08-STIM-triplet_run02_10-100.vhdr"
OUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
TRIPLETS_PER_INTENSITY = 20
INTER_TRIPLET_INTERVAL_S = 5.0

# Epoch windows (no filter applied here — that happens downstream per window)
ON_WINDOW_S      = (-0.6, 0.7)   # covers 600 ms pre + triplet (0–40 ms) + 660 ms response
LATE_OFF_WINDOW_S = (2.5, 4.2)   # quiet period: 2.5–4.2 s post-triplet, noise reference for SASS/SSD

# Triplet onset detection
STIM_THRESHOLD_FRACTION = 0.08   # fraction of max stim amplitude; detects even 10% intensity
MIN_INTER_TRIPLET_S      = 0.100 # 100 ms >> intra-triplet pulse gap (20 ms); collapses triplet into one onset

EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# VHDR (31 EEG + stim + GT, 1000 Hz)
# ├─ stim trace → Hilbert envelope → rising edges → cluster (gap > 100 ms)
# │   → first crossing per triplet = triplet onset
# │   → validate: 200 onsets (20 × 10 intensities)
# ├─ Group onsets sequentially into 10 intensity blocks
# └─ Per intensity: build ON + late-OFF epochs for EEG, GT, stim
#    → 60 .fif files (3 types × 2 windows × 10 intensities)


# ============================================================
# 1) LOAD & PREPARE DATA
# ============================================================

# ══ 1.1 Read BrainVision file, suppress metadata warnings ══
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc*")
    raw = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw.info["sfreq"])
print(f"Loaded: {raw.n_times / sfreq:.1f} s, {sfreq:.0f} Hz, {len(raw.ch_names)} channels")

if "stim" not in raw.ch_names:
    raise RuntimeError("Missing required channel: stim")

# ══ 1.2 Extract component traces ══
stim_trace = raw.copy().pick(["stim"]).get_data()[0]
# → (n_samples,) stim voltage in volts

raw_eeg = raw.copy().drop_channels([
    ch for ch in raw.ch_names
    if ch.lower() in {"stim", "ground_truth"} or ch.startswith("STI") or ch in EXCLUDED_CHANNELS
])
gt_raw   = raw.copy().pick(["ground_truth"])
stim_raw = raw.copy().pick(["stim"])
print(f"EEG channels retained: {len(raw_eeg.ch_names)}")


# ============================================================
# 2) DETECT TRIPLET ONSETS
# ============================================================

# ══ 2.1 Hilbert envelope → rising-edge threshold crossings ══
envelope = np.abs(hilbert(stim_trace))
threshold = np.max(envelope) * STIM_THRESHOLD_FRACTION
crossings = np.where(np.diff((envelope > threshold).astype(int)) == 1)[0]
# → all rising edges, including 3 per triplet (pulses at 0, 20, 40 ms)

# ══ 2.2 Cluster: keep only the first crossing per triplet ══
# Pulses within a triplet are 20 ms apart; inter-triplet gap is 5000 ms.
# Any crossing within MIN_INTER_TRIPLET_S of the previous kept crossing is suppressed.
min_gap_samples = int(MIN_INTER_TRIPLET_S * sfreq)  # → 100 samples
triplet_onsets = []
prev = -min_gap_samples
for c in crossings:
    if c - prev >= min_gap_samples:
        triplet_onsets.append(c)
        prev = c
triplet_onsets = np.array(triplet_onsets, dtype=int)

# ══ 2.3 Validate count ══
expected = len(INTENSITY_LEVELS) * TRIPLETS_PER_INTENSITY
if len(triplet_onsets) < expected:
    raise RuntimeError(
        f"Expected {expected} triplet onsets, found only {len(triplet_onsets)}. "
        "Try lowering STIM_THRESHOLD_FRACTION."
    )
triplet_onsets = triplet_onsets[:expected]
print(f"Detected: {len(triplet_onsets)} triplet onsets (first at {triplet_onsets[0]/sfreq:.2f} s)")


# ============================================================
# 3) GROUP ONSETS INTO INTENSITY BLOCKS
# ============================================================

# Sequential 20-triplet blocks: indices 0–19 → 10%, 20–39 → 20%, …, 180–199 → 100%
intensity_onset_map = {}
for i, level in enumerate(INTENSITY_LEVELS):
    pct = int(level * 100)
    block = triplet_onsets[i * TRIPLETS_PER_INTENSITY:(i + 1) * TRIPLETS_PER_INTENSITY]
    intensity_onset_map[pct] = block
    print(f"  {pct}%: {len(block)} triplets, first at {block[0]/sfreq:.2f} s")


# ============================================================
# 4) BUILD AND SAVE EPOCHS PER INTENSITY
# ============================================================

on_pre_samples      = int(round(-ON_WINDOW_S[0] * sfreq))
on_post_samples     = int(round(ON_WINDOW_S[1] * sfreq))
lateoff_post_samples = int(round(LATE_OFF_WINDOW_S[1] * sfreq))

summary_rows = []
for level in INTENSITY_LEVELS:
    pct = int(level * 100)
    onsets = intensity_onset_map[pct]

    # ══ 4.1 Reject epochs where either window falls outside recording bounds ══
    on_ok     = (onsets >= on_pre_samples) & (onsets + on_post_samples <= raw.n_times)
    lateoff_ok = onsets + lateoff_post_samples <= raw.n_times
    valid = onsets[on_ok & lateoff_ok]

    if len(valid) == 0:
        raise RuntimeError(f"No valid epochs for {pct}%.")

    events   = preprocessing.build_event_array(valid)
    ev_dict  = {f"intensity_{pct}pct": 1}

    # ══ 4.2 Save ON + late-OFF epochs for EEG, GT, and stim traces ══
    for raw_src, prefix in [
        (raw_eeg,  "exp08t_epochs"),
        (gt_raw,   "exp08t_gt_epochs"),
        (stim_raw, "exp08t_stim_epochs"),
    ]:
        ep_on = mne.Epochs(raw_src, events, ev_dict,
                           tmin=ON_WINDOW_S[0], tmax=ON_WINDOW_S[1],
                           baseline=None, preload=True, verbose=False)
        ep_off = mne.Epochs(raw_src, events, ev_dict,
                            tmin=LATE_OFF_WINDOW_S[0], tmax=LATE_OFF_WINDOW_S[1],
                            baseline=None, preload=True, verbose=False)
        ep_on.save(OUT_DIR  / f"{prefix}_{pct}pct_on-epo.fif",      overwrite=True)
        ep_off.save(OUT_DIR / f"{prefix}_{pct}pct_lateoff-epo.fif", overwrite=True)

    summary_rows.append({"pct": pct, "n": len(valid)})
    print(f"  {pct}%: {len(valid)} triplet epochs -> ON + late-OFF x (EEG, GT, stim) saved")


# ============================================================
# 5) SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("EXP08 TRIPLET EPOCH EXTRACTION COMPLETE")
print("=" * 70)
total = sum(r["n"] for r in summary_rows)
n_files = 3 * 2 * len(INTENSITY_LEVELS)  # 3 types × 2 windows × 10 intensities
print(f"Total valid epochs: {total}  |  Files created: {n_files}  |  Prefix: exp08t_")
print(f"Output directory:   {OUT_DIR}")
