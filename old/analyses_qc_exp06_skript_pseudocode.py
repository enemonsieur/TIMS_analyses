"""Select the exp06 baseline SSD component that best matches the measured ground-truth peak."""


# ===== 1. Config ==============================================================
BASELINE_VHDR_PATH = Path(r"...")
OUTPUT_DIRECTORY = Path(r"...")

GT_SEARCH_RANGE_HZ = (6.0, 18.0)
VIEW_RANGE_HZ = (4.0, 20.0)
SIGNAL_HALF_WIDTH_HZ = 1.0

BASELINE_WINDOW_DURATION_S = 1.0
BASELINE_FIRST_WINDOW_START_S = 2.0
N_COMPONENTS = 10


# ===== 2. Analysis Flow =======================================================
# baseline raw -> recorded reference channel -> reference PSD -> peak frequency -> SSD signal band
# baseline raw -> drop stim/reference channels -> retained EEG -> fixed windows -> SSD spatial filters -> component epochs
# recorded reference channel + SSD signal band -> band-pass reference trace
# fixed windows -> scoring mask
# SSD filters + band-pass EEG + view-band EEG + reference trace -> coherence/peak scores -> selected component
# selected component + averaged overlay trace -> figures + summary


# ===== 3. Load baseline run ===================================================
# baseline file -> MNE Raw, volts, channels x samples
raw = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)
sfreq = float(raw.info["sfreq"])


# ===== 4. Split measured channels =============================================
# raw -> recorded reference channel
# gt_trace is the recorded `ground_truth` channel as a 1-D volts trace.
gt_trace = raw.copy().pick(["ground_truth"]).get_data()[0]

# raw -> drop stim/reference channels
# eeg_raw keeps only channels allowed to enter SSD.
eeg_raw = raw.copy().drop_channels(["STIM", "ground_truth"])
window_samples = int(round(BASELINE_WINDOW_DURATION_S * sfreq))


# ===== 5. Build repeated windows ==============================================
# retained EEG -> fixed-window events
# events has shape (n_windows, 3), one MNE row per window start.
events = mne.make_fixed_length_events(
    eeg_raw,
    start=BASELINE_FIRST_WINDOW_START_S,
    duration=BASELINE_WINDOW_DURATION_S,
    overlap=0.0,
)


# ===== 6. Measure the target band =============================================
# recorded reference channel -> PSD over the readable frequency range
gt_psd, freqs_hz = mne.time_frequency.psd_array_welch(
    gt_trace,
    sfreq=sfreq,
    fmin=VIEW_RANGE_HZ[0],
    fmax=VIEW_RANGE_HZ[1],
    n_fft=min(4096, gt_trace.size),
    verbose=False,
)

# PSD -> measured peak -> narrow signal band
search_mask = (freqs_hz >= GT_SEARCH_RANGE_HZ[0]) & (freqs_hz <= GT_SEARCH_RANGE_HZ[1])
peak_hz = float(freqs_hz[search_mask][np.argmax(gt_psd[search_mask])])
signal_band_hz = (peak_hz - SIGNAL_HALF_WIDTH_HZ, peak_hz + SIGNAL_HALF_WIDTH_HZ)


# ===== 7. Fit SSD model =======================================================
# EEG windows -> SSD filters, patterns, eigenvalues
# SSD here means spatial filters fitted to separate the narrow signal band from flanking activity.
n_components = min(N_COMPONENTS, len(eeg_raw.ch_names))
ssd_filters, spatial_patterns, eigenvalues = plot_helpers.run_ssd(
    eeg_raw,
    events,
    signal_band_hz,
    VIEW_RANGE_HZ,
    n_comp=n_components,
    epoch_duration_s=BASELINE_WINDOW_DURATION_S,
)


# ===== 8. Project into component space ========================================
# EEG windows + SSD filters -> component epochs
# comp_epochs has shape (n_components, n_epochs, n_samples).
epochs, comp_epochs = plot_helpers.build_ssd_component_epochs(
    eeg_raw,
    events,
    ssd_filters,
    VIEW_RANGE_HZ,
    BASELINE_WINDOW_DURATION_S,
)


# ===== 9. Build scoring inputs ================================================
# reference channel -> band-pass reference trace
ref_trace = preprocessing.filter_signal(gt_trace, sfreq, signal_band_hz[0], signal_band_hz[1])

# window starts -> scoring mask over the full baseline trace
# score_mask has shape (n_samples,).
score_mask = np.zeros(eeg_raw.n_times, dtype=bool)
for start_sample in events[:, 0]:
    score_mask[int(start_sample):int(start_sample) + window_samples] = True

# retained EEG -> signal-band EEG + view-band EEG
# signal_raw is for reference matching; view_raw is for peak-shape inspection.
signal_raw = eeg_raw.copy().filter(*signal_band_hz, verbose=False)
view_raw = eeg_raw.copy().filter(*VIEW_RANGE_HZ, verbose=False)


# ===== 10. Compute component scores ============================================
# SSD outputs + EEG views + reference -> one score vector per component
coherence_scores, peak_ratios, peak_freqs = preprocessing.rank_ssd_components_against_reference(
    spatial_filters=ssd_filters,
    raw_signal_band=signal_raw,
    raw_view_band=view_raw,
    evaluation_mask=score_mask,
    reference_band_signal=ref_trace,
    sampling_rate_hz=sfreq,
    signal_band_hz=signal_band_hz,
    view_range_hz=VIEW_RANGE_HZ,
)


# ===== 11. Select the best component ==========================================
# score vectors -> selected component index
candidate_indices = [i for i, peak_hz_i in enumerate(peak_freqs) if signal_band_hz[0] <= peak_hz_i <= signal_band_hz[1]]
selection_pool = candidate_indices if candidate_indices else list(range(n_components))
selected_index = max(selection_pool, key=lambda i: (coherence_scores[i], peak_ratios[i], float(eigenvalues[i])))
selected_number = selected_index + 1


# ===== 12. Prepare the plot overlay ===========================================
# windowed reference -> averaged overlay trace
# gt_windows is (n_windows, n_samples); ref_mean_uv is one averaged overlay in microvolts.
gt_windows = preprocessing.extract_event_windows(gt_trace, events[:, 0], window_samples)
ref_mean_uv = preprocessing.filter_signal(gt_windows, sfreq, signal_band_hz[0], signal_band_hz[1]).mean(axis=0) * 1e6


# ===== 13. Save figures and summary ===========================================
# shared plot inputs -> gallery + selected-component figures
summary_plot_kwargs = dict(
    epochs=epochs,
    freq_band_hz=signal_band_hz,
    noise_band_hz=VIEW_RANGE_HZ,
    psd_freq_range_hz=VIEW_RANGE_HZ,
    line_color=plot_helpers.TIMS_CONDITION_COLORS["baseline"],
    reference_frequency_hz=peak_hz,
    temporal_reference_data=ref_mean_uv,
)

plot_helpers.plot_ssd_component_summary(...)
summary_lines = [...]
