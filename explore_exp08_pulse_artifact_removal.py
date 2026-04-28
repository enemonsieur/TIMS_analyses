"""Remove TMS pulse artifact from EXP08 EEG epochs via per-epoch per-channel threshold detection + interpolation."""

from pathlib import Path
import matplotlib.pyplot as plt
import mne
import numpy as np

OUTPUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

PRE_BASELINE_START_MS = -100   # pre-pulse baseline window start
PRE_BASELINE_END_MS = -5       # close to pulse — captures current baseline state
K_THRESHOLD = 5                # artifact threshold: k × pre-pulse std
PEAK_FRACTION = 0.02           # threshold floor: 2% of peak artifact amplitude
MIN_ARTIFACT_MS = 10           # never declare recovery before 10 ms (pulse is ~15 ms wide)
DEBOUNCE_SAMPLES = 5           # consecutive sub-threshold samples to confirm recovery (5 ms)
MAX_ARTIFACT_MS = 200          # hard cap: never crop more than 200 ms per trial
POST_ANCHOR_SAMPLES = 10       # samples after artifact_end for post-baseline mean

ALL_INTENSITIES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

# ════════════════════════════════════════════════════════════════════════════
# GOAL: Remove pulse artifact from EXP08 EEG epochs, per-epoch per-channel,
#       using amplitude-threshold detection and linear interpolation.
#
# INPUT:  exp08t_epochs_{pct}pct_on-epo.fif  (10 intensity files, 10-100%)
# OUTPUT: exp08t_epochs_{pct}pct_on_artremoved-epo.fif
#
# PIPELINE:
#   1) LOAD EPOCHS for each intensity
#   2) FOR EACH EPOCH, CHANNEL:
#      └─ Detect artifact end via amplitude threshold + debounce
#      └─ Interpolate artifact region using epoch-specific baselines
#   3) SAVE cleaned epochs
#   4) QC visualization (heatmaps per intensity + before/after Oz overlay at 100%)
# ════════════════════════════════════════════════════════════════════════════

def _fit_drift(signal, times, baseline_start_idx, baseline_end_idx):
    """
    Fit a linear trend to the pre-pulse baseline window.

    Returns slope, intercept such that expected(t) = slope * t + intercept.
    Also returns residual_std: std of signal around the fitted trend (true noise floor,
    not inflated by drift as a plain std() would be).
    """
    pre_times = times[baseline_start_idx:baseline_end_idx]
    pre_values = signal[baseline_start_idx:baseline_end_idx]
    slope, intercept = np.polyfit(pre_times, pre_values, 1)
    residual_std = (pre_values - (slope * pre_times + intercept)).std()
    return slope, intercept, residual_std


