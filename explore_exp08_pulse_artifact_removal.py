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
DEBOUNCE_SAMPLES = 5           # consecutive sub-threshold samples to confirm recovery
MAX_ARTIFACT_MS = 200          # hard cap: never crop more than 200 ms per trial
POST_ANCHOR_SAMPLES = 10       # samples after artifact_end for post-baseline mean

# ════════════════════════════════════════════════════════════════════════════
# GOAL: Remove pulse artifact from EXP08 EEG epochs, per-epoch per-channel,
#       using amplitude-threshold detection and linear interpolation.
#
# INPUT:  exp08t_epochs_{pct}pct_on-epo.fif  (3 intensity files)
# OUTPUT: exp08t_epochs_{pct}pct_on_artremoved-epo.fif
#
# PIPELINE:
#   1) LOAD EPOCHS for each intensity
#   2) FOR EACH EPOCH, CHANNEL:
#      └─ Detect artifact end via amplitude threshold + debounce
#      └─ Interpolate artifact region using epoch-specific baselines
#   3) SAVE cleaned epochs
#   4) QC visualization (heatmap + before/after overlay)
# ════════════════════════════════════════════════════════════════════════════

def detect_artifact_end(signal, times, baseline_start_ms, baseline_end_ms,
                        k_threshold, debounce_samples, max_artifact_ms, sfreq):
    """
    Detect artifact recovery point via amplitude threshold.

    For this (epoch, channel):
    1. Compute baseline mean and std over pre-pulse window
    2. Find peak amplitude in the artifact region (first 200 ms)
    3. Walk forward from pulse onset until |signal - baseline_mean| < k*std AND
       is decreasing towards baseline (rate of change < small threshold)
    4. Return the sample index of artifact end

    Returns: artifact_end_sample (int, relative to pulse onset t=0)
    """
    # Convert ms to sample indices
    t_zero_idx = np.argmin(np.abs(times))
    baseline_start_idx = np.argmin(np.abs(times - baseline_start_ms / 1000))
    baseline_end_idx = np.argmin(np.abs(times - baseline_end_ms / 1000))
    max_artifact_samples = int(max_artifact_ms / 1000 * sfreq)

    # Compute baseline stats from pre-pulse window
    baseline_values = signal[baseline_start_idx:baseline_end_idx]
    baseline_mean = baseline_values.mean()
    baseline_std = baseline_values.std()

    # Threshold: k × standard deviation
    threshold = k_threshold * baseline_std

    # Walk forward from pulse onset, looking for recovery
    # Require: signal close to baseline AND stable (not changing rapidly)
    artifact_end_sample = None
    sub_threshold_count = 0

    for sample_idx in range(t_zero_idx + 1, min(t_zero_idx + max_artifact_samples, len(signal))):
        current_dev = np.abs(signal[sample_idx] - baseline_mean)
        prev_dev = np.abs(signal[sample_idx - 1] - baseline_mean)

        # Two conditions: (1) close to baseline, (2) stable or decreasing
        is_close = current_dev < threshold
        is_stable_or_decreasing = current_dev <= prev_dev * 1.1  # Allow 10% wiggle for noise

        if is_close and is_stable_or_decreasing:
            sub_threshold_count += 1
            if sub_threshold_count >= debounce_samples:
                # Confirmed recovery: return the first sample of the debounce window
                artifact_end_sample = sample_idx - debounce_samples + 1
                break
        else:
            sub_threshold_count = 0

    # If no recovery detected, cap at max_artifact_samples
    if artifact_end_sample is None:
        artifact_end_sample = min(t_zero_idx + max_artifact_samples, len(signal) - 1)

    # Return sample index relative to pulse onset (t_zero_idx)
    return artifact_end_sample - t_zero_idx


def remove_pulse_artifact(epochs, config):
    """
    Remove pulse artifact from epochs via per-epoch per-channel threshold detection + interpolation.

    For each (epoch, channel):
    1. Detect artifact_end_sample using amplitude threshold
    2. Extract pre-baseline (−100 to −5 ms) and post-baseline (10 ms after artifact_end)
    3. Linearly interpolate from pre to post across artifact region
    4. Replace [pulse_onset : artifact_end] with interpolation

    Returns: cleaned epochs, artifact_end_samples array
    """
    epochs_clean = epochs.copy()
    data = epochs_clean.get_data()  # (n_epochs, n_channels, n_times)
    times = epochs_clean.times
    sfreq = epochs_clean.info['sfreq']

    # Time indices for baseline windows
    pre_base_start_idx = np.argmin(np.abs(times - config['PRE_BASELINE_START_MS'] / 1000))
    pre_base_end_idx = np.argmin(np.abs(times - config['PRE_BASELINE_END_MS'] / 1000))
    t_zero_idx = np.argmin(np.abs(times))

    # Storage for artifact_end_samples (for QC visualization)
    artifact_end_samples = np.zeros((data.shape[0], data.shape[1]), dtype=int)

    # Loop: epoch × channel
    for ep_idx in range(data.shape[0]):
        for ch_idx in range(data.shape[1]):
            signal = data[ep_idx, ch_idx, :]

            # Step 1: Detect artifact end for this epoch/channel
            artifact_end_sample = detect_artifact_end(
                signal, times,
                config['PRE_BASELINE_START_MS'],
                config['PRE_BASELINE_END_MS'],
                config['K_THRESHOLD'],
                config['DEBOUNCE_SAMPLES'],
                config['MAX_ARTIFACT_MS'],
                sfreq
            )
            artifact_end_samples[ep_idx, ch_idx] = artifact_end_sample

            # Step 2: Compute pre- and post-anchors
            pre_baseline_mean = signal[pre_base_start_idx:pre_base_end_idx].mean()
            post_anchor_start_idx = t_zero_idx + artifact_end_sample
            post_anchor_end_idx = min(post_anchor_start_idx + config['POST_ANCHOR_SAMPLES'], len(signal))
            post_baseline_mean = signal[post_anchor_start_idx:post_anchor_end_idx].mean()

            # Step 3: Create linear interpolation
            artifact_region_samples = artifact_end_sample
            if artifact_region_samples > 0:
                interp = np.linspace(pre_baseline_mean, post_baseline_mean, artifact_region_samples)

                # Step 4: Replace artifact region
                data[ep_idx, ch_idx, t_zero_idx:t_zero_idx + artifact_region_samples] = interp

    # Update epochs with cleaned data
    epochs_clean._data = data

    return epochs_clean, artifact_end_samples


