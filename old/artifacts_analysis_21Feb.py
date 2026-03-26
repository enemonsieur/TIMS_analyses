import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from pathlib import Path
from scipy.signal import butter, sosfiltfilt, iirnotch, filtfilt, hilbert, welch, coherence, find_peaks
import mne
import pandas as pd
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)

# ---------------- paths ----------------
base_vhdr = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-baseline-run01.vhdr"  # baseline (no stim)
stim_vhdr = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-stim-pulse-10hz-GT-run02.vhdr"  # stimulation run (≈10s IOI)
outdir = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS") / "exp02_subspace_separation_run02_10s"
outdir.mkdir(exist_ok=True, parents=True)

BAD_CHANNELS = ['T7', 'TP9', 'Pz', 'P3', 'P7', 'O1', 'Oz', 'O2', 'P4', 'P8',
                'TP10', 'T8', 'FT10', 'F7', 'CP5', 'CP6', 'CP2', 'FC5', 'FT9', 'C3']

# ---------------- helpers ----------------
def notch_iir(x, fs, f0=50.0, q=30.0):
    b, a = iirnotch(w0=f0, Q=q, fs=fs)
    return filtfilt(b, a, x, axis=-1)

def bandpass(x, fs, fmin, fmax, order=4):
    sos = butter(order, [fmin, fmax], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, x, axis=-1)

def welch_psd(x, fs, nper=4096):
    nper = int(min(nper, len(x)))
    return welch(x, fs=fs, nperseg=nper)

def coh_band(x, y, fs, fmin, fmax, nper=4096):
    f, cxy = coherence(x, y, fs=fs, nperseg=min(nper, len(x)))
    m = (f>=fmin) & (f<=fmax)
    return float(np.mean(cxy[m])) if np.any(m) else float(cxy[np.argmin(np.abs(f-(fmin+fmax)/2))])

def coh10(x, y, fs, bw=0.5):
    return coh_band(x, y, fs, 10-bw, 10+bw)

def plv_phase(xa, ya):
    d = np.angle(xa) - np.angle(ya)
    return float(np.abs(np.mean(np.exp(1j*d))))

def proj_from_W(W):
    return W.T @ np.linalg.pinv(W @ W.T) @ W

def epoch_1d(x, onsets, fs, pre_s, post_s):
    pre = int(pre_s*fs); post = int(post_s*fs)
    valid = onsets[(onsets>=pre) & (onsets < len(x)-post)]
    E = np.stack([x[o-pre:o+post] for o in valid], axis=0) if len(valid) else np.zeros((0, pre+post))
    t = np.arange(-pre, post)/fs
    return E, t, valid

def db_env(x, eps=1e-12):
    return 20*np.log10(np.abs(hilbert(x)) + eps)

def snr10_db(x, fs):
    f, p = welch_psd(x, fs, nper=4096)
    def bandpow(a,b):
        m=(f>=a)&(f<=b)
        return float(np.trapz(p[m], f[m])) if np.any(m) else 0.0
    sig = bandpow(9,11)
    noi = bandpow(3,8) + bandpow(12,22)
    return 10*np.log10((sig+1e-30)/(noi+1e-30))

def safe_label_list(chs):
    return chs if len(chs) <= 32 else []

def rms(sig):
    return float(np.sqrt(np.mean(sig**2))) if sig.size else np.nan

def pct_recovery(clean, raw, base):
    denom = base - raw
    return 100.0 * (clean - raw) / denom if abs(denom) > 1e-12 else np.nan

# ---------------- load ----------------
stim_raw = mne.io.read_raw_brainvision(stim_vhdr, preload=True, verbose=False)
base_raw = mne.io.read_raw_brainvision(base_vhdr, preload=True, verbose=False)
sfreq = float(stim_raw.info["sfreq"])

gt_ch   = "ground_truth" if "ground_truth" in stim_raw.ch_names else [c for c in stim_raw.ch_names if "truth" in c.lower() or c.lower()=="gt"][0]
stim_ch = "stim" if "stim" in stim_raw.ch_names else [c for c in stim_raw.ch_names if "stim" in c.lower()][0]

all_eeg = [c for c in stim_raw.ch_names if c not in (gt_ch, stim_ch) and not c.upper().startswith("STI")]
eeg_chs = [c for c in all_eeg if c not in BAD_CHANNELS]  # <-- remove bad channels
removed = [c for c in all_eeg if c in BAD_CHANNELS]

ref_ch  = "Cz" if "Cz" in eeg_chs else eeg_chs[0]
ref_idx = eeg_chs.index(ref_ch)

X_stim = stim_raw.copy().pick(eeg_chs).get_data()
X_base = base_raw.copy().pick(eeg_chs).get_data()
stim_marker = stim_raw.copy().pick([stim_ch]).get_data()[0]
gt_stim     = stim_raw.copy().pick([gt_ch]).get_data()[0]
gt_base     = base_raw.copy().pick([gt_ch]).get_data()[0]
n_t = X_stim.shape[1]

# ---------------- Step 0: robust pulse onset detection (works for ~10s IOI) ----------------
env = np.abs(hilbert(stim_marker))
prom = max(3*np.std(env), np.percentile(env,95) - np.percentile(env,50))
cand, _ = find_peaks(env, prominence=prom, distance=int(0.05*sfreq))
if len(cand) < 5:
    cand, _ = find_peaks(env, prominence=np.std(env), distance=int(0.02*sfreq))
cand = np.array(cand, dtype=int)

