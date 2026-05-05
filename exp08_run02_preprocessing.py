"""Remove EXP08 run02 triplet artifacts; save 4 pre-filtered epoch FIF files (all intensities, event_id 1–10)."""

import os
os.environ["QT_API"] = "pyqt6"
os.environ["MPLBACKEND"] = "qtagg"

from pathlib import Path
import warnings

import mne
import numpy as np
from scipy.signal import find_peaks
import preprocessing

# ============================================================
# CONFIG
# ============================================================

DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
VHDR     = DATA_DIR / "exp08-STIM-triplet_run02_10-100.vhdr"
OUT_DIR  = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDED      = {"TP9", "Fp1", "TP10", "F7"}
ON_TMIN       = -1.0    # s pre-pulse
ON_TMAX       =  2.0    # s post-pulse
LOFF_TMIN     =  2.0    # s post-pulse (late-OFF rest window start)
LOFF_TMAX     =  4.0    # s post-pulse (late-OFF rest window end)

INTENSITIES   = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # % MSO blocks
N_PULSES      = 20      # fixed pulses per intensity block
FIRST_PULSE   = 31670   # run02 first triplet onset (31.67 s × 1000 Hz); others follow 5-s IPI


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Run02 raw VHDR (EEG + GT + STIM, 1000 Hz, ~1046 s)
# ├─ Load: drop EXCLUDED + STI hardware channels; retain GT + STIM
# ├─ Schedule: 200-triplet fixed-interval; event_id 1–10 per intensity block
# ├─ Clean: per-triplet × per-EEG-channel find_peaks dual-threshold removal
# │         initial spike 0–70 ms (covers 3 pulses); search 70–250 ms
# ├─ Filter: raw_clean (1 Hz HP) → raw_signal (12–14 Hz) + raw_noise (4–20 Hz)
# └─ Save: 4 epoch FIF files (on_artremoved / on_signal / on_noise / lateoff_noise)


# ════════════════════════════════════════════════════════════════════════════
# 1) LOAD
# ════════════════════════════════════════════════════════════════════════════

# ══ 1.1 Read raw recording ══
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    raw = mne.io.read_raw_brainvision(str(VHDR), preload=True, verbose=False)
# → MNE Raw: (EEG + GT + STIM + STI trigger) @ 1000 Hz

sfreq = float(raw.info["sfreq"])
raw.drop_channels([ch for ch in raw.ch_names if ch in EXCLUDED or ch.startswith("STI")])
eeg_idx = [i for i, ch in enumerate(raw.ch_names) if ch not in {"stim", "ground_truth"}]
# → eeg_idx: EEG-only channel indices; GT + STIM retained and untouched by artifact removal

# ══ 1.2 Build fixed-interval pulse schedule ══
pulse_samples = FIRST_PULSE + np.arange(N_PULSES * len(INTENSITIES)) * int(round(5.0 * sfreq))
# → (200,) sample indices, 20 triplets × 10 intensity blocks; We just reconstruct the pulse timings

print(f"Loaded: {raw.n_times / sfreq:.1f} s, {len(raw.ch_names)} channels ({len(eeg_idx)} EEG + GT + STIM), {pulse_samples.size} triplets")


# ════════════════════════════════════════════════════════════════════════════
# 2) ARTIFACT REMOVAL + FILTER COPIES
# ════════════════════════════════════════════════════════════════════════════

# ══ 2.1 Remove triplet artifacts (EEG channels only) ══
# Per triplet × EEG channel: baseline from −100 to −10 ms → threshold = max(5×SD, 2%×spike peak)
# → initial spike 0–70 ms covers all 3 triplet pulses (at 0 / 20 / 40 ms)
# → find last oscillation peak above threshold in 70–250 ms → replace −25 ms → peak with linear interp.
def ms(x): return int(round(x / 1000.0 * sfreq))

clean_data   = raw.get_data().copy()                                      # (n_ch, n_samples) Volts; GT+STIM included but not modified
durations_ms = np.zeros((pulse_samples.size, len(eeg_idx)), dtype=float) # (200, n_eeg) ms from pulse onset

for p_idx, pulse in enumerate(pulse_samples.astype(int)):
    if p_idx % 20 == 0:
        print(f"Processing triplet {p_idx+1}/{pulse_samples.size} at sample {pulse} ({pulse/sfreq:.1f} s)...")
    
    eeg_sig  = clean_data[eeg_idx, :]
    bl       = eeg_sig[:, pulse + ms(-100) : pulse + ms(-10)]             # (n_eeg, ~90) pre-pulse baseline
    bl_mean  = bl.mean(axis=1)                                            # (n_eeg,)
    bl_std   = bl.std(axis=1)                                             # (n_eeg,) noise floor
    first70  = np.abs(eeg_sig[:, pulse : pulse + ms(70)] - bl_mean[:, None])             # (n_eeg, 70) all 3 triplet pulses
    search   = np.abs(eeg_sig[:, pulse + ms(70) : pulse + ms(250)] - bl_mean[:, None])   # (n_eeg, ~180) post-triplet tail
    art_start = pulse + ms(-25)

    for k, ch in enumerate(eeg_idx):
        threshold_k = np.maximum(4.0 * bl_std[k], 0.02 * search[k].max())
        peaks, _ = find_peaks(search[k], height=threshold_k)
        art_end = pulse + ms(70) + peaks[-1] if len(peaks) else pulse + ms(70)
        idx = np.arange(art_start, art_end)

        if idx.size:
            clean_data[ch, idx] = np.linspace(clean_data[ch, art_start], clean_data[ch, art_end], idx.size, endpoint=False)
        durations_ms[p_idx, k] = (art_end - pulse) * 1000.0 / sfreq
