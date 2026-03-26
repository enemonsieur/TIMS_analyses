"""
Phase-difference PLV / ITPC: Ground Truth ↔ Signal comparison.
Compares phase synchronisation between the 10 Hz ground-truth channel
and each EEG signal (raw Cz, SSD-filtered) during TIMS stimulation,
with a no-stim baseline control (GT ↔ Cz without stimulation).
PLV  = |mean(exp(i·Δφ))| at pulse onset  → phase coherence across trials
ITPC = same formula at every time point   → time-resolved phase coherence
Δφ   = angle(GT) − angle(signal)
"""
from pathlib import Path
import numpy as np
import mne
from scipy.signal import hilbert
from plot_helpers import (
    plot_timeseries,
    plot_plv_group,
    plot_itpc_group,
    plot_trials_group,
    run_ssd,
    detect_pulses,
    epoch_1d,
    prep_eeg,
)


EXPDIR = Path(__file__).parent / "Experiment_1"
OUTDIR = EXPDIR / "figures"
OUTDIR.mkdir(exist_ok=True)

# 1. Load stim + baseline recordings
stim_raw = mne.io.read_raw_brainvision(str(EXPDIR / "STIM_SP_01_notTurnedOff.vhdr"), preload=True, verbose=False)
baseline_raw = mne.io.read_raw_brainvision(str(EXPDIR / "baseline-pre-STIM-not-turned-off.vhdr"), preload=True, verbose=False)
sfreq = stim_raw.info["sfreq"]

# --- sanity: required raw channels must exist before preprocessing ---
REQUIRED_RAW_CH = ["stim", "ground_truth"]
for name, raw in (("stim_raw", stim_raw), ("baseline_raw", baseline_raw)):
    missing = [ch for ch in REQUIRED_RAW_CH if ch not in raw.ch_names]
    if missing:
        raise RuntimeError(f"{name} missing required channels: {missing}. Available: {raw.ch_names}")
print("Raw-channel check OK: 'stim' and 'ground_truth' present in both recordings.")

# 2. DETECT PULSES (stim recording only – baseline stim channel is empty)
stim_pulse_onsets, stim_channel_waveform = detect_pulses(stim_raw, ch="stim")
print(f"  Stim pulses detected: {len(stim_pulse_onsets)}")

# 3. LIGHT PREPROCESSING
stim_eeg, baseline_eeg = prep_eeg(stim_raw), prep_eeg(baseline_raw)
reference_channel = "Cz" if "Cz" in stim_eeg.ch_names else stim_eeg.ch_names[0]

stim_raw.set_channel_types({'ground_truth': 'eeg'}) # make sure GT is an EEG
baseline_raw.set_channel_types({'ground_truth': 'eeg'}) # make sure GT is an EEG

# 4a. EXTRACT PHASE from raw data
stim_cz_analytic = hilbert(stim_eeg.copy().pick([reference_channel]).filter(8, 12, verbose=False).get_data()[0])
baseline_cz_analytic = hilbert(baseline_eeg.copy().pick([reference_channel]).filter(8, 12, verbose=False).get_data()[0])
stim_gt_analytic     = hilbert(stim_raw.copy().pick(['ground_truth']).filter(8, 12, verbose=False).get_data()[0])
baseline_gt_analytic = hilbert(baseline_raw.copy().pick(["ground_truth"]).filter(8, 12, verbose=False).get_data()[0])

# 4b. EXTRACT PHASE from SSD
ssd_events = mne.make_fixed_length_events(stim_eeg, duration=4.0)
ssd_filters, _, ssd_eigenvalues = run_ssd(stim_eeg, ssd_events, (8, 12), (3, 22), n_comp=min(6, len(stim_eeg.ch_names)))
ssd_first_component = ssd_filters[0] @ stim_eeg.copy().filter(8, 12, verbose=False).get_data()
if np.isrealobj(ssd_first_component):
    ssd_first_component_analytic = hilbert(ssd_first_component)
else:
    ssd_first_component_analytic = ssd_first_component  # already complex

# 5. EPOCH around pulses
pre_samples, post_samples = int(sfreq), int(2 * sfreq)
epoch_time_vector, pulse_onset_index = np.arange(-pre_samples, post_samples) / sfreq, pre_samples
stim_cz_epochs, valid_stim_pulses = epoch_1d(stim_cz_analytic, stim_pulse_onsets, pre_samples, post_samples)
stim_gt_epochs, _                 = epoch_1d(stim_gt_analytic, stim_pulse_onsets, pre_samples, post_samples)
baseline_cz_epochs, _             = epoch_1d(baseline_cz_analytic, stim_pulse_onsets, pre_samples, post_samples)
baseline_gt_epochs, _             = epoch_1d(baseline_gt_analytic, stim_pulse_onsets, pre_samples, post_samples)
ssd_epochs, _                     = epoch_1d(ssd_first_component_analytic, stim_pulse_onsets, pre_samples, post_samples)
print(f"  Epochs: stim Cz={len(stim_cz_epochs)}, stim GT={len(stim_gt_epochs)}, "
      f"baseline Cz={len(baseline_cz_epochs)}, baseline GT={len(baseline_gt_epochs)}, SSD={len(ssd_epochs)}")