# estimate IOI from candidates (ignore tiny within-pulse gaps)
if len(cand) > 2:
    d = np.diff(cand)/sfreq
    d2 = d[d>0.5]
    med_guess = float(np.median(d2)) if len(d2) else 10.0
else:
    med_guess = 10.0

# enforce one onset per pulse (refractory)
min_dist = int(max(0.6*med_guess*sfreq, 1.5*sfreq))
kept=[]; last=-10**9
for idx in cand:
    if idx-last >= min_dist:
        kept.append(idx); last=idx
    else:
        if env[idx] > env[last]:
            kept[-1]=idx; last=idx
onsets = np.array(kept, dtype=int)
ioi = np.diff(onsets)/sfreq if len(onsets)>1 else np.array([])

# masks: ON 0–1.00s, END-JUMP 0.90–1.05s, OFF excludes 0–1.05s
mask_on  = np.zeros(n_t, dtype=bool)
mask_end = np.zeros(n_t, dtype=bool)
mask_off = np.ones(n_t, dtype=bool)
for o in onsets:
    mask_on[o:min(n_t, o+int(1.00*sfreq))] = True
    mask_end[min(n_t, o+int(0.90*sfreq)):min(n_t, o+int(1.05*sfreq))] = True
    mask_off[o:min(n_t, o+int(1.05*sfreq))] = False

# ---------------- preprocess ----------------
X_stim_bb = bandpass(notch_iir(X_stim, sfreq), sfreq, 0.5, 45)
X_base_bb = bandpass(notch_iir(X_base, sfreq), sfreq, 0.5, 45)
X_stim_10 = bandpass(notch_iir(X_stim, sfreq), sfreq, 8, 12)
X_base_10 = bandpass(notch_iir(X_base, sfreq), sfreq, 8, 12)
gt_stim_10 = bandpass(notch_iir(gt_stim, sfreq), sfreq, 8, 12)
gt_base_10 = bandpass(notch_iir(gt_base, sfreq), sfreq, 8, 12)

cz_base_bb = X_base_bb[ref_idx]
cz_stim_bb = X_stim_bb[ref_idx]

# =========================
# From here: keep your pipeline unchanged
# (PSD baseline vs OFF vs ON, GT-SSD on baseline+OFF, artifact subspace ON vs OFF,
# subtraction + GT-protected variant, metrics + percent recovery, report + figures)
# =========================

# --- you can literally paste the rest of your run01 script below ---
# Only two *required* edits were:
#   1) stim_vhdr -> run02
#   2) eeg_chs excludes BAD_CHANNELS
#   3) onset detection refractory as above (replaces distance=int(0.12*sfreq))

print("Detected pulses:", len(onsets), "IOI median:", (np.median(ioi) if len(ioi) else np.nan))
print("Removed bad channels:", removed)

