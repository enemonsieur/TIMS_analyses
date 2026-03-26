"""
TIMS Stimulation–EEG Synchronization Analysis  (revised)
=========================================================
Stimulation parameters (from user):
  - 0.25 Hz pulse rate  (1 pulse every 4 s, confirmed: 83 pulses, ISI = 4.000 s)
  - ~9 ms pulse duration (brief TMS-like pulse)
  - 10 Hz TI beat frequency (ground_truth channel)

Analysis strategy:
  1. Detect pulse onsets from the 'stim' channel (threshold on envelope)
  2. SSD on EEG → extract best 10 Hz spatial component
  3. Epoch SSD source around pulse onsets → event-related analysis
  4. Multiple figures:
     Fig 1 – Data overview: raw channels, stim pulses, PSD
     Fig 2 – SSD decomposition: topographies, eigenvalues, component PSDs
     Fig 3 – Pulse-locked time courses: ERP, single-trial, time-freq
     Fig 4 – Phase synchronization: inter-trial PLV, phase distribution
     Fig 5 – STIM vs Baseline comparison (if baseline data exists)

Author: Automated analysis
"""

from pathlib import Path
import numpy as np
import mne
from scipy import linalg
from scipy.signal import welch, hilbert, find_peaks, butter, filtfilt
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt


# =========================================================================== #
#  SSD (calibration-style GED, from analysis.py)                              #
# =========================================================================== #

def _apply_ssd_filters(data, filters):
    """filters: (n_comp, n_ch),  data: (n_epochs, n_ch, n_times)."""
    return np.array([[f @ e for e in data] for f in filters])


def run_ssd_calibration_style(
    raw, events, freq_band, noise_band, event_id=None,
    tmin=0, tmax=4, n_components=6, verbose=True,
):
    freq_low, freq_high = freq_band
    ch_names_out = list(raw.ch_names)

    raw_signal = raw.copy().filter(freq_low, freq_high, verbose=False)
    raw_noise  = raw.copy().filter(noise_band[0], noise_band[1], verbose=False)
    raw_noise  = raw_noise.notch_filter(
        freqs=[(freq_low + freq_high) / 2.0],
        notch_widths=freq_high - freq_low, verbose=False,
    )

    if event_id is None:
        event_id = list(np.unique(events[:, 2]))

    if verbose:
        print(f"  SSD  signal={freq_low}-{freq_high} Hz, "
              f"noise={noise_band[0]}-{noise_band[1]} Hz (signal notched)")

    epochs_signal = mne.Epochs(raw_signal, events, event_id=event_id,
                               tmin=tmin, tmax=tmax, baseline=None,
                               proj=False, preload=True, verbose=False)
    epochs_noise  = mne.Epochs(raw_noise, events, event_id=event_id,
                               tmin=tmin, tmax=tmax, baseline=None,
                               proj=False, preload=True, verbose=False)

    data_signal = epochs_signal.get_data()
    data_noise  = epochs_noise.get_data()
    if verbose:
        print(f"  Epochs: {len(data_signal)} trials, shape {data_signal.shape}")

    sig_concat   = np.concatenate([np.real(e) for e in data_signal], axis=-1)
    noise_concat = np.concatenate([np.real(e) for e in data_noise],  axis=-1)
    COV_signal = np.cov(sig_concat)
    COV_noise  = np.cov(noise_concat)

    evals, evecs = linalg.eig(COV_signal, COV_noise)
    evals = np.real(evals)
    idx   = np.argsort(evals)[::-1]
    evals, evecs = evals[idx], evecs[:, idx]

    filters  = evecs.T[:n_components, :]
    patterns = linalg.pinv(evecs.T)[:, :n_components]
    evals    = evals[:n_components]
    sources  = _apply_ssd_filters(np.real(data_signal), filters)

    if verbose:
        print(f"  Top eigenvalues: {', '.join(f'{e:.3f}' for e in evals[:min(3, len(evals))])}")
    return sources, patterns, evals, filters, ch_names_out


# =========================================================================== #
#  MAIN                                                                       #
# =========================================================================== #