# 6. PHASE-DIFFERENCE PLV: ground_truth ↔ each signal
#    Δφ = angle(GT) − angle(signal);  PLV = |mean(exp(i·Δφ))| across trials
#    Artifact window (±300 ms around pulse onset) is excluded from PLV/ITPC.
ARTIFACT_MS = 300
artifact_samples = int(ARTIFACT_MS / 1000.0 * sfreq)
# Boolean mask: True = clean sample, False = artifact window
n_epoch_samples = pre_samples + post_samples
clean_mask = np.ones(n_epoch_samples, dtype=bool)
clean_mask[pulse_onset_index - artifact_samples : pulse_onset_index + artifact_samples] = False
# For PLV we pick a representative clean time point outside the artifact window
plv_eval_index = pulse_onset_index + artifact_samples  # first clean sample after artifact
print(f"  Artifact exclusion: ±{ARTIFACT_MS} ms ({artifact_samples} samples) around pulse onset; "
      f"PLV evaluated at t={epoch_time_vector[plv_eval_index]:.3f} s")

def phase_diff_plv(gt_epochs, signal_epochs, t0, mask=None):
    """PLV/ITPC between GT and signal based on their phase difference.
    If mask is provided, ITPC is computed only at clean time points;
    masked time points are set to NaN."""
    diff = np.angle(gt_epochs) - np.angle(signal_epochs)
    plv  = np.abs(np.mean(np.exp(1j * diff[:, t0])))
    itpc = np.abs(np.mean(np.exp(1j * diff), axis=0))
    if mask is not None:
        itpc[~mask] = np.nan  # mark artifact window as NaN
    R    = np.abs(np.sum(np.exp(1j * diff[:, t0])))
    n    = len(diff)
    z    = R**2 / n
    p    = max(np.exp(-z) * (1 + (2*z - z**2) / (4*n)), 0.0)
    return plv, itpc, z, p

# STIM conditions: exclude artifact window
plv_gt_cz,   itpc_gt_cz,   _, p_gt_cz   = phase_diff_plv(stim_gt_epochs, stim_cz_epochs, plv_eval_index, clean_mask)
plv_gt_ssd,  itpc_gt_ssd,  _, p_gt_ssd  = phase_diff_plv(stim_gt_epochs, ssd_epochs,      plv_eval_index, clean_mask)
# Baseline: no artifact, evaluate at same relative time for fair comparison
plv_gt_base, itpc_gt_base, _, p_gt_base = phase_diff_plv(baseline_gt_epochs, baseline_cz_epochs, plv_eval_index)
chance = 1 / np.sqrt(max(len(stim_gt_epochs), 1))
print(f"  Phase-diff PLV (artifact-free):  GT↔Cz={plv_gt_cz:.4f}(p={p_gt_cz:.1e})  "
      f"GT↔SSD={plv_gt_ssd:.4f}(p={p_gt_ssd:.1e})  "
      f"Baseline GT↔Cz={plv_gt_base:.4f}(p={p_gt_base:.1e})  chance={chance:.4f}")

# 7. PLOTS
plot_timeseries(OUTDIR, stim_cz_analytic, ssd_first_component, stim_channel_waveform,
                valid_stim_pulses, sfreq, ssd_eigenvalues, reference_channel)

labels    = ["Baseline GT↔Cz", "STIM GT↔Cz", "STIM GT↔SSD"]
phases_t0 = [
    np.angle(baseline_gt_epochs[:, plv_eval_index]) - np.angle(baseline_cz_epochs[:, plv_eval_index]),
    np.angle(stim_gt_epochs[:, plv_eval_index])     - np.angle(stim_cz_epochs[:, plv_eval_index]),
    np.angle(stim_gt_epochs[:, plv_eval_index])     - np.angle(ssd_epochs[:, plv_eval_index]),
]
plvs  = [plv_gt_base, plv_gt_cz, plv_gt_ssd]
ps    = [p_gt_base, p_gt_cz, p_gt_ssd]
itpcs = [itpc_gt_base, itpc_gt_cz, itpc_gt_ssd]

plot_plv_group(OUTDIR, labels, phases_t0, plvs, ps,
               "Phase coherence: Ground Truth ↔ Signal", "fig2_plv_gt_vs_signal.png")
plot_itpc_group(OUTDIR, epoch_time_vector, labels, itpcs, chance,
                "ITPC: Ground Truth ↔ Signal", "fig3_itpc_gt_vs_signal.png")
# Raster: show phase-difference (GT − signal) per trial, not raw amplitude
phase_diff_baseline = np.exp(1j * (np.angle(baseline_gt_epochs) - np.angle(baseline_cz_epochs)))
phase_diff_cz       = np.exp(1j * (np.angle(stim_gt_epochs)     - np.angle(stim_cz_epochs)))
phase_diff_ssd      = np.exp(1j * (np.angle(stim_gt_epochs)     - np.angle(ssd_epochs)))
plot_trials_group(OUTDIR, epoch_time_vector, labels,
                  [phase_diff_baseline, phase_diff_cz, phase_diff_ssd],
                  "Raster Plot: Phase difference (GT − Signal)", "fig4_trials_gt_vs_signal.png")
print(f"All figures saved in {OUTDIR}")