# ════════════════════════════════════════════════════════════════════════════
# 1) LOAD EPOCHS
# ════════════════════════════════════════════════════════════════════════════

config = {
    'PRE_BASELINE_START_MS': PRE_BASELINE_START_MS,
    'PRE_BASELINE_END_MS': PRE_BASELINE_END_MS,
    'K_THRESHOLD': K_THRESHOLD,
    'DEBOUNCE_SAMPLES': DEBOUNCE_SAMPLES,
    'MAX_ARTIFACT_MS': MAX_ARTIFACT_MS,
    'POST_ANCHOR_SAMPLES': POST_ANCHOR_SAMPLES,
}

epochs_list = []
artifact_end_samples_list = []

for intensity_label in ["10%", "50%", "100%"]:
    print(f"Processing {intensity_label} intensity...")

    pct_label = intensity_label.replace('%', 'pct')
    epochs_file = OUTPUT_DIR / f"exp08t_epochs_{pct_label}_on-epo.fif"

    # Load original epochs
    epochs = mne.read_epochs(epochs_file, verbose=False, preload=True)
    print(f"  Loaded {len(epochs)} epochs, {len(epochs.ch_names)} channels")

    # ════════════════════════════════════════════════════════════════════════
    # 2) DETECT ARTIFACT END & INTERPOLATE (per epoch, per channel)
    # ════════════════════════════════════════════════════════════════════════

    epochs_clean, artifact_end_samples = remove_pulse_artifact(epochs, config)
    print(f"  Removed artifact from all {len(epochs)} epochs, {len(epochs.ch_names)} channels")

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

fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

# Panel A: artifact_end_samples heatmap for each intensity
for row, (intensity_label, artifact_end_samples) in enumerate(artifact_end_samples_list):
    ax = fig.add_subplot(gs[row, 0])
    im = ax.imshow(artifact_end_samples, aspect='auto', cmap='viridis', origin='lower')
    ax.set_xlabel('Channel index')
    ax.set_ylabel('Epoch')
    ax.set_title(f'{intensity_label} artifact end (samples)')
    plt.colorbar(im, ax=ax, label='Samples')

# Panel B: Before/after overlay for 100% intensity (Oz channel)
intensity_100_idx = 2
intensity_label_100, epochs_orig_100, epochs_clean_100 = epochs_list[intensity_100_idx]

ch_idx_oz = epochs_orig_100.ch_names.index('Oz')
t = epochs_orig_100.times

for col_idx, (title_suffix, epochs_to_plot) in enumerate([
    ('BEFORE artifact removal', epochs_orig_100),
    ('AFTER artifact removal', epochs_clean_100),
]):
    ax = fig.add_subplot(gs[2, 1 + col_idx])

    data_plot = epochs_to_plot.get_data()[:, ch_idx_oz, :] * 1e6
    for epoch in data_plot:
        ax.plot(t, epoch, alpha=0.15, linewidth=0.5, color='gray')

    ax.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Pulse onset')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Oz (uV)')
    ax.set_title(f'100% intensity {title_suffix}')
    ax.grid(True, alpha=0.2)
    ax.legend(fontsize=8)

fig.suptitle('Pulse Artifact Removal QC: Per-Epoch Per-Channel Detection + Interpolation',
             fontsize=14, fontweight='bold', y=0.995)

fig.savefig(OUTPUT_DIR / "exp08_pulse_artremoved_qc.png", dpi=150, bbox_inches='tight')
plt.close()
print("\nSaved: exp08_pulse_artremoved_qc.png")

# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("PULSE ARTIFACT REMOVAL COMPLETE")
print("="*70)
print(f"Config:")
print(f"  Pre-baseline window: {PRE_BASELINE_START_MS} to {PRE_BASELINE_END_MS} ms")
print(f"  Threshold: k={K_THRESHOLD} × baseline_std")
print(f"  Debounce: {DEBOUNCE_SAMPLES} samples")
print(f"  Max artifact: {MAX_ARTIFACT_MS} ms")

print(f"\nArtifact end sample statistics (relative to pulse onset):")
for intensity_label, artifact_end_samples in artifact_end_samples_list:
    mean_samples = artifact_end_samples.mean()
    std_samples = artifact_end_samples.std()
    min_samples = artifact_end_samples.min()
    max_samples = artifact_end_samples.max()
    print(f"  {intensity_label:>5}: mean={mean_samples:6.1f}, std={std_samples:5.1f}, "
          f"range=[{min_samples:3.0f}, {max_samples:3.0f}] samples")

print(f"\nCleaned epoch files saved:")
for intensity_label, _, _ in epochs_list:
    pct_label = intensity_label.replace('%', 'pct')
    print(f"  exp08t_epochs_{pct_label}_on_artremoved-epo.fif")
