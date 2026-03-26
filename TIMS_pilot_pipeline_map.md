# TIMS Pilot/Dose-Response Pipeline Map (Preproc -> Trials -> Epochs -> Analyses)

This is the canonical, minimal-to-full pipeline for the pilot/doseresp datasets.
It is written as an I/O map: each stage names the required inputs, the exact
transformations implemented in the scripts, and the outputs you should expect.

Scope (datasets): `TIMS_data_sync/pilot/doseresp/` only.

Scope (scripts): `plot_artifact_decay.py`, `check_decay_presence.py`,
`check_minus1.py`, `artifacts_analysis_21Feb.py`, `plot_stim_10_30s.py`.

High-level flow:

`BrainVision (.vhdr/.eeg/.vmrk)` -> `mne.io.Raw` -> (EEG pick + filters)
-> pulse onsets from `stim` -> optional ON/OFF masks -> epochs -> analyses/figures.

## Verified Dataset Metadata (from .vhdr)

| Field | Value |
| --- | --- |
| Runs | `exp02-phantom-stim-pulse-10hz-GT-run01.*`, `exp02-phantom-stim-pulse-10hz-GT-run02.*` |
| Baseline | `exp02-phantom-baseline-run01.*` |
| Format | float32, multiplexed |
| Sampling rate | 1000 Hz (SamplingInterval=1000 us) |
| Channels | 33 total: 31 EEG + `ground_truth` + `stim` |
| Core roles | EEG: all except `ground_truth`/`stim`; `stim`: pulse marker; `ground_truth`: 10 Hz reference |

Canonical shapes: `raw.get_data()` is `(n_ch, n_times)`; EEG-only arrays are
typically `(n_eeg, n_times)`; `stim` and `ground_truth` are 1D vectors of
length `n_times`.

## Stage 1: Import (Raw Objects)

Input is a `.vhdr` path. The import call is `mne.io.read_raw_brainvision(vhdr, preload=True)`.
Downstream assumes `stim` exists; `ground_truth` is required only for GT-based metrics.

## Stage 2: Minimal Preprocessing (Strictly Necessary)

| What | Input(s) | Transformation(s) | Output(s) | Used in |
| --- | --- | --- | --- | --- |
| EEG pick | `raw` | drop `stim`, `ground_truth`, and any `STI*` | EEG-only raw/array | all analyses |
| Bad electrodes | EEG ch list | drop fixed `BAD_CHANNELS` | reduced `eeg_chs` | `artifacts_analysis_21Feb.py` |
| Broadband | EEG | 50 Hz notch, then 0.5-45 Hz bandpass | `X_*_bb` | decay + cleaning |
| 10 Hz band | EEG + `ground_truth` | 8-12 Hz bandpass | `X_*_10`, `gt_*_10` | SSD + metrics |
| SSD noise | EEG | 3-22 Hz bandpass + 10 Hz notch (Q=10) | `Cn` covariance input | GT-SSD |

## Stage 3: Trial Definition (Pulse Onsets + IOI)

Pulse detection is implemented similarly across scripts. Inputs are `marker`
(`stim`) and `fs`. Outputs are `onsets` (sample indices) and `med_ioi` (s).

Algorithm (as implemented):

```text
env = abs(hilbert(marker))
prom = max(3*std(env), percentile(env,95) - percentile(env,50))
cand = find_peaks(env, prominence=prom, distance=int(0.05*fs))
(only in artifacts_analysis_21Feb.py: if len(cand)<5, use prominence=std(env), distance=int(0.02*fs))

ioi_guess = median(diff(cand/fs) filtered by >0.5s) else 10.0
min_dist = int(max(0.6*ioi_guess*fs, 1.5*fs))
onsets = keep 1 peak per min_dist window (keep strongest if collisions)
med_ioi = median(diff(onsets/fs) filtered by >0.5s) else 10.0
```

## Stage 4: Derived Masks (ON/OFF Segmentation)