# → clean_data: EEG artifact windows replaced by linear interpolation; GT + STIM channels unchanged

# ══ 2.2 Three filtered copies ══
raw_clean  = raw.copy()
raw_clean._data[:] = clean_data
raw_clean.filter(1.0, None, verbose=False)                                # 1 Hz HP: removes slow drift + DC
raw_signal = raw_clean.copy().filter(12.0, 14.0, verbose=False)          # SSD signal-band numerator covariance
raw_noise  = raw_clean.copy().filter(4.0,  20.0, verbose=False)          # SSD denominator + SASS ON/lateOFF covariance
# → raw_signal and raw_noise span the same epochs; filters applied to all channels including GT + STIM

import matplotlib.pyplot as plt
# let's make a simple Before After plot of the entire composition at Oz to sanity check the artifact removal across all pulses (worst case: last pulse with 19 prior triplets)
plt.figure(figsize=(14, 5))
plt.plot(raw.times, raw.get_data()[raw.ch_names.index("Oz"), :] * 1e6, label="Raw Oz", alpha=0.7)
plt.plot(raw.times, clean_data[raw.ch_names.index("Oz"), :] * 1e6, label="Cleaned (70ms window)", linewidth=2)
plt.xlabel("Time (s)")
plt.ylabel("Amplitude (µV)")
plt.title("EXP08 Run02: Artifact Removal Across ALL Pulses (Oz channel)")
plt.legend(frameon=False)
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# ════════════════════════════════════════════════════════════════════════════
# 3) EPOCH + SAVE
# ════════════════════════════════════════════════════════════════════════════

# ══ 3.1 Unified events array: event_id 1–10 encodes intensity 10–100% ══
event_id_map = {f"intensity_{pct}pct": i + 1 for i, pct in enumerate(INTENSITIES)}
events = np.column_stack([
    pulse_samples.astype(int),
    np.zeros(pulse_samples.size, dtype=int),
    np.repeat(np.arange(1, 11), N_PULSES),   # event_id 1–10 per block of 20 triplets
])
# → events: (200, 3) MNE-style array; intensity index in column 2

kw = dict(baseline=None, preload=True, verbose=False)  # shared epoch kwargs

# ══ 3.2 Save 4 epoch files ══
mne.Epochs(raw_clean,  events, event_id_map, ON_TMIN,   ON_TMAX,   **kw).save(OUT_DIR / "exp08_run02_all_on_artremoved-epo.fif",  overwrite=True, verbose=False)
mne.Epochs(raw_signal, events, event_id_map, ON_TMIN,   ON_TMAX,   **kw).save(OUT_DIR / "exp08_run02_all_on_signal-epo.fif",      overwrite=True, verbose=False)
mne.Epochs(raw_noise,  events, event_id_map, ON_TMIN,   ON_TMAX,   **kw).save(OUT_DIR / "exp08_run02_all_on_noise-epo.fif",       overwrite=True, verbose=False)
mne.Epochs(raw_noise,  events, event_id_map, LOFF_TMIN, LOFF_TMAX, **kw).save(OUT_DIR / "exp08_run02_all_lateoff_noise-epo.fif",  overwrite=True, verbose=False)
# → 4 FIF files; all channels (EEG + GT + STIM); event_id 1–10 per intensity

print("Saved 4 epoch files.")


# ════════════════════════════════════════════════════════════════════════════
# 4) TEXT SUMMARY
# ════════════════════════════════════════════════════════════════════════════

summary_lines = [
    "EXP08 RUN02 TRIPLET ARTIFACT REMOVAL SUMMARY",
    "=" * 72,
    f"Source: {VHDR.name}",
    f"Sampling rate: {sfreq:.0f} Hz",
    f"EEG channels: {len(eeg_idx)} (excluded: {sorted(EXCLUDED)})",
    f"GT + STIM retained in all epoch files",
    f"Pulse count: {pulse_samples.size} (10 intensities × 20 triplets)",
    f"First triplet sample: {FIRST_PULSE}",
    "",
    "Algorithm: find_peaks dual-threshold + linear interpolation (triplet-aware)",
    "  Baseline window:       −100 to −10 ms",
    "  Artifact start:        −25 ms",
    "  Initial spike window:  0–70 ms  (covers all 3 pulses at 0 / 20 / 40 ms)",
    "  Search window:         70–250 ms",
    "  Threshold:             max(5× baseline SD, 2%× first-70ms peak)",
    "",
    "Artifact end statistics by intensity (ms from triplet onset):",
    f"{'Intensity':>10}  {'Mean':>8}  {'Std':>6}  {'Min':>6}  {'Max':>6}",
]
for i, pct in enumerate(INTENSITIES):
    d = durations_ms[i * N_PULSES : (i + 1) * N_PULSES]
    summary_lines.append(f"{pct:>9}%  {d.mean():>8.1f}  {d.std():>6.1f}  {d.min():>6.0f}  {d.max():>6.0f}")
summary_lines += [
    "",
    "Outputs:",
    "  exp08_run02_all_on_artremoved-epo.fif   (1 Hz HP, all 200 triplets)",
    "  exp08_run02_all_on_signal-epo.fif       (12–14 Hz, all 200 triplets)",
    "  exp08_run02_all_on_noise-epo.fif        (4–20 Hz,  all 200 triplets)",
    "  exp08_run02_all_lateoff_noise-epo.fif   (4–20 Hz,  +2 to +4 s lateOFF)",
]

(OUT_DIR / "exp08_run02_triplet_artifact_summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print("Saved: exp08_run02_triplet_artifact_summary.txt")
