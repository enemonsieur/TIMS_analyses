"""
plot_artifact_decay.py
Visualise how long the TIMS stimulation artifact persists after each pulse.
Helpers are module-level so they can be imported by other scripts.

Produces:
  decay_fig1_envelope_µV.png  – median ± IQR of Cz broadband envelope over one IOI
  decay_fig2_ratio_to_floor.png – ratio to baseline noise floor (log scale)
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from scipy.signal import butter, sosfiltfilt, hilbert, find_peaks
import mne, warnings
warnings.filterwarnings('ignore')

# ─── helpers (importable) ────────────────────────────────────────────────────

def bp_filter(x, fs, fmin=0.5, fmax=45, order=4):
    sos = butter(order, [fmin, fmax], btype='bandpass', fs=fs, output='sos')
    return sosfiltfilt(sos, x)

def detect_onsets(marker, fs):
    """Return pulse onsets (samples) and median IOI (s) from a stim-marker channel."""
    env = np.abs(hilbert(marker))
    prom = max(3 * np.std(env), np.percentile(env, 95) - np.percentile(env, 50))
    cand, _ = find_peaks(env, prominence=prom, distance=int(0.05 * fs))
    d = np.diff(cand / fs); d2 = d[d > 0.5]
    med_ioi = float(np.median(d2)) if len(d2) else 10.0
    min_dist = int(max(0.6 * med_ioi * fs, 1.5 * fs))
    kept, last = [], -10**9
    for i in cand:
        if i - last >= min_dist: kept.append(i); last = i
        elif env[i] > env[last]: kept[-1] = i; last = i
    return np.array(kept, dtype=int), med_ioi

def epoch_envelope(signal_env, onsets, ioi_n):
    """Stack per-onset envelope segments of length ioi_n."""
    valid = [o for o in onsets if o + ioi_n < len(signal_env)]
    return np.stack([signal_env[o:o + ioi_n] for o in valid])

# ─── main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    from pathlib import Path
    STIM = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-stim-pulse-10hz-GT-run02.vhdr"
    BASE = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-baseline-run01.vhdr"
    OUTDIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp02_subspace_separation_run02_10s")

    sr = mne.io.read_raw_brainvision(STIM, preload=True, verbose=False)
    br = mne.io.read_raw_brainvision(BASE, preload=True, verbose=False)
    fs = float(sr.info['sfreq'])

    stim_ch = next(c for c in sr.ch_names if 'stim' in c.lower())
    marker   = sr.copy().pick([stim_ch]).get_data()[0]
    cz_stim  = bp_filter(sr.copy().pick(['Cz']).get_data()[0], fs)
    cz_base  = bp_filter(br.copy().pick(['Cz']).get_data()[0], fs)

    onsets, med_ioi = detect_onsets(marker, fs)
    ioi_n  = int(med_ioi * fs)
    t      = np.arange(ioi_n) / fs

    env_stim = np.abs(hilbert(cz_stim))
    env_base = np.abs(hilbert(cz_base))
    noise_p75 = np.percentile(env_base, 75) * 1e6   # µV
    noise_p95 = np.percentile(env_base, 95) * 1e6

    epochs = epoch_envelope(env_stim * 1e6, onsets, ioi_n)   # µV
    med    = np.median(epochs, axis=0)
    p25    = np.percentile(epochs, 25, axis=0)
    p75    = np.percentile(epochs, 75, axis=0)
    ratio  = med / (np.percentile(env_base, 75) * 1e6)       # dimensionless

    # closest approach
    min_t = t[np.argmin(med)]

    # ── Figure 1: envelope in µV ──────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(13, 4), constrained_layout=True)
    #ax1.fill_between(t, p25, p75, alpha=0.2, color='steelblue', label='IQR')
    ax1.plot(t, med, color='steelblue', lw=1.5, label='Cz activity')
    #ax1.axhline(noise_p75, color='k',      lw=1.2, ls='--', label=f'Baseline p75  ({noise_p75:.1f} µV)')
    ax1.axhline(noise_p95, color='gray',   lw=0.8, ls=':',  label=f'Baseline activity  ({noise_p95:.1f} µV)')
    ax1.axvspan(med_ioi - 1.0, med_ioi, color='tomato', alpha=0.12, label='Stim ON (−1–0s)')
    ax1.axvline(min_t,    color='green',   lw=1.2, ls='--', label=f'Minimum Amp')
    ax1.set_yscale('log'); ax1.set_xlim(0, med_ioi)
    ax1.set_xlabel('Time (seconds)'); ax1.set_ylabel('Log Amplitude (µV)')
    ax1.set_title(f'Average Time course over {len(epochs)} pulses with Epochs ={med_ioi:.1f} s')
    ax1.legend(loc='upper right', fontsize=8, ncols=2)
    ax1.grid(True, which='both', alpha=0.1)
    fig1.savefig(OUTDIR / 'decay_fig1_envelope_uV.png', dpi=200); plt.close(fig1)
    print('Saved decay_fig1_envelope_uV.png')

    # ── Figure 2: ratio to baseline floor ────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(13, 4), constrained_layout=True)
    ax2.plot(t, ratio, color='darkorange', lw=1.5)
    ax2.axhline(1,  color='k',    lw=1.2, ls='--', label='Baseline p75 (1×)')
    ax2.axhline(2,  color='gray', lw=0.8, ls=':',  label='2× floor (target)')
    ax2.axvspan(med_ioi - 1.0, med_ioi, color='tomato', alpha=0.12, label='Stim ON (−1–0 s pre-pulse)')
    ax2.axvline(1.05,     color='tomato',  lw=1.0, ls='--', label='mask_off start (1.05 s)')
    ax2.axvline(min_t,    color='green',   lw=1.2, ls='--', label=f'Minimum {ratio.min():.0f}× at {min_t:.1f} s')
    ax2.set_yscale('log'); ax2.set_xlim(0, med_ioi)
    ax2.set_xlabel('Time post-onset (s)'); ax2.set_ylabel('Ratio to baseline noise floor (log)')
    ax2.set_title('Artifact-to-noise ratio over IOI — artifact never fully decays')
    ax2.legend(loc='upper right', fontsize=8, ncols=2)
    ax2.grid(True, which='both', alpha=0.2)
    fig2.savefig(OUTDIR / 'decay_fig2_ratio_to_floor.png', dpi=200); plt.close(fig2)
    print('Saved decay_fig2_ratio_to_floor.png')