def detect_artifact_end(signal, times, baseline_start_ms, baseline_end_ms,
                        k_threshold, peak_fraction, min_artifact_ms,
                        debounce_samples, max_artifact_ms, sfreq):
    """
    Detect artifact recovery point using a drift-aware amplitude threshold.

    The pre-pulse baseline is modelled as a linear trend (slope + intercept) rather
    than a fixed mean. At 100% intensity the signal drifts at up to -3000 uV/s because
    the previous pulse's artifact hasn't settled. Comparing the post-pulse signal against
    a frozen baseline_mean causes false detections; comparing against the extrapolated
    trend correctly asks "has the spike returned to where the signal would have been
    without the pulse?"

    For each (epoch, channel):
    1. Fit linear trend to pre-pulse window → slope, intercept, residual_std
    2. expected(t) = slope * t + intercept
    3. Peak amplitude = max deviation from expected in first 5 ms post-pulse
    4. Threshold = max(k * residual_std, peak_fraction * peak_amplitude)
    5. Walk forward from MIN_ARTIFACT_MS; at each sample compare |signal - expected(t)|
       for debounce_samples consecutive samples below threshold
    6. Return artifact_end_sample relative to t=0

    Returns: artifact_end_sample (int, samples relative to pulse onset)
    """
    t_zero_idx = np.argmin(np.abs(times))
    baseline_start_idx = np.argmin(np.abs(times - baseline_start_ms / 1000))
    baseline_end_idx = np.argmin(np.abs(times - baseline_end_ms / 1000))
    max_artifact_samples = int(max_artifact_ms / 1000 * sfreq)
    min_artifact_samples = int(min_artifact_ms / 1000 * sfreq)
    peak_window_samples = int(0.005 * sfreq)  # 5 ms peak window

    # Fit drift model to pre-pulse window
    slope, intercept, residual_std = _fit_drift(signal, times, baseline_start_idx, baseline_end_idx)

    # Peak deviation from extrapolated trend in first 5 ms post-pulse
    peak_end = min(t_zero_idx + peak_window_samples, len(signal))
    peak_amp = np.max(np.abs(signal[t_zero_idx:peak_end] - (slope * times[t_zero_idx:peak_end] + intercept)))

    # Threshold: noise floor OR artifact-relative floor — whichever is larger
    threshold = max(k_threshold * residual_std, peak_fraction * peak_amp)

    # Walk forward from minimum artifact window, testing deviation from extrapolated trend
    artifact_end_sample = None
    sub_threshold_count = 0

    walk_start = t_zero_idx + min_artifact_samples
    for sample_idx in range(walk_start, min(t_zero_idx + max_artifact_samples, len(signal))):
        expected_now  = slope * times[sample_idx]     + intercept
        expected_prev = slope * times[sample_idx - 1] + intercept
        current_dev = np.abs(signal[sample_idx]     - expected_now)
        prev_dev    = np.abs(signal[sample_idx - 1] - expected_prev)

        is_close             = current_dev < threshold
        is_stable_or_decreasing = current_dev <= prev_dev * 1.1  # 10% wiggle for noise

        if is_close and is_stable_or_decreasing:
            sub_threshold_count += 1
            if sub_threshold_count >= debounce_samples:
                artifact_end_sample = sample_idx - debounce_samples + 1
                break
        else:
            sub_threshold_count = 0

    if artifact_end_sample is None:
        artifact_end_sample = min(t_zero_idx + max_artifact_samples, len(signal) - 1)

    return artifact_end_sample - t_zero_idx


def remove_pulse_artifact(epochs, config):
    """
    Remove pulse artifact from epochs via drift-aware detection + interpolation.

    For each (epoch, channel):
    1. Fit linear drift to pre-pulse window (slope + intercept)
    2. Detect artifact_end via drift-relative threshold
    3. Interpolate from expected(t=0) to expected(t=artifact_end)
       — fills artifact window with the drift continuation, not a flat ramp
    4. Replace [pulse_onset : artifact_end] with this interpolation

    The slow post-pulse exponential decay (expected physics) is preserved — only
    the acute spike region is replaced.

    Returns: cleaned epochs, artifact_end_samples array
    """
    epochs_clean = epochs.copy()
    data = epochs_clean.get_data()  # (n_epochs, n_channels, n_times)
    times = epochs_clean.times
    sfreq = epochs_clean.info['sfreq']

    pre_base_start_idx = np.argmin(np.abs(times - config['PRE_BASELINE_START_MS'] / 1000))
    pre_base_end_idx   = np.argmin(np.abs(times - config['PRE_BASELINE_END_MS'] / 1000))
    t_zero_idx = np.argmin(np.abs(times))

    artifact_end_samples = np.zeros((data.shape[0], data.shape[1]), dtype=int)

    for ep_idx in range(data.shape[0]):
        for ch_idx in range(data.shape[1]):
            signal = data[ep_idx, ch_idx, :]

            # Step 1: Fit drift model to pre-pulse window
            slope, intercept, _ = _fit_drift(signal, times, pre_base_start_idx, pre_base_end_idx)

            # Step 2: Detect artifact end (drift-relative)
            artifact_end_sample = detect_artifact_end(
                signal, times,
                config['PRE_BASELINE_START_MS'],
                config['PRE_BASELINE_END_MS'],
                config['K_THRESHOLD'],
                config['PEAK_FRACTION'],
                config['MIN_ARTIFACT_MS'],
                config['DEBOUNCE_SAMPLES'],
                config['MAX_ARTIFACT_MS'],
                sfreq
            )
            artifact_end_samples[ep_idx, ch_idx] = artifact_end_sample

            # Step 3: Anchors from extrapolated trend — not the raw signal
            # pre_anchor:  expected value at pulse onset (t=0)
            # post_anchor: expected value at artifact_end (where drift would have taken the signal)
            t_zero   = times[t_zero_idx]
            t_end    = times[t_zero_idx + artifact_end_sample]
            pre_anchor  = slope * t_zero + intercept
            post_anchor = slope * t_end  + intercept

            # Step 4: Replace artifact region with drift-continuation ramp
            artifact_region_samples = artifact_end_sample
            if artifact_region_samples > 0:
                interp = np.linspace(pre_anchor, post_anchor, artifact_region_samples)
                data[ep_idx, ch_idx, t_zero_idx:t_zero_idx + artifact_region_samples] = interp

    epochs_clean._data = data
    return epochs_clean, artifact_end_samples


