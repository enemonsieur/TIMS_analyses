# Lab Book: exp07 -- iTBS Dose-Response Artifact Characterization (10–100%)

**Subject:** Phantom
**Goal:** Characterize how EEG artifact amplitude scales with stimulation intensity across 10 amplitude levels (10%–100%), using pure amplitude modulation iTBS.

---

## Stimulation Protocol

**Protocol script:** `itbs_10-100_pct_ampmod.py`
**Protocol file:** `itbs_10-100_pct_ampmod_1s.tims`

| Parameter | Value |
|-----------|-------|
| Amplitude encoding | Pure amplitude modulation (no modulation signal variation) |
| Amplitude levels | 10%, 20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%, 100% (10 blocks) |
| Burst rate | 5 Hz |
| Triplet rate | 50 Hz (3 pulses per burst at 0, 20, 40 ms) |
| ON duration | 2 s |
| OFF duration | 4 s |
| Cycle duration | 6 s (2 s ON + 4 s OFF) |
| Cycles per block | 20 |
| Block duration | 120 s (20 cycles × 6 s) |
| Total session | 1200 s (10 blocks × 120 s) |
| Pulses per block | 600 (20 cycles × 10 bursts × 3 pulses) |
| Pulse width | 5 ms square events in amplitude signal |

The dose-response is encoded entirely by scaling the amplitude signal. The modulation signal is constant at 1.0. Protocol-level stimulator intensity is fixed at 1.0.

---

## Recordings

| File | Condition | Duration |
|------|-----------|----------|
| `exp07-baseline-gt_13hz.vhdr` | Baseline resting state with 13 Hz GT | — |
| `exp07-STIM-iTBS_run01.vhdr` | iTBS dose-response (run 1) | — |
| `exp07-STIM-iTBS_run02_mod100pct.vhdr` | iTBS dose-response (run 2, 100% modulation) | 1238.2 s |

Run02 is the primary analysis target.

---

## Recording Metadata (run02)

| Field | Value |
|-------|-------|
| Format | BrainVision float32, multiplexed |
| Sampling rate | 1000 Hz |
| EEG channels | 31 |
| Reference channel for onset detection | CP2 (lowest linear drift across session) |
| Online filters | software highpass + notch |

---

## Epoch Structure (run02)

Epochs were created by `explore_exp07_make_epochs.py`:

| Parameter | Value |
|-----------|-------|
| First ON onset | ~11.32 s (detected via Hilbert envelope on CP2) |
| Cycle | 6000 samples (2000 ON + 4000 OFF @ 1000 Hz) |
| Total ON blocks detected | 204 (200 expected from 10 × 20; 4 extra at tail) |
| Epoch window | tmin=0, tmax=2.0 s (ON window only; OFF not saved) |
| Epoch shape | (204, 31, 2001) |
| Output file | `EXP07/exp07_epochs-epo.fif` |

### Splitting epochs by intensity

Blocks are ordered sequentially: intensity 1 (10%) → intensity 10 (100%).

```
epochs[0:20]    → 10%
epochs[20:40]   → 20%
...
epochs[180:200] → 100%
epochs[200:204] → tail (discard)
```

---

## Analysis Scripts

- `explore_exp07_make_epochs.py` — pulse detection, ON/OFF windowing, epoch creation
- `explore_exp07_artifacts_chx.py` — ON-state artifact visualization per intensity on CP2

## Key Finding (preliminary)

Artifact on CP2 is negligible at low intensities (≤40%, mean_abs < 2 µV) and grows sharply from 50% (~92 µV) to 100% (~16,000 µV).