Defined only in `artifacts_analysis_21Feb.py` to separate stimulation artifact
windows from off periods.

| Mask | Definition (per onset) | Shape | Used for |
| --- | --- | --- | --- |
| `mask_on` | samples `[o, o+1.00s)` | `(n_times,)` | ON covariance, ON PSD, RMS suppression |
| `mask_end` | samples `[o+0.90s, o+1.05s)` | `(n_times,)` | end-jump RMS suppression |
| `mask_off` | all samples except `[o, o+1.05s)` | `(n_times,)` | OFF covariance, SSD training, OFF metrics |

## Stage 5: Epoching (Windows + Validity)

Epoching always drops onsets that do not fit fully inside the requested window.

| Script | Signal(s) | Window | Output shape |
| --- | --- | --- | --- |
| `plot_artifact_decay.py` | Cz envelope | `0 .. med_ioi` (IOI length) | `(n_epochs, ioi_n)` |
| `check_decay_presence.py` | Cz envelope | `0 .. med_ioi` (IOI length) | `(n_epochs, ioi_n)` |
| `check_minus1.py` | Cz envelope | `-1.2 .. +2.0` s | `(n_epochs, 3.2*fs)` |
| `artifacts_analysis_21Feb.py` | Cz bb + components | `-0.25 .. +2.0` s | `(n_epochs, 2.25*fs)` |
| `artifacts_analysis_21Feb.py` | Cz env (over IOI) | `0 .. Twin` where `Twin=min(med_ioi,10.0)` | `(n_epochs, Twin*fs)` |

## Analysis Branches (What Runs After Epochs)

| Branch | Goal | Required inputs | Outputs | Script |
| --- | --- | --- | --- | --- |
| A: Decay map | how long envelope stays above baseline floor | stim+baseline, `stim`, `Cz` | `decay_fig1_envelope_uV.png`, `decay_fig2_ratio_to_floor.png` | `plot_artifact_decay.py` |
| B: Decay stats | quantify min ratio and below-threshold fractions | stim (+baseline floor) | printed metrics only | `check_decay_presence.py`, `check_minus1.py` |
| C: Subspace separation | isolate GT subspace and artifact subspace; clean | stim+baseline, `ground_truth`, masks | figures + `metrics_summary.csv` + `report.txt` | `artifacts_analysis_21Feb.py` |
| D: Window QC | quick visual inspection of EEG + aux channels | stim run | `stim_10_30s.png` | `plot_stim_10_30s.py` |

Branch C (subspace separation) has a fixed internal structure:

| Step | Core transformation | Key outputs |
| --- | --- | --- |
| 1 | pulse-aligned Cz + PSD baseline vs OFF vs ON | `fig1a_*`, `fig1b_*`, `fig1c_*` |
| 2 | GT-SSD (GED on `Cs` vs `Cn`) + component scoring | `fig2a_*`, `fig2b_*` |
| 3 | artifact subspace (GED on `Con` vs `Coff`) | `fig3_*` |
| 4 | cleaning (`X_clean = X - P_art X`) + GT-protected variant | `fig4a_*`..`fig4d_*` |
| 5 | coherence/PLV/SNR + RMS suppression + percent recovery | `fig5a_*`..`fig5c_*`, `metrics_summary.csv`, `report.txt` |

## Minimal Checklist (Import -> Epochs)

1. Load stim and baseline with `mne.io.read_raw_brainvision(..., preload=True)`.
2. Pick EEG channels; keep `stim` and (optionally) `ground_truth` separately.
3. Apply 50 Hz notch + 0.5-45 Hz bandpass to the EEG signal you will epoch.
4. Detect `onsets` from `stim` using envelope + refractory; compute `med_ioi`.
5. Choose epoching window (fixed pre/post or IOI length) and drop invalid onsets.
6. Produce `(n_epochs, n_times_epoch)` arrays for downstream plots/metrics.