# ════════════════════════════════════════════════════════════════════════════
# 1) LOAD AND PROCESS ALL INTENSITIES
# ════════════════════════════════════════════════════════════════════════════

config = {
    'PRE_BASELINE_START_MS': PRE_BASELINE_START_MS,
    'PRE_BASELINE_END_MS': PRE_BASELINE_END_MS,
    'K_THRESHOLD': K_THRESHOLD,
    'PEAK_FRACTION': PEAK_FRACTION,
    'MIN_ARTIFACT_MS': MIN_ARTIFACT_MS,
    'DEBOUNCE_SAMPLES': DEBOUNCE_SAMPLES,
    'MAX_ARTIFACT_MS': MAX_ARTIFACT_MS,
    'POST_ANCHOR_SAMPLES': POST_ANCHOR_SAMPLES,
}

epochs_list = []             # (intensity_label, epochs_orig, epochs_clean)
artifact_end_samples_list = []  # (intensity_label, artifact_end_samples)

for intensity_pct in ALL_INTENSITIES:
    intensity_label = f"{intensity_pct}%"
    print(f"Processing {intensity_label} intensity...")

    pct_label = f"{intensity_pct}pct"
    epochs_file = OUTPUT_DIR / f"exp08t_epochs_{pct_label}_on-epo.fif"

    # Load original epochs
    epochs = mne.read_epochs(epochs_file, verbose=False, preload=True)
    print(f"  Loaded {len(epochs)} epochs, {len(epochs.ch_names)} channels")

    # ════════════════════════════════════════════════════════════════════════
    # 2) DETECT ARTIFACT END & INTERPOLATE (per epoch, per channel)
    # ════════════════════════════════════════════════════════════════════════

    epochs_clean, artifact_end_samples = remove_pulse_artifact(epochs, config)

    mean_ms = artifact_end_samples.mean()
    std_ms = artifact_end_samples.std()
    min_ms = artifact_end_samples.min()
    max_ms = artifact_end_samples.max()
    print(f"  Artifact duration: mean={mean_ms:.1f} ms, std={std_ms:.1f}, range=[{min_ms}, {max_ms}] ms")

    # ════════════════════════════════════════════════════════════════════════
    # 3) SAVE CLEANED EPOCHS
    # ════════════════════════════════════════════════════════════════════════

    output_file = OUTPUT_DIR / f"exp08t_epochs_{pct_label}_on_artremoved-epo.fif"
    epochs_clean.save(output_file, overwrite=True, verbose=False)
    print(f"  Saved: {output_file.name}")

    epochs_list.append((intensity_label, epochs, epochs_clean))
    artifact_end_samples_list.append((intensity_label, artifact_end_samples))

# ════════════════════════════════════════════════════════════════════════════
# 4) QC VISUALIZATION
# ════════════════════════════════════════════════════════════════════════════

# Panel layout: 10 heatmap rows (one per intensity) + 2 Oz overlay panels for 100%
fig = plt.figure(figsize=(18, 28))
gs = fig.add_gridspec(12, 2, hspace=0.4, wspace=0.35)

# Panel A: artifact_end_samples heatmap for each intensity (left column)
for row, (intensity_label, artifact_end_samples) in enumerate(artifact_end_samples_list):
    ax = fig.add_subplot(gs[row, 0])
    im = ax.imshow(artifact_end_samples, aspect='auto', cmap='viridis', origin='lower')
    ax.set_xlabel('Channel index')
    ax.set_ylabel('Epoch')
    ax.set_title(f'{intensity_label} artifact end (ms)')
    plt.colorbar(im, ax=ax, label='ms')