# =============== Step 0: figures ================
T = np.arange(n_t) / sfreq
fig, ax = plt.subplots(figsize=(14, 4), constrained_layout=True)
ax.plot(T, stim_marker, lw=0.8)
ax.scatter(onsets / sfreq, stim_marker[onsets], s=18, color='r', label='detected onsets')
zoom_end = min(T[-1], (onsets[0] / sfreq + 2 * float(np.median(ioi))) if len(ioi) else 30)
ax.set_xlim(0, zoom_end)
ax.set_title('Step 0: stim marker with detected pulse onsets (zoom)')
ax.set_xlabel('Time (s)'); ax.legend()
fig.savefig(outdir / 'fig0a_stim_marker_onsets.png', dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
if len(ioi):
    ax.hist(ioi, bins=20); ax.axvline(np.median(ioi), color='k', lw=1)
ax.set_title(f'Step 0: IOI distribution (n={len(ioi)})'); ax.set_xlabel('IOI (s)')
fig.savefig(outdir / 'fig0b_ioi_hist.png', dpi=200); plt.close(fig)

summary = {'pulses': int(len(onsets)), 'ioi_median_s': float(np.median(ioi)) if len(ioi) else np.nan,
           'ioi_min_s': float(np.min(ioi)) if len(ioi) else np.nan,
           'ioi_max_s': float(np.max(ioi)) if len(ioi) else np.nan}
pd.DataFrame([summary]).to_csv(outdir / 'step0_pulse_summary.csv', index=False)

# =============== Step 1: waveform + PSD ================
E_raw, t_ep, _ = epoch_1d(cz_stim_bb, onsets, sfreq, 0.25, 2.0)
E_base, t_ep2, _ = epoch_1d(cz_base_bb, onsets, sfreq, 0.25, 2.0)
fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
if E_raw.shape[0]:
    m = E_raw.mean(0); s = E_raw.std(0)
    ax.plot(t_ep, m, label='Stim Cz raw mean'); ax.fill_between(t_ep, m-s, m+s, alpha=0.2)
if E_base.shape[0]:
    ax.plot(t_ep2, E_base.mean(0), label='Baseline Cz mean', lw=1.2)
ax.axvspan(0, 1.0, alpha=0.08); ax.axvspan(0.90, 1.05, alpha=0.08)
ax.set_title('Step 1: Pulse-aligned broadband waveform (mean ± SD)'); ax.set_xlabel('Time rel onset (s)'); ax.legend()
fig.savefig(outdir / 'fig1a_pulse_aligned_waveform_bb.png', dpi=200); plt.close(fig)

Twin = min(float(np.median(ioi)) if len(ioi) else 10.0, 10.0)
post = int(Twin * sfreq)
valid_post = onsets[onsets < n_t - post]

def pulse_db_stats(x):
    tt = np.arange(post) / sfreq
    if len(valid_post) == 0:
        return tt, np.zeros_like(tt), np.zeros_like(tt), np.zeros_like(tt)
    E = np.stack([db_env(x[o:o + post]) for o in valid_post], axis=0)
    return tt, np.median(E, 0), np.percentile(E, 25, 0), np.percentile(E, 75, 0)

tt, rm, r25, r75 = pulse_db_stats(cz_stim_bb)
fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
ax.plot(tt, rm, label='Stim Cz raw (median dB env)'); ax.fill_between(tt, r25, r75, alpha=0.15)
ax.axvspan(0, 1.0, color='k', alpha=0.06); ax.axvspan(0.90, 1.05, color='r', alpha=0.06)
ax.set_title(f'Step 1: Pulse-aligned envelope (dB) over IOI~{Twin:.2f}s'); ax.set_xlabel('Time rel onset (s)'); ax.legend()
fig.savefig(outdir / 'fig1b_db_envelope_over_ioi_raw.png', dpi=200); plt.close(fig)

f_b, p_b = welch_psd(cz_base_bb, sfreq)
f_off, p_off = welch_psd(cz_stim_bb[mask_off], sfreq)
f_on, p_on = welch_psd(cz_stim_bb[mask_on], sfreq)
fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
ax.semilogy(f_b, p_b, label='Baseline'); ax.semilogy(f_off, p_off, label='Stim-OFF raw')
ax.semilogy(f_on, p_on, label='Stim-ON raw')
ax.set_xlim(0, 45); ax.set_xlabel('Hz'); ax.set_ylabel('PSD')
ax.set_title(f'Step 1 PSD (Cz) | pulses={len(onsets)} IOI~{summary["ioi_median_s"]:.2f}s'); ax.legend()
fig.savefig(outdir / 'fig1c_psd_baseline_off_on_raw.png', dpi=200); plt.close(fig)

# =============== Step 2: GT-SSD ================
X_train_10  = np.concatenate([X_base_10, X_stim_10[:, mask_off]], axis=1)
Xnoi_base   = bandpass(notch_iir(X_base, sfreq), sfreq, 3, 22)
Xnoi_off    = bandpass(notch_iir(X_stim, sfreq), sfreq, 3, 22)[:, mask_off]
Xnoi_train  = np.concatenate([Xnoi_base, Xnoi_off], axis=1)
b10, a10    = iirnotch(w0=10.0, Q=10.0, fs=sfreq)
Xnoi_train  = filtfilt(b10, a10, Xnoi_train, axis=-1)
Cs = np.cov(X_train_10); Cn = np.cov(Xnoi_train)
evals_gt, evecs_gt = np.linalg.eig(np.linalg.pinv(Cn) @ Cs)
idx = np.argsort(np.real(evals_gt))[::-1]
evals_gt = np.real(evals_gt[idx]); evecs_gt = np.real(evecs_gt[:, idx])
k_gt = min(6, X_stim.shape[0])
W_gt = evecs_gt[:, :k_gt].T
Sgt_10 = W_gt @ X_stim_10; Sgt_bb = W_gt @ X_stim_bb

scores_gt = []
for k in range(k_gt):
    scores_gt.append((
        k,
        coh10(Sgt_10[k][mask_off], gt_stim_10[mask_off], sfreq),
        plv_phase(hilbert(Sgt_10[k][mask_off]), hilbert(gt_stim_10[mask_off])),
        snr10_db(Sgt_10[k][mask_off], sfreq),
        float(np.sqrt(np.mean(Sgt_bb[k][mask_on]**2)) / (np.sqrt(np.mean(Sgt_bb[k][mask_off]**2)) + 1e-12)),
    ))
scores_gt_sorted = sorted(scores_gt, key=lambda t: (t[1] + 0.5*t[2] + 0.05*t[3]) / (t[4] + 1e-3), reverse=True)
best_gt = scores_gt_sorted[0][0]

fig = plt.figure(figsize=(18, 7), constrained_layout=True)
gs = fig.add_gridspec(2, k_gt, height_ratios=[1, 1])
for j in range(k_gt):
    coh_off_, plv_off_, snr_, ar_ = [(c, p, s, a) for (k, c, p, s, a) in scores_gt if k == j][0]
    axw = fig.add_subplot(gs[0, j])
    axw.plot(W_gt[j]); axw.axhline(0, lw=0.8)
    axw.set_title(f'GT-C{j+1} λ={evals_gt[j]:.3f}\ncoh={coh_off_:.3f} plv={plv_off_:.3f}\nSNR={snr_:.1f}dB art={ar_:.2f}')
    axw.set_xticks(range(len(eeg_chs)))
    axw.set_xticklabels(safe_label_list(eeg_chs), rotation=90, fontsize=7)
    axp = fig.add_subplot(gs[1, j])
    f, pow_ = welch_psd(Sgt_bb[j][mask_off], sfreq)
    axp.plot(f, 10*np.log10(pow_ + 1e-30)); axp.axvspan(9, 11, alpha=0.2); axp.set_xlim(1, 35); axp.grid(True, alpha=0.2)
fig.suptitle('Step 2: GT subspace (SSD on baseline+stim-OFF) | weights + PSD (stim-OFF)')
fig.savefig(outdir / 'fig2a_gt_components_weights_psd.png', dpi=200); plt.close(fig)

cohs_ = np.array([t[1] for t in scores_gt]); ars_ = np.array([t[4] for t in scores_gt])
fig, ax = plt.subplots(figsize=(6, 5), constrained_layout=True)
ax.scatter(ars_, cohs_)
for (k, c, p, sn, ar) in scores_gt:
    ax.text(ar, c, f'C{k+1}', fontsize=9)
ax.set_xlabel('Artifact ratio RMS(ON)/RMS(OFF)'); ax.set_ylabel('Coherence with GT @10Hz (OFF)')
ax.set_title('Step 2: Coherence vs artifact ratio (Pareto)')
fig.savefig(outdir / 'fig2b_coh_vs_artifact_ratio.png', dpi=200); plt.close(fig)

# =============== Step 3: artifact subspace ================
Con  = np.cov(X_stim_bb[:, mask_on]); Coff = np.cov(X_stim_bb[:, mask_off])
evals_art, evecs_art = np.linalg.eig(np.linalg.pinv(Coff) @ Con)
idx = np.argsort(np.real(evals_art))[::-1]
evals_art = np.real(evals_art[idx]); evecs_art = np.real(evecs_art[:, idx])
k_art = min(8, X_stim.shape[0])
W_art = evecs_art[:, :k_art].T; Sart_bb = W_art @ X_stim_bb

fig = plt.figure(figsize=(18, 7), constrained_layout=True)
gs = fig.add_gridspec(2, k_art, height_ratios=[1, 1])
for j in range(k_art):
    E, t_ep_j, _ = epoch_1d(Sart_bb[j], onsets, sfreq, 0.25, 2.0)
    ax = fig.add_subplot(gs[0, j])
    if E.shape[0]: ax.plot(t_ep_j, E.mean(0))
    ax.axvspan(0, 1.0, alpha=0.08); ax.axvspan(0.90, 1.05, alpha=0.08)
    ar = float(np.sqrt(np.mean(Sart_bb[j][mask_on]**2)) / (np.sqrt(np.mean(Sart_bb[j][mask_off]**2)) + 1e-12))
    ax.set_title(f'ART-C{j+1} λ={evals_art[j]:.2f}\nRMS ratio={ar:.1f}')
    axp = fig.add_subplot(gs[1, j])
    f, pow_ = welch_psd(Sart_bb[j][mask_on], sfreq)
    axp.plot(f, 10*np.log10(pow_ + 1e-30)); axp.set_xlim(1, 45); axp.grid(True, alpha=0.2)
fig.suptitle('Step 3: Artifact subspace | pulse-locked mean + PSD(ON)')
fig.savefig(outdir / 'fig3_artifact_components_time_psd.png', dpi=200); plt.close(fig)

# =============== Step 4: cleaning ================
P_art = proj_from_W(W_art[:min(6, k_art)])
X_clean_bb = X_stim_bb - (P_art @ X_stim_bb)
P_gt = proj_from_W(W_gt[:min(3, k_gt)])
I_ = np.eye(P_gt.shape[0])
X_clean_bb_gtprot = X_stim_bb - ((I_ - P_gt) @ (P_art @ X_stim_bb))
X_clean_10       = bandpass(notch_iir(X_clean_bb, sfreq), sfreq, 8, 12)
X_clean_10_gtprot = bandpass(notch_iir(X_clean_bb_gtprot, sfreq), sfreq, 8, 12)
cz_clean_bb = X_clean_bb[ref_idx]; cz_clean_bb_gtprot = X_clean_bb_gtprot[ref_idx]

E_raw, t0, _ = epoch_1d(cz_stim_bb, onsets, sfreq, 0.25, 2.0)
E_cln, _, _  = epoch_1d(cz_clean_bb, onsets, sfreq, 0.25, 2.0)
E_cln2, _, _ = epoch_1d(cz_clean_bb_gtprot, onsets, sfreq, 0.25, 2.0)
fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
if E_raw.shape[0]:  ax.plot(t0, E_raw.mean(0), label='Stim Cz raw')
if E_cln.shape[0]:  ax.plot(t0, E_cln.mean(0), label='Cleaned Cz (art-sub)')
if E_cln2.shape[0]: ax.plot(t0, E_cln2.mean(0), label='Cleaned Cz (GT-protected)')
ax.axvspan(0, 1.0, alpha=0.07); ax.axvspan(0.90, 1.05, alpha=0.07)
ax.legend(); ax.set_title('Step 4: Pulse-locked morphology (broadband mean)')
fig.savefig(outdir / 'fig4a_pulselocked_morphology_raw_vs_clean.png', dpi=200); plt.close(fig)

_, cm, c25, c75 = pulse_db_stats(cz_clean_bb)
_, gm, g25, g75 = pulse_db_stats(cz_clean_bb_gtprot)
fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
ax.plot(tt, rm, label='Raw Cz'); ax.fill_between(tt, r25, r75, alpha=0.12)
ax.plot(tt, cm, label='Cleaned Cz (art-sub)'); ax.fill_between(tt, c25, c75, alpha=0.12)
ax.plot(tt, gm, label='Cleaned Cz (GT-protected)'); ax.fill_between(tt, g25, g75, alpha=0.12)
ax.axvspan(0, 1.0, color='k', alpha=0.06); ax.axvspan(0.90, 1.05, color='r', alpha=0.06)
ax.legend(); ax.set_title(f'Step 4: Pulse-aligned envelope (dB) | IOI~{Twin:.2f}s')
fig.savefig(outdir / 'fig4b_db_envelope_raw_vs_clean.png', dpi=200); plt.close(fig)

f_coff, p_coff = welch_psd(cz_clean_bb[mask_off], sfreq)
f_goff, p_goff = welch_psd(cz_clean_bb_gtprot[mask_off], sfreq)
fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
ax.semilogy(f_b, p_b, label='Baseline'); ax.semilogy(f_off, p_off, label='Stim-OFF raw')
ax.semilogy(f_coff, p_coff, label='Stim-OFF cleaned'); ax.semilogy(f_goff, p_goff, label='Stim-OFF cleaned (GT-prot)')
ax.set_xlim(0, 45); ax.legend(); ax.set_title('Step 4: PSD (OFF) baseline vs raw vs cleaned')
fig.savefig(outdir / 'fig4c_psd_off_baseline_raw_clean.png', dpi=200); plt.close(fig)

f_ron, p_ron = welch_psd(cz_stim_bb[mask_on], sfreq)
f_con, p_con = welch_psd(cz_clean_bb[mask_on], sfreq)
f_gon, p_gon = welch_psd(cz_clean_bb_gtprot[mask_on], sfreq)
fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
ax.semilogy(f_ron, p_ron, label='Stim-ON raw'); ax.semilogy(f_con, p_con, label='Stim-ON cleaned')
ax.semilogy(f_gon, p_gon, label='Stim-ON cleaned (GT-prot)')
ax.set_xlim(0, 45); ax.legend(); ax.set_title('Step 4: PSD (ON) raw vs cleaned')
fig.savefig(outdir / 'fig4d_psd_on_raw_clean.png', dpi=200); plt.close(fig)

# =============== Step 5: metrics ================
cz_raw_10 = X_stim_10[ref_idx]; cz_cln_10 = X_clean_10[ref_idx]; cz_gtp_10 = X_clean_10_gtprot[ref_idx]
best_gt_clean = (W_gt @ X_clean_10)[best_gt]; best_gt_gtp = (W_gt @ X_clean_10_gtprot)[best_gt]

coh_base_off = coh10(gt_base_10, X_base_10[ref_idx], sfreq)
coh_raw_off  = coh10(gt_stim_10[mask_off], cz_raw_10[mask_off], sfreq)
coh_cln_off  = coh10(gt_stim_10[mask_off], cz_cln_10[mask_off], sfreq)
coh_gtp_off  = coh10(gt_stim_10[mask_off], cz_gtp_10[mask_off], sfreq)
coh_gt_off   = coh10(gt_stim_10[mask_off], best_gt_clean[mask_off], sfreq)
coh_gt_gtp_off = coh10(gt_stim_10[mask_off], best_gt_gtp[mask_off], sfreq)

plv_base_off = plv_phase(hilbert(gt_base_10), hilbert(X_base_10[ref_idx]))
plv_raw_off  = plv_phase(hilbert(gt_stim_10[mask_off]), hilbert(cz_raw_10[mask_off]))
plv_cln_off  = plv_phase(hilbert(gt_stim_10[mask_off]), hilbert(cz_cln_10[mask_off]))
plv_gtp_off  = plv_phase(hilbert(gt_stim_10[mask_off]), hilbert(cz_gtp_10[mask_off]))
plv_gt_off   = plv_phase(hilbert(gt_stim_10[mask_off]), hilbert(best_gt_clean[mask_off]))
plv_gt_gtp_off = plv_phase(hilbert(gt_stim_10[mask_off]), hilbert(best_gt_gtp[mask_off]))

snr_base_off   = snr10_db(X_base_10[ref_idx], sfreq)
snr_raw_off    = snr10_db(cz_raw_10[mask_off], sfreq)
snr_cln_off    = snr10_db(cz_cln_10[mask_off], sfreq)
snr_gtp_off    = snr10_db(cz_gtp_10[mask_off], sfreq)
snr_gt_off     = snr10_db(best_gt_clean[mask_off], sfreq)
snr_gt_gtp_off = snr10_db(best_gt_gtp[mask_off], sfreq)

E_gt, t_ep, _ = epoch_1d(gt_stim_10, onsets, sfreq, 0.25, 2.0)
E_r,  _, _    = epoch_1d(cz_raw_10,     onsets, sfreq, 0.25, 2.0)
E_c,  _, _    = epoch_1d(cz_cln_10,     onsets, sfreq, 0.25, 2.0)
E_gp, _, _    = epoch_1d(cz_gtp_10,     onsets, sfreq, 0.25, 2.0)
E_g,  _, _    = epoch_1d(best_gt_clean, onsets, sfreq, 0.25, 2.0)
E_ggp,_, _    = epoch_1d(best_gt_gtp,   onsets, sfreq, 0.25, 2.0)
pm = (t_ep >= 1.05) & (t_ep <= 2.0)
cat = lambda E: E[:, pm].ravel() if E.shape[0] else np.array([])
coh_raw_post    = coh10(cat(E_gt), cat(E_r),   sfreq) if cat(E_gt).size else np.nan
coh_cln_post    = coh10(cat(E_gt), cat(E_c),   sfreq) if cat(E_gt).size else np.nan
coh_gtp_post    = coh10(cat(E_gt), cat(E_gp),  sfreq) if cat(E_gt).size else np.nan
coh_gt_post     = coh10(cat(E_gt), cat(E_g),   sfreq) if cat(E_gt).size else np.nan
coh_gt_gtp_post = coh10(cat(E_gt), cat(E_ggp), sfreq) if cat(E_gt).size else np.nan

rms_on_raw = rms(cz_stim_bb[mask_on]); rms_on_cln = rms(cz_clean_bb[mask_on]); rms_on_gtp = rms(cz_clean_bb_gtprot[mask_on])
rms_end_raw = rms(cz_stim_bb[mask_end]); rms_end_cln = rms(cz_clean_bb[mask_end]); rms_end_gtp = rms(cz_clean_bb_gtprot[mask_end])
on_red_cln = 100*(1 - rms_on_cln/(rms_on_raw+1e-30)); on_red_gtp = 100*(1 - rms_on_gtp/(rms_on_raw+1e-30))
end_red_cln = 100*(1 - rms_end_cln/(rms_end_raw+1e-30)); end_red_gtp = 100*(1 - rms_end_gtp/(rms_end_raw+1e-30))

pct_coh_cln = pct_recovery(coh_cln_off, coh_raw_off, coh_base_off)
pct_coh_gtp = pct_recovery(coh_gtp_off, coh_raw_off, coh_base_off)
pct_coh_gt  = pct_recovery(coh_gt_off,  coh_raw_off, coh_base_off)
pct_coh_gt_gtp = pct_recovery(coh_gt_gtp_off, coh_raw_off, coh_base_off)
pct_snr_cln = pct_recovery(snr_cln_off, snr_raw_off, snr_base_off)
pct_snr_gtp = pct_recovery(snr_gtp_off, snr_raw_off, snr_base_off)
pct_snr_gt  = pct_recovery(snr_gt_off,  snr_raw_off, snr_base_off)
pct_snr_gt_gtp = pct_recovery(snr_gt_gtp_off, snr_raw_off, snr_base_off)

labels = ['Cz raw', 'Cz clean', 'Cz GT-prot', f'GT-C{best_gt+1} clean', f'GT-C{best_gt+1} GT-prot']
coh_off_vals  = [coh_raw_off, coh_cln_off, coh_gtp_off, coh_gt_off, coh_gt_gtp_off]
coh_post_vals = [coh_raw_post, coh_cln_post, coh_gtp_post, coh_gt_post, coh_gt_gtp_post]
plv_off_vals  = [plv_raw_off, plv_cln_off, plv_gtp_off, plv_gt_off, plv_gt_gtp_off]
snr_off_vals  = [snr_raw_off, snr_cln_off, snr_gtp_off, snr_gt_off, snr_gt_gtp_off]

fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
x_ = np.arange(len(labels)); w = 0.2
ax.bar(x_-1.5*w, coh_off_vals,  width=w, label='Coherence@10 OFF')
ax.bar(x_-0.5*w, coh_post_vals, width=w, label='Coherence@10 post (1.05–2.0s)')
ax.bar(x_+0.5*w, plv_off_vals,  width=w, label='PLV OFF (8–12)')
ax.set_xticks(x_); ax.set_xticklabels(labels, rotation=10); ax.set_ylim(0, 1.05)
ax.set_title(f'Step 5 metrics | baseline Cz: coh@10={coh_base_off:.3f}, PLV={plv_base_off:.3f}')
ax.legend(ncols=3, fontsize=9)
fig.savefig(outdir / 'fig5a_metrics_coh_plv.png', dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
ax.bar(np.arange(len(labels)), snr_off_vals)
ax.set_xticks(np.arange(len(labels))); ax.set_xticklabels(labels, rotation=10)
ax.set_title(f'Step 5: SNR10 OFF (dB) | baseline Cz={snr_base_off:.2f} dB')
fig.savefig(outdir / 'fig5b_snr10_off.png', dpi=200); plt.close(fig)

pct_labels = ['Cz clean', 'Cz GT-prot', f'GT-C{best_gt+1} clean', f'GT-C{best_gt+1} GT-prot']
pct_coh = [pct_coh_cln, pct_coh_gtp, pct_coh_gt, pct_coh_gt_gtp]
pct_snr = [pct_snr_cln, pct_snr_gtp, pct_snr_gt, pct_snr_gt_gtp]
fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
x_ = np.arange(len(pct_labels)); w = 0.35
ax.bar(x_-w/2, pct_coh, width=w, label='%Recovery coherence@10 OFF')
ax.bar(x_+w/2, pct_snr, width=w, label='%Recovery SNR10 OFF')
ax.axhline(0, color='k', lw=0.8); ax.set_xticks(x_); ax.set_xticklabels(pct_labels, rotation=10)
ax.set_title('Step 5: Percent recovery vs baseline'); ax.legend()
fig.savefig(outdir / 'fig5c_percent_recovery.png', dpi=200); plt.close(fig)

# =============== CSV + report ================
pd.DataFrame([{
    'sfreq': sfreq, 'pulses': len(onsets), 'ioi_median_s': float(np.median(ioi)) if len(ioi) else np.nan,
    'ref_ch': ref_ch, 'n_eeg_used': len(eeg_chs), 'n_removed': len(removed),
    'best_gt_comp': int(best_gt+1),
    'coh_base_off': coh_base_off, 'coh_raw_off': coh_raw_off,
    'coh_clean_off': coh_cln_off, 'coh_gtprot_off': coh_gtp_off,
    'coh_gtcomp_clean_off': coh_gt_off, 'coh_gtcomp_gtprot_off': coh_gt_gtp_off,
    'snr_base_off_db': snr_base_off, 'snr_raw_off_db': snr_raw_off,
    'snr_clean_off_db': snr_cln_off, 'snr_gtprot_off_db': snr_gtp_off,
    'snr_gtcomp_clean_off_db': snr_gt_off, 'snr_gtcomp_gtprot_off_db': snr_gt_gtp_off,
    'on_rms_reduction_clean_pct': on_red_cln, 'on_rms_reduction_gtprot_pct': on_red_gtp,
    'end_rms_reduction_clean_pct': end_red_cln, 'end_rms_reduction_gtprot_pct': end_red_gtp,
    'pct_recovery_coh_clean': pct_coh_cln, 'pct_recovery_coh_gtprot': pct_coh_gtp,
    'pct_recovery_coh_gtcomp_clean': pct_coh_gt, 'pct_recovery_coh_gtcomp_gtprot': pct_coh_gt_gtp,
    'pct_recovery_snr_clean': pct_snr_cln, 'pct_recovery_snr_gtprot': pct_snr_gtp,
    'pct_recovery_snr_gtcomp_clean': pct_snr_gt, 'pct_recovery_snr_gtcomp_gtprot': pct_snr_gt_gtp,
}]).to_csv(outdir / 'metrics_summary.csv', index=False)

report = (
    f"SUBSPACE SEPARATION REPORT (RUN02 ~10s IOI)\n"
    f"stim_file={stim_vhdr}\nbaseline_file={base_vhdr}\n"
    f"sfreq={sfreq}  ref={ref_ch}  n_eeg={len(eeg_chs)}  removed={removed}\n"
    f"pulses={len(onsets)}  IOI_median={np.median(ioi) if len(ioi) else np.nan:.4f}s\n\n"
    f"best_GT_component=GT-C{best_gt+1}\n"
    f"scores (comp, coh_off, plv_off, snr10_dB, art_ratio):\n{scores_gt_sorted}\n\n"
    f"Metrics (OFF):\n"
    f"  Baseline Cz : coh10={coh_base_off:.3f}  plv={plv_base_off:.3f}  snr10={snr_base_off:.2f} dB\n"
    f"  Cz raw      : coh10={coh_raw_off:.3f}   plv={plv_raw_off:.3f}   snr10={snr_raw_off:.2f} dB\n"
    f"  Cz clean    : coh10={coh_cln_off:.3f}   plv={plv_cln_off:.3f}   snr10={snr_cln_off:.2f} dB\n"
    f"  Cz GT-prot  : coh10={coh_gtp_off:.3f}   plv={plv_gtp_off:.3f}   snr10={snr_gtp_off:.2f} dB\n"
    f"  GT-C{best_gt+1} clean : coh10={coh_gt_off:.3f}  plv={plv_gt_off:.3f}  snr10={snr_gt_off:.2f} dB\n"
    f"  GT-C{best_gt+1} GT-prot: coh10={coh_gt_gtp_off:.3f}  plv={plv_gt_gtp_off:.3f}  snr10={snr_gt_gtp_off:.2f} dB\n\n"
    f"Post-stim coherence (1.05-2.0s): raw={coh_raw_post:.3f}  clean={coh_cln_post:.3f}  "
    f"gtprot={coh_gtp_post:.3f}  GTcomp_clean={coh_gt_post:.3f}  GTcomp_gtprot={coh_gt_gtp_post:.3f}\n\n"
    f"Artifact suppression RMS (Cz broadband):\n"
    f"  ON  reduction: clean={on_red_cln:.2f}%  GT-prot={on_red_gtp:.2f}%\n"
    f"  END reduction: clean={end_red_cln:.2f}%  GT-prot={end_red_gtp:.2f}%\n\n"
    f"%Recovery = 100*(metric_clean - metric_raw)/(metric_baseline - metric_raw)\n"
)
(outdir / 'report.txt').write_text(report)
print('DONE — outputs saved to:', outdir)

# ------------------ Additional variants ------------------
# Variant A: use baseline-only as OFF covariance (cleaning trained on baseline)
suffix = '_baselineOFF'
outdir_a = outdir / ('variant' + suffix)
outdir_a.mkdir(exist_ok=True, parents=True)

# GT-SSD trained only on baseline 10Hz
X_train_10_a = X_base_10
Xnoi_train_a  = Xnoi_base
Cs_a = np.cov(X_train_10_a); Cn_a = np.cov(Xnoi_train_a)
evals_a, evecs_a = np.linalg.eig(np.linalg.pinv(Cn_a) @ Cs_a)
idx = np.argsort(np.real(evals_a))[::-1]
evals_a = np.real(evals_a[idx]); evecs_a = np.real(evecs_a[:, idx])
k_gt_a = min(6, X_stim.shape[0])
W_gt_a = evecs_a[:, :k_gt_a].T
Sgt_10_a = W_gt_a @ X_stim_10; Sgt_bb_a = W_gt_a @ X_stim_bb

# Artifact subspace using original mask_off but Coff from baseline (effectively Coff=baseline cov)
Con_a = np.cov(X_stim_bb[:, mask_on])
Coff_a = np.cov(X_base_bb)
evals_art_a, evecs_art_a = np.linalg.eig(np.linalg.pinv(Coff_a) @ Con_a)
idx = np.argsort(np.real(evals_art_a))[::-1]
evals_art_a = np.real(evals_art_a[idx]); evecs_art_a = np.real(evecs_art_a[:, idx])
k_art_a = min(8, X_stim.shape[0])
W_art_a = evecs_art_a[:, :k_art_a].T; Sart_bb_a = W_art_a @ X_stim_bb

# cleaning
P_art_a = proj_from_W(W_art_a[:min(6, k_art_a)])
X_clean_bb_a = X_stim_bb - (P_art_a @ X_stim_bb)
P_gt_a = proj_from_W(W_gt_a[:min(3, k_gt_a)])
I_a = np.eye(P_gt_a.shape[0])
X_clean_bb_gtprot_a = X_stim_bb - ((I_a - P_gt_a) @ (P_art_a @ X_stim_bb))
X_clean_10_a       = bandpass(notch_iir(X_clean_bb_a, sfreq), sfreq, 8, 12)
X_clean_10_gtprot_a = bandpass(notch_iir(X_clean_bb_gtprot_a, sfreq), sfreq, 8, 12)

# simple metrics (only OFF region as before)
cz_clean_bb_a = X_clean_bb_a[ref_idx]; cz_clean_bb_gtprot_a = X_clean_bb_gtprot_a[ref_idx]
cz_cln_10_a = X_clean_10_a[ref_idx]; cz_gtp_10_a = X_clean_10_gtprot_a[ref_idx]
best_gt_a = 0
coh_cln_off_a  = coh10(gt_stim_10[mask_off], cz_cln_10_a[mask_off], sfreq)
coh_gtp_off_a  = coh10(gt_stim_10[mask_off], cz_gtp_10_a[mask_off], sfreq)
snr_cln_off_a  = snr10_db(cz_cln_10_a[mask_off], sfreq)
snr_gtp_off_a  = snr10_db(cz_gtp_10_a[mask_off], sfreq)

pd.DataFrame([{ 'variant': 'baselineOFF', 'coh_cln_off': coh_cln_off_a, 'coh_gtp_off': coh_gtp_off_a,
               'snr_cln_off_db': snr_cln_off_a, 'snr_gtp_off_db': snr_gtp_off_a }]).to_csv(outdir_a / 'metrics_summary_variant_baselineOFF.csv', index=False)

# Variant B: expanded OFF selection (exclude first N seconds after each pulse)
suffix = '_expandedOFF'
outdir_b = outdir / ('variant' + suffix)
outdir_b.mkdir(exist_ok=True, parents=True)

# choose expanded exclusion window (seconds after pulse to treat as contaminated)
expanded_exclude_s = 4.5
mask_off_exp = np.ones(n_t, dtype=bool)
for o in onsets:
    mask_off_exp[o:min(n_t, o+int(expanded_exclude_s*sfreq))] = False

# GT-SSD trained on baseline + expanded OFF
X_train_10_b = np.concatenate([X_base_10, X_stim_10[:, mask_off_exp]], axis=1)
Xnoi_train_b = np.concatenate([Xnoi_base, bandpass(notch_iir(X_stim, sfreq), sfreq, 3, 22)[:, mask_off_exp]], axis=1)
b10, a10 = iirnotch(w0=10.0, Q=10.0, fs=sfreq)
Xnoi_train_b = filtfilt(b10, a10, Xnoi_train_b, axis=-1)
Cs_b = np.cov(X_train_10_b); Cn_b = np.cov(Xnoi_train_b)
evals_b, evecs_b = np.linalg.eig(np.linalg.pinv(Cn_b) @ Cs_b)
idx = np.argsort(np.real(evals_b))[::-1]
evals_b = np.real(evals_b[idx]); evecs_b = np.real(evecs_b[:, idx])
k_gt_b = min(6, X_stim.shape[0])
W_gt_b = evecs_b[:, :k_gt_b].T

# artifact subspace using expanded OFF
Con_b = np.cov(X_stim_bb[:, mask_on]); Coff_b = np.cov(X_stim_bb[:, mask_off_exp])
evals_art_b, evecs_art_b = np.linalg.eig(np.linalg.pinv(Coff_b) @ Con_b)
idx = np.argsort(np.real(evals_art_b))[::-1]
evals_art_b = np.real(evals_art_b[idx]); evecs_art_b = np.real(evecs_art_b[:, idx])
k_art_b = min(8, X_stim.shape[0])
W_art_b = evecs_art_b[:, :k_art_b].T; Sart_bb_b = W_art_b @ X_stim_bb

# cleaning
P_art_b = proj_from_W(W_art_b[:min(6, k_art_b)])
X_clean_bb_b = X_stim_bb - (P_art_b @ X_stim_bb)
P_gt_b = proj_from_W(W_gt_b[:min(3, k_gt_b)])
I_b = np.eye(P_gt_b.shape[0])
X_clean_bb_gtprot_b = X_stim_bb - ((I_b - P_gt_b) @ (P_art_b @ X_stim_bb))
X_clean_10_b       = bandpass(notch_iir(X_clean_bb_b, sfreq), sfreq, 8, 12)
X_clean_10_gtprot_b = bandpass(notch_iir(X_clean_bb_gtprot_b, sfreq), sfreq, 8, 12)

# metrics
cz_cln_10_b = X_clean_10_b[ref_idx]; cz_gtp_10_b = X_clean_10_gtprot_b[ref_idx]
coh_cln_off_b = coh10(gt_stim_10[mask_off_exp], cz_cln_10_b[mask_off_exp], sfreq)
coh_gtp_off_b = coh10(gt_stim_10[mask_off_exp], cz_gtp_10_b[mask_off_exp], sfreq)
snr_cln_off_b = snr10_db(cz_cln_10_b[mask_off_exp], sfreq)
snr_gtp_off_b = snr10_db(cz_gtp_10_b[mask_off_exp], sfreq)

pd.DataFrame([{ 'variant': 'expandedOFF', 'expanded_exclude_s': expanded_exclude_s,
               'coh_cln_off': coh_cln_off_b, 'coh_gtp_off': coh_gtp_off_b,
               'snr_cln_off_db': snr_cln_off_b, 'snr_gtp_off_db': snr_gtp_off_b }]).to_csv(outdir_b / 'metrics_summary_variant_expandedOFF.csv', index=False)