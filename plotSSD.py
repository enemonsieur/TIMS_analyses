
def plot_ssd_components(
    epochs,
    ssd,
    ssd_sources,
    freq_band,
    condition_name='',
    n_components=6,
    psd_freq_range=None,
    psd_nperseg=None,
    noise_gap=None,
    noise_flank_width=None,
    save_path=None
):
    """
    Plot SSD components for visual inspection and selection.
    
    Shows topographic patterns and power spectral density for each component.
    
    Parameters
    ----------
    epochs : mne.Epochs
        Epoched data used for SSD
    ssd : mne.decoding.SSD
        Fitted SSD object
    ssd_sources : ndarray, shape (n_components, n_epochs, n_times)
        SSD source activations
    freq_band : tuple
        (low_freq, high_freq) target frequency band
    condition_name : str, default=''
        Label for the condition (e.g., 'STIM', 'REST')
    n_components : int, default=6
        Number of components to display
    psd_freq_range : tuple or None, default=None
        (fmin, fmax) for PSD x-axis. If None, uses target_freq ± 10 Hz
    psd_nperseg : int or None, default=None
        Segment length for Welch PSD. If None, defaults to 1024.
    noise_gap : float or None, default=None
        Gap between signal band and flanks (for plotting only).
    noise_flank_width : float or None, default=None
        Width of each noise flank (for plotting only).
    save_path : str or None, default=None
        Path to save figure
        
    Returns
    -------
    fig : matplotlib.figure.Figure
        Figure object
    """
    from scipy.signal import welch
    
    # Handle complex sources: extract real part for visualization
    if np.iscomplexobj(ssd_sources):
        ssd_sources = np.real(ssd_sources)
    
    freq_low, freq_high = freq_band
    freq_center = (freq_low + freq_high) / 2
    sfreq = epochs.info['sfreq']
    
    # Auto-set PSD range to target ± 10 Hz if not specified
    if psd_freq_range is None:
        psd_freq_range = (max(2, freq_center - 10), min(sfreq/2, freq_center + 10))
    
    # Get spectral ratios
    ssd_sources_mne = np.transpose(ssd_sources, (1, 0, 2))  # Back to MNE format
    ratios, _ = ssd.get_spectral_ratio(ssd_sources_mne)
    
    fig, axes = plt.subplots(2, n_components, figsize=(20, 8))
    
    for i in range(n_components):
        # Top row: Topographic pattern
        pattern = ssd.patterns_[:, i]
        mne.viz.plot_topomap(pattern, epochs.info, ch_type='eeg',
                            axes=axes[0, i], show=False, cmap='RdBu_r')
        axes[0, i].set_title(f'Comp {i+1}\nRatio: {ratios[i]:.2f}',
                            fontweight='bold')
        
        # Bottom row: PSD
        psds = []
        for trial_idx in range(ssd_sources.shape[1]):
            f, psd = welch(
                ssd_sources[i, trial_idx, :],
                fs=sfreq,
                nperseg=psd_nperseg or 1024,
            )
            psds.append(psd)
        mean_psd = np.mean(psds, axis=0)
        
        # Get frequency mask for visible range
        freq_mask = (f >= psd_freq_range[0]) & (f <= psd_freq_range[1])
        visible_psd = mean_psd[freq_mask]
        
        # Calculate reasonable y-limits (avoid extreme log scale)
        psd_max = np.max(visible_psd)
        psd_min = np.min(visible_psd[visible_psd > 0])  # Exclude zeros
        y_range = psd_max / psd_min
        
        # Set y-limits to show 2-3 orders of magnitude around the peak
        if y_range > 1e3:
            ylim_bottom = psd_max / 1e3
            ylim_top = psd_max * 10
        else:
            ylim_bottom = psd_min / 10
            ylim_top = psd_max * 10
        
        axes[1, i].semilogy(f, mean_psd, linewidth=2)
        # Highlight signal band and flanks (estimated around the band)
        axes[1, i].axvspan(freq_low, freq_high, alpha=0.2, color='red')
        if noise_flank_width is not None:
            gap = noise_gap or 0.0
            lf_start = max(0, freq_low - gap - noise_flank_width)
            lf_end = max(0, freq_low - gap)
            hf_start = freq_high + gap
            hf_end = freq_high + gap + noise_flank_width
            axes[1, i].axvspan(lf_start, lf_end, alpha=0.1, color='gray')
            axes[1, i].axvspan(hf_start, hf_end, alpha=0.1, color='gray')
        axes[1, i].set_xlabel('Frequency (Hz)', fontweight='bold')
        axes[1, i].set_ylabel('Power', fontweight='bold')
        axes[1, i].set_xlim(psd_freq_range)  # Focus on target range
        axes[1, i].set_ylim(ylim_bottom, ylim_top)  # Better y-limits
        axes[1, i].grid(True, alpha=0.3)
    
    fig.suptitle(f'SSD Components: {freq_low}-{freq_high} Hz - {condition_name}',
                fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✅ SSD components plot saved: {save_path}")
    
    return fig