# Panel B: mean artifact duration across intensities (right column, top)
ax_trend = fig.add_subplot(gs[0:4, 1])
means = [arr.mean() for _, arr in artifact_end_samples_list]
stds = [arr.std() for _, arr in artifact_end_samples_list]
intensities = ALL_INTENSITIES
ax_trend.errorbar(intensities, means, yerr=stds, fmt='o-', capsize=4, color='steelblue')
ax_trend.set_xlabel('Intensity (%)')
ax_trend.set_ylabel('Artifact duration (ms)')
ax_trend.set_title('Mean artifact duration vs intensity\n(should increase or plateau, not drop at 100%)')
ax_trend.grid(True, alpha=0.3)
ax_trend.set_xticks(intensities)

# Panel C: Before/after Oz overlay for 100% intensity (right column, bottom)
intensity_100_label = "100%"
match_100 = [(lab, orig, clean) for lab, orig, clean in epochs_list if lab == intensity_100_label]
if match_100:
    intensity_label_100, epochs_orig_100, epochs_clean_100 = match_100[0]
    ch_idx_oz = epochs_orig_100.ch_names.index('Oz')
    t = epochs_orig_100.times

    for col_idx, (title_suffix, epochs_to_plot, color) in enumerate([
        ('BEFORE removal (100%)', epochs_orig_100, 'gray'),
        ('AFTER removal (100%)', epochs_clean_100, 'steelblue'),
    ]):
        ax = fig.add_subplot(gs[4:8, 1] if col_idx == 0 else gs[8:12, 1])
        data_plot = epochs_to_plot.get_data()[:, ch_idx_oz, :] * 1e6
        for epoch in data_plot:
            ax.plot(t, epoch, alpha=0.2, linewidth=0.5, color=color)
        ax.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.7, label='Pulse onset')
        ax.set_xlim(-0.3, 0.5)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Oz (uV)')
        ax.set_title(f'Oz {title_suffix}')
        ax.grid(True, alpha=0.2)
        ax.legend(fontsize=8)

fig.suptitle(
    'Pulse Artifact Removal QC: All Intensities (10-100%)\n'
    'Drift-aware threshold | peak-relative floor | 5-sample debounce | 10 ms minimum',
    fontsize=13, fontweight='bold', y=0.995
)

fig.savefig(OUTPUT_DIR / "exp08_pulse_artremoved_qc.png", dpi=150, bbox_inches='tight')
plt.close()
print("\nSaved: exp08_pulse_artremoved_qc.png")

# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("PULSE ARTIFACT REMOVAL COMPLETE — ALL INTENSITIES")
print("="*70)
print(f"Config:")
print(f"  Pre-baseline window: {PRE_BASELINE_START_MS} to {PRE_BASELINE_END_MS} ms")
print(f"  Threshold:           k={K_THRESHOLD} x baseline_std  OR  {PEAK_FRACTION*100:.0f}% of peak amplitude")
print(f"  Min artifact:        {MIN_ARTIFACT_MS} ms")
print(f"  Debounce:            {DEBOUNCE_SAMPLES} samples ({DEBOUNCE_SAMPLES} ms at 1000 Hz)")
print(f"  Max artifact:        {MAX_ARTIFACT_MS} ms")

print(f"\nArtifact duration statistics per intensity:")
print(f"  {'Intensity':>10}  {'Mean (ms)':>10}  {'Std':>7}  {'Min':>5}  {'Max':>5}")
for intensity_label, artifact_end_samples in artifact_end_samples_list:
    mean_ms = artifact_end_samples.mean()
    std_ms = artifact_end_samples.std()
    min_ms = artifact_end_samples.min()
    max_ms = artifact_end_samples.max()
    print(f"  {intensity_label:>10}  {mean_ms:>10.1f}  {std_ms:>7.1f}  {min_ms:>5.0f}  {max_ms:>5.0f}")

print(f"\nCleaned epoch files saved (all intensities):")
for intensity_pct in ALL_INTENSITIES:
    print(f"  exp08t_epochs_{intensity_pct}pct_on_artremoved-epo.fif")