def main():
    EXPDIR   = Path(__file__).parent / "Experiment_1"
    OUTDIR   = EXPDIR / "figures"
    OUTDIR.mkdir(exist_ok=True)
    VHDR     = EXPDIR / "STIM_SP_01_notTurnedOff.vhdr"

    # Also load baseline for comparison
    VHDR_BASE = EXPDIR / "baseline-pre-STIM-not-turned-off.vhdr"

    # ------------------------------------------------------------------ #
    # 1.  Load data                                                       #
    # ------------------------------------------------------------------ #
    raw_full = mne.io.read_raw_brainvision(str(VHDR), preload=True, verbose=False)
    sfreq    = raw_full.info["sfreq"]
    print(f"STIM loaded : {VHDR.name}  sfreq={sfreq:.0f} Hz  dur={raw_full.times[-1]:.1f} s")

    raw_base = None
    if VHDR_BASE.exists():
        raw_base = mne.io.read_raw_brainvision(str(VHDR_BASE), preload=True, verbose=False)
        print(f"BASE loaded : {VHDR_BASE.name}  dur={raw_base.times[-1]:.1f} s")

    # ------------------------------------------------------------------ #
    # 2.  Extract stim & ground_truth channels                           #
    # ------------------------------------------------------------------ #
    stim_data = raw_full.copy().pick(["stim"]).get_data()[0]
    gt_data   = raw_full.copy().pick(["ground_truth"]).get_data()[0]

    # ---- detect pulse onsets from stim channel (0.25 Hz, ~9 ms pulses) #
    stim_env  = np.abs(stim_data)
    thresh    = stim_data.mean() + 3 * stim_data.std()
    above     = stim_env > thresh
    diffs     = np.diff(above.astype(int))
    pulse_onsets = np.where(diffs == 1)[0] + 1  # index of first sample above thresh

    pulse_isi = np.diff(pulse_onsets) / sfreq
    print(f"\nPulse onsets detected: {len(pulse_onsets)}")
    print(f"  ISI = {pulse_isi.mean():.4f} +- {pulse_isi.std():.4f} s  "
          f"({1/pulse_isi.mean():.3f} Hz)")
    print(f"  First pulse at {pulse_onsets[0]/sfreq:.3f} s, "
          f"last at {pulse_onsets[-1]/sfreq:.3f} s")

    # ---- 10 Hz reference from ground_truth ----------------------------- #
    b10, a10 = butter(4, [8, 12], btype="band", fs=sfreq)
    gt_10hz  = filtfilt(b10, a10, gt_data)
    gt_analytic = hilbert(gt_10hz)
    gt_phase = np.angle(gt_analytic)

    # ------------------------------------------------------------------ #
    # 3.  Prepare EEG for SSD                                            #
    # ------------------------------------------------------------------ #
    non_eeg = [ch for ch in raw_full.ch_names
               if ch in ("stim", "ground_truth") or ch.startswith("STI")]
    raw_eeg = raw_full.copy().drop_channels(non_eeg)
    raw_eeg.notch_filter([50.0], notch_widths=2, verbose=False)
    raw_eeg.filter(0.5, 45.0, verbose=False)
    n_eeg = len(raw_eeg.ch_names)
    print(f"\nEEG channels: {n_eeg}  {raw_eeg.ch_names}")

    # Set montage for topoplots
    try:
        montage = mne.channels.make_standard_montage("standard_1020")
        raw_eeg.set_montage(montage, on_missing="warn")
    except Exception:
        pass

    # Also prepare baseline EEG
    raw_base_eeg = None
    if raw_base is not None:
        non_eeg_b = [ch for ch in raw_base.ch_names
                     if ch in ("stim", "ground_truth") or ch.startswith("STI")]
        raw_base_eeg = raw_base.copy().drop_channels(non_eeg_b)
        raw_base_eeg.notch_filter([50.0], notch_widths=2, verbose=False)
        raw_base_eeg.filter(0.5, 45.0, verbose=False)
        # Keep only common channels
        common = [ch for ch in raw_eeg.ch_names if ch in raw_base_eeg.ch_names]
        raw_eeg = raw_eeg.pick(common)
        raw_base_eeg = raw_base_eeg.pick(common)
        n_eeg = len(common)

    # ------------------------------------------------------------------ #
    # 4.  SSD – extract 10 Hz component (calibration style)              #
    # ------------------------------------------------------------------ #
    signal_band = (8.0, 12.0)
    noise_band  = (3.0, 22.0)

    # Pseudo-events every 4 s for SSD (continuous decomposition)
    epoch_dur  = 4.0
    n_ssd_ep   = int(raw_eeg.times[-1] / epoch_dur) - 1
    ssd_events = np.array([[int(i * epoch_dur * sfreq), 0, 1]
                            for i in range(n_ssd_ep)])
    n_comp = min(6, n_eeg)

    print(f"\nRunning SSD  signal={signal_band}, noise={noise_band}, "
          f"n_epochs={n_ssd_ep}, epoch_dur={epoch_dur} s")

    sources, patterns, evals, filters, ch_names = run_ssd_calibration_style(
        raw_eeg, ssd_events, signal_band, noise_band,
        event_id=1, tmin=0, tmax=epoch_dur, n_components=n_comp, verbose=True,
    )

    # ---- continuous SSD 10 Hz source ---------------------------------- #
    raw_eeg_bp  = raw_eeg.copy().filter(signal_band[0], signal_band[1], verbose=False)
    eeg_data_bp = raw_eeg_bp.get_data()
    best = 0
    ssd_10hz     = filters[best] @ eeg_data_bp   # (n_times,)
    ssd_analytic = hilbert(ssd_10hz)
    ssd_phase    = np.angle(ssd_analytic)
    ssd_envelope = np.abs(ssd_analytic)
    print(f"\nSSD comp {best} -> continuous 10 Hz source, {ssd_10hz.shape[0]} samples")

    # Also compute all component time-series for later
    all_comp_ts = np.array([filters[c] @ eeg_data_bp for c in range(n_comp)])

    # ------------------------------------------------------------------ #
    # 5.  Epoch around pulse onsets                                      #
    # ------------------------------------------------------------------ #
    pre_s, post_s = 1.0, 2.0        # epoch window: -1 to +2 s around pulse
    pre_n  = int(pre_s * sfreq)
    post_n = int(post_s * sfreq)
    epoch_len = pre_n + post_n

    # Filter valid onsets
    valid_onsets = pulse_onsets[(pulse_onsets > pre_n) &
                               (pulse_onsets < len(ssd_10hz) - post_n)]
    n_trials = len(valid_onsets)
    print(f"Valid pulse epochs: {n_trials}  (window: -{pre_s} to +{post_s} s)")

    t_epoch = np.arange(-pre_n, post_n) / sfreq  # epoch time axis

    # Epoch the SSD 10 Hz source
    ssd_epochs = np.array([ssd_10hz[o - pre_n: o + post_n] for o in valid_onsets])
    ssd_env_epochs = np.array([ssd_envelope[o - pre_n: o + post_n] for o in valid_onsets])
    ssd_phase_epochs = np.array([ssd_phase[o - pre_n: o + post_n] for o in valid_onsets])

    # Epoch the ground_truth 10 Hz
    gt_epochs = np.array([gt_10hz[o - pre_n: o + post_n] for o in valid_onsets])

    # Epoch the stim channel
    stim_epochs = np.array([stim_data[o - pre_n: o + post_n] for o in valid_onsets])

    # Epoch raw EEG (best channel for comparison)
    ref_ch = "Cz" if "Cz" in raw_eeg.ch_names else raw_eeg.ch_names[0]
    ref_idx = raw_eeg.ch_names.index(ref_ch)
    raw_eeg_data = raw_eeg.get_data()
    eeg_epochs_ref = np.array([raw_eeg_data[ref_idx, o - pre_n: o + post_n]
                               for o in valid_onsets])

    # ------------------------------------------------------------------ #
    # 6.  Synchronization metrics                                        #
    # ------------------------------------------------------------------ #
    # 6a. Inter-trial phase coherence (ITPC) at each time point
    itpc = np.abs(np.mean(np.exp(1j * ssd_phase_epochs), axis=0))

    # 6b. Phase at pulse onset (t=0)
    onset_idx = pre_n
    phases_at_onset = ssd_phase_epochs[:, onset_idx]
    plv_onset = np.abs(np.mean(np.exp(1j * phases_at_onset)))

    # Rayleigh test
    n_ph = len(phases_at_onset)
    R = np.abs(np.sum(np.exp(1j * phases_at_onset)))
    z_ray = R**2 / n_ph
    p_ray = np.exp(-z_ray) * (1 + (2*z_ray - z_ray**2)/(4*n_ph))
    p_ray = max(p_ray, 0.0)

    # 6c. Cross-PLV (SSD vs ground_truth, global)
    n_common = min(len(ssd_phase), len(gt_phase))
    dphi = ssd_phase[:n_common] - gt_phase[:n_common]
    plv_global = np.abs(np.mean(np.exp(1j * dphi)))

    # 6d. ITPC in pre vs post windows
    pre_phase = ssd_phase_epochs[:, :pre_n]
    post_phase = ssd_phase_epochs[:, pre_n:pre_n + int(0.5*sfreq)]
    itpc_pre  = np.abs(np.mean(np.exp(1j * pre_phase), axis=0)).mean()
    itpc_post = np.abs(np.mean(np.exp(1j * post_phase), axis=0)).mean()

    # 6e. Envelope (amplitude) modulation around pulses
    env_mean = ssd_env_epochs.mean(axis=0)
    env_pre  = ssd_env_epochs[:, :pre_n].mean()
    env_post = ssd_env_epochs[:, pre_n:pre_n + int(0.5*sfreq)].mean()

    print(f"\n{'='*60}")
    print(f"SYNCHRONIZATION RESULTS")
    print(f"{'='*60}")
    print(f"  Inter-trial PLV at pulse onset  : {plv_onset:.4f}")
    print(f"  Rayleigh test  z={z_ray:.2f}, p={p_ray:.2e}")
    print(f"  ITPC pre-stim  (-1 to 0 s)      : {itpc_pre:.4f}")
    print(f"  ITPC post-stim ( 0 to 0.5 s)    : {itpc_post:.4f}")
    print(f"  Cross-PLV (SSD vs GT, global)   : {plv_global:.4f}")
    print(f"  10 Hz envelope pre              : {env_pre:.4e}")
    print(f"  10 Hz envelope post             : {env_post:.4e}")
    print(f"  Envelope ratio (post/pre)       : {env_post/env_pre:.3f}")
    print(f"{'='*60}\n")

    # ==================================================================== #
    #                       FIGURE 1: DATA OVERVIEW                        #
    # ==================================================================== #
    print("Plotting Figure 1: Data overview ...")
    fig1, axes1 = plt.subplots(4, 1, figsize=(16, 14), constrained_layout=True)
    fig1.suptitle("Figure 1 - Data Overview & Pulse Structure", fontsize=14, fontweight="bold")

    # 1a. Stim channel full recording with detected pulses
    t_all = np.arange(len(stim_data)) / sfreq
    axes1[0].plot(t_all, stim_data, "k-", lw=0.5)
    axes1[0].plot(pulse_onsets / sfreq, stim_data[pulse_onsets], "rv",
                  ms=4, label=f"Pulse onsets ({len(pulse_onsets)})")
    axes1[0].set_ylabel("Stim (uV)")
    axes1[0].set_title(f"Stim Channel - 0.25 Hz pulses (ISI = {pulse_isi.mean():.3f} s, "
                       f"pulse width ~ 9 ms)")
    axes1[0].legend(loc="upper right")
    axes1[0].set_xlim(0, t_all[-1])

    # 1b. Zoom on a single pulse (stim + EEG)
    zoom_pk = valid_onsets[len(valid_onsets)//2]
    z0, z1 = zoom_pk - int(0.1*sfreq), zoom_pk + int(0.3*sfreq)
    tz = np.arange(z0, z1) / sfreq - zoom_pk/sfreq
    axes1[1].plot(tz*1000, stim_data[z0:z1], "r-", lw=1.5, label="stim")
    ax_twin = axes1[1].twinx()
    ax_twin.plot(tz*1000, raw_eeg_data[ref_idx, z0:z1], "b-", lw=0.8,
                 alpha=0.7, label=f"EEG ({ref_ch})")
    axes1[1].set_xlabel("Time from pulse (ms)")
    axes1[1].set_ylabel("Stim", color="red")
    ax_twin.set_ylabel(f"EEG {ref_ch} (uV)", color="blue")
    axes1[1].set_title("Zoom: Single Pulse + EEG")
    axes1[1].axvline(0, color="gray", ls="--", lw=1)
    lines1 = axes1[1].get_lines() + ax_twin.get_lines()
    axes1[1].legend(lines1, [l.get_label() for l in lines1], loc="upper right")

    # 1c. Ground-truth 10 Hz (first 2 s)
    show_n = int(2 * sfreq)
    t_show = np.arange(show_n) / sfreq
    axes1[2].plot(t_show, gt_data[:show_n], "gray", lw=0.6, alpha=0.5, label="GT raw")
    axes1[2].plot(t_show, gt_10hz[:show_n], "r-", lw=1.5, label="GT 8-12 Hz")
    axes1[2].set_ylabel("Ground Truth")
    axes1[2].set_title("Ground-Truth Channel - 10 Hz Beat Frequency Reference")
    axes1[2].legend()

    # 1d. PSD of stim, ground_truth, and one EEG channel
    for label, sig, color in [("stim", stim_data, "red"),
                               ("ground_truth", gt_data, "green"),
                               (ref_ch, raw_eeg_data[ref_idx], "blue")]:
        f, p = welch(sig, fs=sfreq, nperseg=int(sfreq*2))
        axes1[3].semilogy(f, p, color=color, lw=1.2, label=label)
    axes1[3].axvspan(8, 12, color="orange", alpha=0.15, label="SSD band")
    axes1[3].axvline(10, color="k", ls=":", lw=0.8)
    axes1[3].set_xlim(0, 50)
    axes1[3].set_xlabel("Frequency (Hz)")
    axes1[3].set_ylabel("PSD")
    axes1[3].set_title("Power Spectral Density")
    axes1[3].legend(ncol=2)

    fig1.savefig(str(OUTDIR / "fig1_data_overview.png"), dpi=200, bbox_inches="tight")
    print(f"  Saved -> {OUTDIR / 'fig1_data_overview.png'}")

    # ==================================================================== #
    #                   FIGURE 2: SSD DECOMPOSITION                        #
    # ==================================================================== #
    print("Plotting Figure 2: SSD decomposition ...")
    fig2 = plt.figure(figsize=(16, 12), constrained_layout=True)
    gs2 = fig2.add_gridspec(3, n_comp, height_ratios=[1, 1, 0.8])
    fig2.suptitle("Figure 2 - SSD Decomposition (8-12 Hz)", fontsize=14, fontweight="bold")

    # Row 1: Topographies
    for c in range(n_comp):
        ax = fig2.add_subplot(gs2[0, c])
        if patterns is not None:
            try:
                mne.viz.plot_topomap(patterns[:, c], raw_eeg.info, axes=ax, show=False)
            except Exception:
                ax.text(0.5, 0.5, "N/A", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"Comp {c}\nlambda = {evals[c]:.3f}", fontsize=10)

    # Row 2: PSD of each component
    for c in range(n_comp):
        ax = fig2.add_subplot(gs2[1, c])
        f_c, p_c = welch(all_comp_ts[c], fs=sfreq, nperseg=int(sfreq*2))
        ax.semilogy(f_c, p_c, "b-", lw=1)
        ax.axvspan(8, 12, color="orange", alpha=0.2)
        ax.set_xlim(0, 30)
        ax.set_xlabel("Hz")
        if c == 0:
            ax.set_ylabel("PSD")
        ax.set_title(f"Comp {c} PSD", fontsize=10)

    # Row 3, left: Eigenvalue bar chart
    ax_bar = fig2.add_subplot(gs2[2, :n_comp//2])
    colors = ["steelblue" if e >= 1.0 else "lightcoral" for e in evals]
    ax_bar.bar(range(n_comp), evals, color=colors, edgecolor="navy")
    ax_bar.axhline(1.0, color="k", ls="--", lw=1, label="lambda=1 (signal=noise)")
    ax_bar.set_xlabel("Component")
    ax_bar.set_ylabel("Eigenvalue")
    ax_bar.set_title("Eigenvalue Spectrum")
    ax_bar.legend()

    # Row 3, right: SSD vs best raw channel PSD
    ax_cmp = fig2.add_subplot(gs2[2, n_comp//2:])
    f_ssd, p_ssd = welch(ssd_10hz, fs=sfreq, nperseg=int(sfreq*2))
    f_ch, p_ch = welch(raw_eeg_data[ref_idx], fs=sfreq, nperseg=int(sfreq*2))
    ax_cmp.semilogy(f_ssd, p_ssd / p_ssd.max(), "b-", lw=1.5, label=f"SSD comp {best}")
    ax_cmp.semilogy(f_ch, p_ch / p_ch.max(), "gray", lw=1, alpha=0.7, label=f"Raw {ref_ch}")
    ax_cmp.axvspan(8, 12, color="orange", alpha=0.15)
    ax_cmp.set_xlim(0, 30)
    ax_cmp.set_xlabel("Hz")
    ax_cmp.set_ylabel("Normalized PSD")
    ax_cmp.set_title(f"SSD comp {best} vs {ref_ch}")
    ax_cmp.legend()

    fig2.savefig(str(OUTDIR / "fig2_ssd_decomposition.png"), dpi=200, bbox_inches="tight")
    print(f"  Saved -> {OUTDIR / 'fig2_ssd_decomposition.png'}")

    # ==================================================================== #
    #         FIGURE 3: PULSE-LOCKED TIME COURSE & TIME-FREQUENCY          #
    # ==================================================================== #
    print("Plotting Figure 3: Pulse-locked analysis ...")
    fig3, axes3 = plt.subplots(3, 2, figsize=(16, 14), constrained_layout=True)
    fig3.suptitle(f"Figure 3 - Pulse-Locked Time Courses  "
                  f"({n_trials} pulses, 0.25 Hz)",
                  fontsize=14, fontweight="bold")

    # 3a. Single-trial SSD 10 Hz (image plot)
    ax = axes3[0, 0]
    vmax = np.percentile(np.abs(ssd_epochs), 95)
    ax.imshow(ssd_epochs, aspect="auto", cmap="RdBu_r",
              extent=[t_epoch[0], t_epoch[-1], n_trials, 0],
              vmin=-vmax, vmax=vmax)
    ax.axvline(0, color="k", ls="--", lw=1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Trial")
    ax.set_title("Single-Trial SSD 10 Hz Source")

    # 3b. Mean SSD 10 Hz +/- SEM (ERP-like)
    ax = axes3[0, 1]
    mean_ssd = ssd_epochs.mean(axis=0)
    sem_ssd  = ssd_epochs.std(axis=0) / np.sqrt(n_trials)
    ax.fill_between(t_epoch, mean_ssd - sem_ssd, mean_ssd + sem_ssd,
                    color="steelblue", alpha=0.3)
    ax.plot(t_epoch, mean_ssd, "b-", lw=2, label="SSD 10 Hz mean")
    ax.axvline(0, color="red", ls="--", lw=1.5, label="Pulse onset")
    ax.axhline(0, color="gray", ls="-", lw=0.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_title("Mean SSD 10 Hz Source +/- SEM")
    ax.legend()

    # 3c. Mean stim-locked ground_truth
    ax = axes3[1, 0]
    gt_mean = gt_epochs.mean(axis=0)
    gt_sem  = gt_epochs.std(axis=0) / np.sqrt(n_trials)
    ax.fill_between(t_epoch, gt_mean - gt_sem, gt_mean + gt_sem,
                    color="green", alpha=0.3)
    ax.plot(t_epoch, gt_mean, "g-", lw=2, label="GT 10 Hz mean")
    ax.axvline(0, color="red", ls="--", lw=1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_title("Mean Ground-Truth 10 Hz at Pulse")
    ax.legend()

    # 3d. Mean raw EEG + stim overlay
    ax = axes3[1, 1]
    eeg_mean = eeg_epochs_ref.mean(axis=0)
    stim_mean = stim_epochs.mean(axis=0)
    ax.plot(t_epoch, eeg_mean, "b-", lw=1.5, label=f"EEG {ref_ch} mean")
    ax_tw2 = ax.twinx()
    ax_tw2.plot(t_epoch, stim_mean, "r-", lw=1, alpha=0.7, label="Stim mean")
    ax.axvline(0, color="gray", ls="--", lw=1)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(f"EEG {ref_ch} (uV)", color="blue")
    ax_tw2.set_ylabel("Stim", color="red")
    ax.set_title(f"Mean Raw EEG ({ref_ch}) + Stim at Pulse")
    lines_3d = ax.get_lines() + ax_tw2.get_lines()
    ax.legend(lines_3d, [l.get_label() for l in lines_3d])

    # 3e. Envelope modulation (10 Hz amplitude around pulses)
    ax = axes3[2, 0]
    ax.plot(t_epoch, env_mean, "b-", lw=2, label="Mean 10 Hz envelope")
    ax.axvline(0, color="red", ls="--", lw=1.5, label="Pulse onset")
    ax.axhspan(env_pre * 0.95, env_pre * 1.05, color="gray", alpha=0.2,
               label=f"Pre baseline ({env_pre:.2e})")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("10 Hz Envelope")
    ax.set_title("10 Hz Amplitude Modulation by Pulse")
    ax.legend(fontsize=9)

    # 3f. Inter-trial phase coherence (ITPC) over time
    ax = axes3[2, 1]
    ax.plot(t_epoch, itpc, "b-", lw=2)
    ax.axvline(0, color="red", ls="--", lw=1.5, label="Pulse onset")
    ax.axhline(itpc[:pre_n].mean(), color="gray", ls=":", lw=1,
               label=f"Pre baseline = {itpc[:pre_n].mean():.3f}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("ITPC")
    ax.set_ylim(0, max(0.2, itpc.max() * 1.2))
    ax.set_title("Inter-Trial Phase Coherence (10 Hz)")
    ax.legend()

    fig3.savefig(str(OUTDIR / "fig3_pulse_locked.png"), dpi=200, bbox_inches="tight")
    print(f"  Saved -> {OUTDIR / 'fig3_pulse_locked.png'}")

    # ==================================================================== #
    #                 FIGURE 4: PHASE SYNCHRONIZATION                      #
    # ==================================================================== #
    print("Plotting Figure 4: Phase synchronization ...")
    fig4 = plt.figure(figsize=(16, 10), constrained_layout=True)
    gs4 = fig4.add_gridspec(2, 3)
    fig4.suptitle("Figure 4 - Phase Synchronization Analysis",
                  fontsize=14, fontweight="bold")

    # 4a. Polar histogram - SSD phase at pulse onset
    ax = fig4.add_subplot(gs4[0, 0], projection="polar")
    ax.hist(phases_at_onset, bins=36, density=True,
            color="steelblue", alpha=0.75, edgecolor="white", lw=0.4)
    mean_ang = np.angle(np.mean(np.exp(1j * phases_at_onset)))
    ax.annotate("", xy=(mean_ang, ax.get_ylim()[1]*0.8), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="red", lw=2.5))
    ax.set_title(f"SSD Phase at Pulse Onset\n"
                 f"PLV = {plv_onset:.3f}, p = {p_ray:.2e}",
                 pad=18, fontweight="bold", fontsize=10)

    # 4b. Polar histogram - SSD phase at 50 ms after pulse
    post50_idx = onset_idx + int(0.05 * sfreq)
    phases_50ms = ssd_phase_epochs[:, post50_idx]
    plv_50ms = np.abs(np.mean(np.exp(1j * phases_50ms)))
    ax = fig4.add_subplot(gs4[0, 1], projection="polar")
    ax.hist(phases_50ms, bins=36, density=True,
            color="orange", alpha=0.75, edgecolor="white", lw=0.4)
    mean_50 = np.angle(np.mean(np.exp(1j * phases_50ms)))
    ax.annotate("", xy=(mean_50, ax.get_ylim()[1]*0.8), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="red", lw=2.5))
    ax.set_title(f"SSD Phase 50 ms post-pulse\nPLV = {plv_50ms:.3f}",
                 pad=18, fontweight="bold", fontsize=10)

    # 4c. Polar histogram - SSD phase at 100 ms after pulse
    post100_idx = onset_idx + int(0.1 * sfreq)
    phases_100ms = ssd_phase_epochs[:, post100_idx]
    plv_100ms = np.abs(np.mean(np.exp(1j * phases_100ms)))
    ax = fig4.add_subplot(gs4[0, 2], projection="polar")
    ax.hist(phases_100ms, bins=36, density=True,
            color="salmon", alpha=0.75, edgecolor="white", lw=0.4)
    mean_100 = np.angle(np.mean(np.exp(1j * phases_100ms)))
    ax.annotate("", xy=(mean_100, ax.get_ylim()[1]*0.8), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color="red", lw=2.5))
    ax.set_title(f"SSD Phase 100 ms post-pulse\nPLV = {plv_100ms:.3f}",
                 pad=18, fontweight="bold", fontsize=10)

    # 4d. PLV as function of time lag from pulse
    ax = fig4.add_subplot(gs4[1, 0])
    lags_ms = np.arange(-200, 500, 5)
    plv_lag = np.zeros(len(lags_ms))
    for li, lag in enumerate(lags_ms):
        lag_idx = onset_idx + int(lag / 1000 * sfreq)
        if 0 <= lag_idx < ssd_phase_epochs.shape[1]:
            plv_lag[li] = np.abs(np.mean(np.exp(1j * ssd_phase_epochs[:, lag_idx])))
    ax.plot(lags_ms, plv_lag, "b-", lw=1.5)
    ax.axvline(0, color="red", ls="--", lw=1, label="Pulse onset")
    ax.axhline(1/np.sqrt(n_trials), color="gray", ls=":", lw=1,
               label=f"Chance ({1/np.sqrt(n_trials):.3f})")
    ax.set_xlabel("Lag from pulse (ms)")
    ax.set_ylabel("PLV")
    ax.set_title("PLV vs Time Lag")
    ax.legend()

    # 4e. ITPC time-course (zoomed)
    ax = fig4.add_subplot(gs4[1, 1])
    zoom_mask = (t_epoch >= -0.5) & (t_epoch <= 1.0)
    ax.plot(t_epoch[zoom_mask], itpc[zoom_mask], "b-", lw=2)
    ax.axvline(0, color="red", ls="--", lw=1.5, label="Pulse onset")
    ax.fill_between(t_epoch[zoom_mask],
                    itpc[:pre_n].mean() - itpc[:pre_n].std(),
                    itpc[:pre_n].mean() + itpc[:pre_n].std(),
                    color="gray", alpha=0.2, label="Pre +/- 1 SD")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("ITPC")
    ax.set_title("ITPC Zoomed (-0.5 to 1 s)")
    ax.legend()

    # 4f. Summary text
    ax = fig4.add_subplot(gs4[1, 2])
    ax.axis("off")
    summary_text = (
        f"SYNCHRONIZATION SUMMARY\n"
        f"{'_' * 35}\n"
        f"Pulse rate:        0.25 Hz (4 s)\n"
        f"Pulse duration:    ~9 ms\n"
        f"Trials:            {n_trials}\n"
        f"SSD band:          {signal_band[0]}-{signal_band[1]} Hz\n"
        f"Best eigenvalue:   {evals[best]:.3f}\n\n"
        f"PLV at onset:      {plv_onset:.4f}\n"
        f"PLV at +50 ms:     {plv_50ms:.4f}\n"
        f"PLV at +100 ms:    {plv_100ms:.4f}\n"
        f"Rayleigh p:        {p_ray:.2e}\n\n"
        f"ITPC pre (-1-0s):  {itpc_pre:.4f}\n"
        f"ITPC post (0-0.5): {itpc_post:.4f}\n\n"
        f"Envelope pre:      {env_pre:.2e}\n"
        f"Envelope post:     {env_post:.2e}\n"
        f"Env ratio:         {env_post/env_pre:.3f}\n\n"
        f"Cross-PLV (global):{plv_global:.4f}"
    )
    ax.text(0.05, 0.95, summary_text, transform=ax.transAxes,
            fontsize=10, va="top", ha="left", family="monospace",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    fig4.savefig(str(OUTDIR / "fig4_phase_synchronization.png"), dpi=200, bbox_inches="tight")
    print(f"  Saved -> {OUTDIR / 'fig4_phase_synchronization.png'}")

    # ==================================================================== #
    #                 FIGURE 5: BASELINE COMPARISON (if available)          #
    # ==================================================================== #
    if raw_base_eeg is not None:
        print("Plotting Figure 5: STIM vs Baseline comparison ...")
        fig5, axes5 = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
        fig5.suptitle("Figure 5 - STIM vs Baseline Comparison",
                      fontsize=14, fontweight="bold")

        # Apply same SSD filter to baseline
        raw_base_bp = raw_base_eeg.copy().filter(signal_band[0], signal_band[1], verbose=False)
        base_data_bp = raw_base_bp.get_data()
        ssd_base = filters[best] @ base_data_bp

        # 5a. PSD comparison: SSD source
        f_s, p_s = welch(ssd_10hz, fs=sfreq, nperseg=int(sfreq*2))
        f_b, p_b = welch(ssd_base, fs=sfreq, nperseg=int(sfreq*2))
        axes5[0, 0].semilogy(f_s, p_s, "r-", lw=1.5, label="STIM")
        axes5[0, 0].semilogy(f_b, p_b, "b-", lw=1.5, label="Baseline")
        axes5[0, 0].axvspan(8, 12, color="orange", alpha=0.15)
        axes5[0, 0].set_xlim(0, 30)
        axes5[0, 0].set_xlabel("Hz")
        axes5[0, 0].set_ylabel("PSD")
        axes5[0, 0].set_title(f"SSD Comp {best} PSD: STIM vs Baseline")
        axes5[0, 0].legend()

        # 5b. PSD comparison: raw channel
        ref_base_idx = raw_base_eeg.ch_names.index(ref_ch)
        base_raw_data = raw_base_eeg.get_data()
        f_sr, p_sr = welch(raw_eeg_data[ref_idx], fs=sfreq, nperseg=int(sfreq*2))
        f_br, p_br = welch(base_raw_data[ref_base_idx], fs=sfreq, nperseg=int(sfreq*2))
        axes5[0, 1].semilogy(f_sr, p_sr, "r-", lw=1.5, label="STIM")
        axes5[0, 1].semilogy(f_br, p_br, "b-", lw=1.5, label="Baseline")
        axes5[0, 1].axvspan(8, 12, color="orange", alpha=0.15)
        axes5[0, 1].set_xlim(0, 30)
        axes5[0, 1].set_xlabel("Hz")
        axes5[0, 1].set_ylabel("PSD")
        axes5[0, 1].set_title(f"Raw {ref_ch} PSD: STIM vs Baseline")
        axes5[0, 1].legend()

        # 5c. Time domain comparison (first 2 s)
        tn = int(2 * sfreq)
        t2 = np.arange(tn) / sfreq
        axes5[1, 0].plot(t2, ssd_10hz[:tn], "r-", lw=1, label="STIM")
        axes5[1, 0].plot(t2, ssd_base[:tn], "b-", lw=1, alpha=0.7, label="Baseline")
        axes5[1, 0].set_xlabel("Time (s)")
        axes5[1, 0].set_ylabel("SSD source")
        axes5[1, 0].set_title(f"SSD 10 Hz Source (first 2 s)")
        axes5[1, 0].legend()

        # 5d. Envelope distributions
        ssd_env_stim = np.abs(hilbert(ssd_10hz))
        ssd_env_base = np.abs(hilbert(ssd_base))
        axes5[1, 1].hist(ssd_env_stim, bins=80, density=True, alpha=0.5,
                         color="red", label=f"STIM (mean={ssd_env_stim.mean():.2e})")
        axes5[1, 1].hist(ssd_env_base, bins=80, density=True, alpha=0.5,
                         color="blue", label=f"Base (mean={ssd_env_base.mean():.2e})")
        axes5[1, 1].set_xlabel("10 Hz Envelope")
        axes5[1, 1].set_ylabel("Density")
        axes5[1, 1].set_title("10 Hz Envelope Distribution")
        axes5[1, 1].legend()

        fig5.savefig(str(OUTDIR / "fig5_stim_vs_baseline.png"), dpi=200, bbox_inches="tight")
        print(f"  Saved -> {OUTDIR / 'fig5_stim_vs_baseline.png'}")

    # Show all
    plt.show()
    print("\nDone. All figures saved in:", OUTDIR)


if __name__ == "__main__":
    main()
