# Lab Book: exp05 -- Phantom cTBS Artifact Characterization

**Date:** March 20, 2025
**Subject:** Phantom (not human)
**Goal:** Verify that stimulation artifacts are negligible at 30% intensity and significant at 100%

---

## Stimulation Protocol

**Protocol file:** `ctbs_like_v1_amp5hz_mod50hz_triplets.tims`
**Protocol script:** `ctbs_like_v1_amp5hz_mod50hz_triplets.py`

| Parameter | Value |
|-----------|-------|
| Amplitude envelope | 5 Hz sinusoidal, applied to both coils A1 and A2 |
| Modulation | 50 Hz triplets (events at 0, 20, 40 ms per 200 ms burst) |
| Burst gating | 2 s ON / 3 s OFF (cycle = 5 s) |
| Session duration | 500 s |
| Modulation routing | Channel A |

This mimics the temporal structure of cTBS: theta-frequency (5 Hz) bursts of high-frequency (50 Hz) triplets, delivered in intermittent ON/OFF blocks.

---

## Recordings

| File | Condition | GT | Duration | Time |
|------|-----------|:--:|-------:|------|
| `exp05-phantom-rs-GT-cTBS-run01.vhdr` | Baseline resting state | No | 310.0 s | 16:33 |
| `exp05-phantom-rs-GT-cTBS-run02.vhdr` | Baseline resting state | Yes | 315.6 s | 16:39 |
| `exp05-phantom-rs-STIM-ON-GT-cTBS-run01.vhdr` | cTBS at 100% intensity | Yes | 526.0 s | 17:18 |
| `exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr` | cTBS at 30% intensity | Yes | 339.0 s | 17:30 |

Recording order: baseline (no GT) -> baseline (GT) -> 100% stim -> 30% stim.

---

## Recording Metadata

| Field | Value |
|-------|-------|
| Format | BrainVision float32, multiplexed |
| Sampling rate | 1000 Hz (SamplingInterval = 1000 us) |
| Channels | 33 total: 31 EEG + `ground_truth` + `stim` |
| Reference | Fz (online, not re-referenced offline) |
| Amplifier | actiCHamp Base Unit (S/N 23090148) + 32 CH Module |
| Online filters | 0.3 s highpass + 50 Hz notch (software) |
| Hardware bandwidth | DC to 280 Hz |
| Electrode file | CACS-64_NO_REF.bvef |

**EEG channels (31):** Fp1, F3, F7, FT9, FC5, FC1, C3, T7, TP9, CP5, CP1, Pz, P3, P7, O1, Oz, O2, P4, P8, TP10, CP6, CP2, Cz, C4, T8, FT10, FC6, FC2, F4, F8, Fp2

**Impedances:** All channels 3-11 kOhm (well below 25 kOhm good threshold).

---

## Conditions Explained

- **run01 (baseline, no GT):** Phantom at rest, stimulator off, ground truth channel not driven. Provides noise floor measurement.
- **run02 (baseline, GT):** Phantom at rest, stimulator off, ground truth channel driven. The recorded GT peak later turned out to sit around `7.1 Hz`, so this run is the SSD calibration reference for the exp05 GT band, not a clean `10 Hz` calibration.
- **STIM-ON 100%:** Full-intensity cTBS. Expected: large artifacts during ON blocks, significant post-ON decay, substantial offset jumps at ON/OFF transitions.
- **STIM-ON 30%:** Reduced-intensity cTBS. Hypothesis: artifacts negligible at this level, minimal or undetectable decay.

---

## Hypothesis

Artifact magnitude and decay time are negligible at 30% intensity but significant at 100%. If confirmed, 30% is a viable operating point for simultaneous EEG recording during TIMS stimulation.

---

## Expected ON-block counts

Given 5 s cycles (2 s ON + 3 s OFF):
- 100% recording (526 s): ~105 ON-blocks
- 30% recording (339 s): ~67 ON-blocks

---

## Analysis Scripts

- `analyses_artifact_exp05.py` -- artifact magnitude and decay at 30% vs 100%
- `analyses_ssd_exp05.py` -- ground truth recovery via SSD across conditions
- `analyses_ica_topo_exp05.py` -- ICA topography of artifact at 30%
