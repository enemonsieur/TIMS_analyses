"""Plotting helpers for ssd_plv_comparison.py"""
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
from mne.time_frequency import tfr_array_morlet
from scipy import linalg
from scipy.signal import hilbert, find_peaks, welch


TIMS_CONDITION_COLORS = {
    "baseline": "gray",
    "30%": "steelblue",
    "100%": "seagreen",
}
TIMS_SIGNAL_BAND_COLOR = "#f9e7cc"
TIMS_NOISE_BAND_COLOR = "#ddebf7"
TIMS_TOPO_CMAP = "RdBu_r"
TIMS_TFR_CMAP = "RdBu_r"


def resolve_channel(raw, *candidates):
    lut = {ch.lower(): ch for ch in raw.ch_names}
    for name in candidates:
        hit = lut.get(name.lower())
        if hit is not None:
            return hit
    raise ValueError(f"None of {candidates} found in channels: {raw.ch_names}")


def detect_pulses(raw, ch="stim", distance_ms=50, prominence=None):
    s = raw.copy().pick([ch]).get_data()[0]
    env = np.abs(hilbert(s))
    sfreq = raw.info.get("sfreq", 1000.0)
    distance = max(1, int(distance_ms / 1000.0 * sfreq))
    if prominence is None:
        prominence = 3.0 * env.std()
    peaks, _ = find_peaks(env, prominence=prominence, distance=distance)
    if len(peaks) == 0:
        above = np.abs(s) > s.mean() + 3 * s.std()
        peaks = np.where(np.diff(above.astype(int)) == 1)[0] + 1
    return peaks, s


def epoch_1d(x, onsets, pre, post):
    ok = onsets[(onsets >= pre) & (onsets < len(x) - post)]
    return np.array([x[o - pre:o + post] for o in ok]), ok


def plv_itpc(phase_ep, t0):
    ph0 = phase_ep[:, t0]
    R = np.abs(np.sum(np.exp(1j * ph0)))
    z, n = R**2 / len(ph0), len(ph0)
    p = max(np.exp(-z) * (1 + (2 * z - z**2) / (4 * n)), 0.0)
    return np.abs(np.mean(np.exp(1j * ph0))), np.abs(np.mean(np.exp(1j * phase_ep), axis=0)), z, p


def prep_eeg(raw):
    #drop = [c for c in raw.ch_names if c.lower() in ("stim", "ground_truth") or c.startswith("STI")]
    return raw.copy().notch_filter([50], notch_widths=2, verbose=False).filter(0.5, 45, verbose=False)


def run_ssd(raw, events, freq, noise, n_comp=6, epoch_duration_s=4.0):
    """GED: COV_signal · w = λ · COV_noise · w for one target frequency band."""
    raw_s = raw.copy().filter(*freq, verbose=False)
    raw_n = raw.copy().filter(*noise, verbose=False)
    raw_n.notch_filter([sum(freq) / 2], notch_widths=freq[1] - freq[0], verbose=False)
    tmax_s = epoch_duration_s - (1.0 / float(raw.info["sfreq"]))
    kw = dict(event_id=1, tmin=0, tmax=tmax_s, baseline=None, proj=False, preload=True, verbose=False)
    d_s = mne.Epochs(raw_s, events, **kw).get_data()
    d_n = mne.Epochs(raw_n, events, **kw).get_data()
    C_s = np.cov(np.concatenate(d_s, axis=-1))
    C_n = np.cov(np.concatenate(d_n, axis=-1))
    evals, evecs = linalg.eig(C_s, C_n)
    idx = np.argsort(np.real(evals))[::-1]
    evals, evecs = np.real(evals[idx]), evecs[:, idx]
    W = evecs.T[:n_comp]                                  # (n_comp, n_ch) spatial filters
    return W, linalg.pinv(evecs.T)[:, :n_comp], evals[:n_comp]


def build_ssd_component_epochs(raw, events, spatial_filters, view_band_hz, epoch_duration_s):
    """Project SSD filters onto epoched view-band data for PSD and TFR inspection."""
    raw_view = raw.copy().filter(*view_band_hz, verbose=False)
    tmax_s = epoch_duration_s - (1.0 / float(raw.info["sfreq"]))
    epochs_view = mne.Epochs(
        raw_view,
        events,
        event_id=1,
        tmin=0.0,
        tmax=tmax_s,
        baseline=None,
        proj=False,
        preload=True,
        verbose=False,
    )
    epoch_data = epochs_view.get_data()
    component_epochs = np.asarray(np.einsum("kc,ect->ket", spatial_filters, epoch_data), dtype=float)
    return epochs_view, component_epochs


def plot_ssd_component_summary(
    epochs,
    spatial_patterns,
    component_epochs,
    spectral_ratios,
    freq_band_hz,
    condition_name,
    output_path,
    noise_band_hz=None,
    n_components=6,
    psd_freq_range_hz=None,
    psd_nperseg=None,
    line_color="steelblue",
    reference_frequency_hz=None,
    comparison_component_epochs=None,
    comparison_color="gray",
    comparison_label=None,
    spectral_ratio_label="Eval",
):
    """Save a plotSSD-style SSD component overview with topomaps and mean PSDs."""
    if np.iscomplexobj(component_epochs):
        component_epochs = np.real(component_epochs)
    if comparison_component_epochs is not None and np.iscomplexobj(comparison_component_epochs):
        comparison_component_epochs = np.real(comparison_component_epochs)

    n_display = min(
        int(n_components),
        int(component_epochs.shape[0]),
        int(spatial_patterns.shape[1]),
        int(len(spectral_ratios)),
    )
    if n_display < 1:
        raise ValueError("No SSD components are available for plotting.")

    freq_low, freq_high = map(float, freq_band_hz)
    sfreq = float(epochs.info["sfreq"])
    freq_center = (freq_low + freq_high) / 2.0
    if psd_freq_range_hz is None:
        psd_freq_range_hz = (max(2.0, freq_center - 10.0), min(sfreq / 2.0, freq_center + 10.0))

    fig, axes = plt.subplots(2, n_display, figsize=(3.5 * n_display, 7.0), constrained_layout=True)
    if n_display == 1:
        axes = np.asarray(axes, dtype=object).reshape(2, 1)

    for component_index in range(n_display):
        topomap_axis = axes[0, component_index]
        pattern = np.asarray(spatial_patterns[:, component_index], dtype=float)
        mne.viz.plot_topomap(
            pattern,
            epochs.info,
            ch_type="eeg",
            axes=topomap_axis,
            show=False,
            cmap=TIMS_TOPO_CMAP,
        )
        topomap_axis.set_title(
            f"Comp {component_index + 1}\n{spectral_ratio_label}: {float(spectral_ratios[component_index]):.2f}",
            fontweight="bold",
        )

        psd_axis = axes[1, component_index]
        frequencies_hz, psd_values = welch(
            component_epochs[component_index],
            fs=sfreq,
            nperseg=min(int(psd_nperseg or 1024), int(component_epochs.shape[-1])),
            axis=-1,
        )
        mean_psd = np.mean(psd_values, axis=0)
        visible_mask = (frequencies_hz >= psd_freq_range_hz[0]) & (frequencies_hz <= psd_freq_range_hz[1])
        positive_visible_psd = mean_psd[visible_mask][mean_psd[visible_mask] > 0]

        comparison_mean_psd = None
        if comparison_component_epochs is not None:
            comparison_freqs_hz, comparison_psd_values = welch(
                comparison_component_epochs[component_index],
                fs=sfreq,
                nperseg=min(int(psd_nperseg or 1024), int(comparison_component_epochs.shape[-1])),
                axis=-1,
            )
            comparison_mean_psd = np.mean(comparison_psd_values, axis=0)
            comparison_visible_mask = (comparison_freqs_hz >= psd_freq_range_hz[0]) & (comparison_freqs_hz <= psd_freq_range_hz[1])
            positive_visible_psd = np.concatenate(
                [positive_visible_psd, comparison_mean_psd[comparison_visible_mask][comparison_mean_psd[comparison_visible_mask] > 0]]
            )

        if positive_visible_psd.size == 0:
            raise RuntimeError("Visible PSD is non-positive for SSD component plotting.")
        psd_max = float(np.max(positive_visible_psd))
        psd_min = float(np.min(positive_visible_psd))
        if psd_max / psd_min > 1e3:
            ylim_bottom = psd_max / 1e3
            ylim_top = psd_max * 10.0
        else:
            ylim_bottom = psd_min / 3.0
            ylim_top = psd_max * 3.0

        psd_axis.semilogy(frequencies_hz, mean_psd, linewidth=2.0, color=line_color, label=condition_name)
        if comparison_mean_psd is not None:
            psd_axis.semilogy(
                comparison_freqs_hz,
                comparison_mean_psd,
                linewidth=1.3,
                color=comparison_color,
                linestyle="--",
                alpha=0.9,
                label=comparison_label,
            )
        psd_axis.axvspan(freq_low, freq_high, alpha=0.8, color=TIMS_SIGNAL_BAND_COLOR)
        if noise_band_hz is not None:
            noise_low, noise_high = map(float, noise_band_hz)
            if noise_low < freq_low:
                psd_axis.axvspan(noise_low, freq_low, alpha=0.55, color=TIMS_NOISE_BAND_COLOR)
            if noise_high > freq_high:
                psd_axis.axvspan(freq_high, noise_high, alpha=0.55, color=TIMS_NOISE_BAND_COLOR)
        if reference_frequency_hz is not None:
            psd_axis.axvline(float(reference_frequency_hz), color="darkorange", lw=1.0, ls="--")
        psd_axis.set_xlabel("Frequency (Hz)", fontweight="bold")
        psd_axis.set_ylabel("PSD (log scale)", fontweight="bold")
        psd_axis.set_xlim(psd_freq_range_hz)
        psd_axis.set_ylim(ylim_bottom, ylim_top)
        psd_axis.grid(True, alpha=0.25)
        if comparison_mean_psd is not None and component_index == 0:
            psd_axis.legend(fontsize=8, loc="upper right")

    fig.suptitle(
        f"SSD Components: {freq_low:.0f}-{freq_high:.0f} Hz - {condition_name}",
        fontsize=15,
        fontweight="bold",
    )
    output_path = Path(output_path)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_ssd_component_tfr(
    epochs,
    component_epochs,
    spectral_ratios,
    condition_name,
    output_path,
    n_components=3,
    frequency_range_hz=(4.0, 25.0),
    display_window_s=None,
    reference_frequency_hz=None,
    spectral_ratio_label="Eval",
):
    """Save an OFF-epoch Morlet TFR as absolute log-power with Morlet-safe cropping."""
    if np.iscomplexobj(component_epochs):
        component_epochs = np.real(component_epochs)

    n_display = min(int(n_components), int(component_epochs.shape[0]), int(len(spectral_ratios)))
    if n_display < 1:
        raise ValueError("No SSD components are available for TFR plotting.")

    epoch_times_s = np.asarray(epochs.times, dtype=float)
    frequencies_hz = np.arange(float(frequency_range_hz[0]), float(frequency_range_hz[1]) + 1.0, 1.0, dtype=float)
    n_cycles = np.clip(frequencies_hz / 2.0, 3.0, 7.0)
    half_wavelet_s = n_cycles / (2.0 * frequencies_hz)
    max_half_wavelet_s = float(np.max(half_wavelet_s))
    pad_samples = int(np.ceil(max_half_wavelet_s * float(epochs.info["sfreq"])))
    if pad_samples < 1:
        raise RuntimeError("Computed non-positive padding for SSD TFR.")

    display_start_s = float(display_window_s[0]) if display_window_s is not None else float(epoch_times_s[0] + max_half_wavelet_s)
    display_stop_s = (
        float(display_window_s[1])
        if display_window_s is not None and display_window_s[1] is not None
        else float(epoch_times_s[-1] - max_half_wavelet_s)
    )
    safe_display_start_s = max(display_start_s, float(epoch_times_s[0] + max_half_wavelet_s))
    safe_display_stop_s = min(display_stop_s, float(epoch_times_s[-1] - max_half_wavelet_s))
    display_mask = (epoch_times_s >= safe_display_start_s) & (epoch_times_s <= safe_display_stop_s)
    if not np.any(display_mask):
        raise ValueError("SSD TFR display window does not overlap the Morlet-safe epoch segment.")

    centered_components = component_epochs[:n_display] - component_epochs[:n_display].mean(axis=-1, keepdims=True)
    morlet_input = np.transpose(centered_components, (1, 0, 2))
    padded_input = np.pad(morlet_input, ((0, 0), (0, 0), (pad_samples, pad_samples)), mode="reflect")
    power = np.asarray(
        tfr_array_morlet(
            padded_input,
            sfreq=float(epochs.info["sfreq"]),
            freqs=frequencies_hz,
            n_cycles=n_cycles,
            output="power",
            zero_mean=True,
        )[..., pad_samples:-pad_samples],
        dtype=float,
    )
    power_db = 10.0 * np.log10(power + 1e-30)
    mean_power_db = np.mean(power_db, axis=0)[:, :, display_mask]
    color_min = float(np.nanpercentile(mean_power_db, 5))
    color_max = float(np.nanpercentile(mean_power_db, 98))
    if not np.isfinite(color_min) or not np.isfinite(color_max) or color_max <= color_min:
        color_min = float(np.nanmin(mean_power_db))
        color_max = float(np.nanmax(mean_power_db))
    if not np.isfinite(color_min) or not np.isfinite(color_max) or color_max <= color_min:
        color_min, color_max = -6.0, 6.0

    fig, axes = plt.subplots(1, n_display, figsize=(4.2 * n_display, 4.2), constrained_layout=True)
    axes = np.atleast_1d(axes)
    image = None
    extent = [float(epoch_times_s[display_mask][0]), float(epoch_times_s[display_mask][-1]), float(frequencies_hz[0]), float(frequencies_hz[-1])]
    for component_index, axis in enumerate(axes):
        image = axis.imshow(
            mean_power_db[component_index],
            aspect="auto",
            origin="lower",
            extent=extent,
            cmap=TIMS_TFR_CMAP,
            vmin=color_min,
            vmax=color_max,
        )
        if reference_frequency_hz is not None:
            axis.axhline(float(reference_frequency_hz), color="darkorange", lw=1.0, ls="--")
        axis.set_title(f"Comp {component_index + 1} | {spectral_ratio_label} {float(spectral_ratios[component_index]):.2f}")
        axis.set_xlabel("Time in OFF epoch (s)")
        if component_index == 0:
            axis.set_ylabel("Frequency (Hz)")

    if image is not None:
        colorbar = fig.colorbar(image, ax=axes, fraction=0.03, pad=0.03)
        colorbar.set_label("Absolute log-power (dB)")
    fig.suptitle(f"SSD Component TFR: {condition_name}", fontsize=14, fontweight="bold")
    output_path = Path(output_path)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output_path



def circplot(ax, phases, plv, p, title, color):
    """Polar histogram + mean resultant vector arrow."""
    ax.hist(phases, bins=36, density=True, color=color, alpha=0.7, edgecolor="w", lw=0.5)
    ax.plot(phases, np.ones(len(phases)) * ax.get_ylim()[1] * 0.95, "ko", ms=3, alpha=0.4)
    ang = np.angle(np.mean(np.exp(1j * phases)))
    ax.annotate("", xy=(ang, plv * ax.get_ylim()[1]), xytext=(0, 0),
                arrowprops=dict(arrowstyle="-|>", color="red", lw=3))
    # Only show the provided title, no significance text
    ax.set_title(title, pad=20, fontsize=12)


def plot_timeseries(outdir, cz, ssd, stim, onsets, sfreq, evals, ref):
    """Fig 1: raw Cz 10 Hz vs SSD 10 Hz with stim overlay."""
    scale_factor = 1e-8 # Display amplitude in units of 10^-8
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(16, 8), constrained_layout=True)
    fig.suptitle("avg. 10Hz time course of STIM ON vs. STIM ON + SSD", fontsize=16, fontweight="bold")
    mid = onsets[len(onsets) // 2]
    ws, we = mid - int(6 * sfreq), mid + int(6 * sfreq)
    tw = np.arange(ws, we) / sfreq
    # Compute shared y-axis limits for both signals
    cz_real = np.real(cz) / scale_factor
    ssd_real = np.real(ssd) / scale_factor
    # Compute independent y-limits for each signal
    cz_min = np.min(cz_real[ws:we])
    cz_max = np.max(cz_real[ws:we])
    ssd_min = np.min(ssd_real[ws:we])
    ssd_max = np.max(ssd_real[ws:we])
    cz_abs_max = max(abs(cz_min), abs(cz_max))
    ssd_abs_max = max(abs(ssd_min), abs(ssd_max))
    # Each subplot gets its own y-limit
    cz_lim = (-1.1 * cz_abs_max, 1.1 * cz_abs_max)
    ssd_lim = (-1.1 * ssd_abs_max, 1.1 * ssd_abs_max)
    for ax, sig, col, lbl, ttl, y_lim in [
        (a1, cz_real, "b", "STIM 10Hz", "BEFORE SSD: Cz 8-12 Hz", cz_lim),
        (a2, ssd_real, "darkgreen", "SSD 10Hz", "AFTER SSD: SSD 8-12 Hz", ssd_lim),
    ]:
        ax.set_title(ttl)
        ax.plot(tw, sig[ws:we], col, lw=1.2, label=lbl)
        ax.set_ylim(y_lim)
        ax.set_ylabel("Amplitude (x$10^{-8}$)")
        for o in onsets:
            pt = o / sfreq
            if tw[0] <= pt <= tw[-1]:
                ax.axvline(pt, color="r", ls="--", lw=0.6, alpha=0.4)
        handles, labels = ax.get_legend_handles_labels()
        filtered = [(h, l) for h, l in zip(handles, labels) if l in ("STIM 10Hz", "SSD 10Hz")]
        if filtered:
            ax.legend([h for h, _ in filtered], [l for _, l in filtered], loc="upper right")
        else:
            ax.legend().set_visible(False)
    a2.set_xlabel("Time (s)")
    fig.savefig(str(outdir / "fig1_before_vs_after_ssd.png"), dpi=200, bbox_inches="tight")


def plot_plv(outdir, phases_b, phases_s, phases_ssd, plvs, ps, nb, ns, ref):
    """Fig 2: three polar PLV plots side by side."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), subplot_kw=dict(projection="polar"),
                             constrained_layout=True)
    fig.suptitle("Circular Plot of Phase Coherence between Pulses and 10Hz signal.", fontsize=14, fontweight="bold")
    # Prepare titles with rounded PLV/p as requested
    plv_b, plv_s, plv_ssd = plvs
    p_b, p_s, p_ssd = ps
    # NO-STIM: PLV=0.04, p=0.65
    title_b = f"NO-STIM: PLV={plv_b:.2f}, p={p_b:.2f}"
    # STIM: PLV=0.96, p<0.01 if p-value is very small, else show rounded value
    if p_s < 0.01:
        title_s = f"STIM: PLV={plv_s:.2f}, p<0.01"
    else:
        title_s = f"STIM: PLV={plv_s:.2f}, p={p_s:.2f}"
    # STIM+SSD: PLV=..., p=... (rounded)
    title_ssd = f"STIM + SSD: PLV={plv_ssd:.2f}, p={p_ssd:.2f}"
    circplot(axes[0], phases_b,   plv_b, p_b, title_b, "gray")
    circplot(axes[1], phases_s,   plv_s, p_s, title_s, "steelblue")
    circplot(axes[2], phases_ssd, plv_ssd, p_ssd, title_ssd, "seagreen")
    fig.savefig(str(outdir / "fig2_plv_3conditions.png"), dpi=200, bbox_inches="tight")


def plot_itpc(outdir, t_ep, itpc_b, itpc_s, itpc_ss, plvs, ps, chance, evals, nb, ns, ref, t0):
    """Fig 3: ITPC time courses for all 3 conditions."""
    fig, ax = plt.subplots(figsize=(20, 6), constrained_layout=True)
    fig.suptitle("ITPC: Inter-Trial Phase Coherence", fontsize=14, fontweight="bold")
    # Convert time to ms for x-axis
    t_ep_ms = t_ep * 1000
    ax.plot(t_ep_ms, itpc_b,  "gray",      lw=2,          label="BASELINE")
    ax.plot(t_ep_ms, itpc_s,  "steelblue", lw=2, ls="--", label="STIM raw")
    ax.plot(t_ep_ms, itpc_ss, "green",     lw=2.5,        label="STIM SSD")
    ax.axvline(0, color="red", ls="--", lw=2, label="Pulse onset")
    ax.axhline(chance, color="gray", ls=":", lw=1.5, label=f"Chance ({chance:.3f})")
    ax.set(xlabel="Time from pulse (ms)", ylabel="ITPC",
        ylim=(0, max(0.3, max(itpc_ss.max(), itpc_s.max(), itpc_b.max()) * 1.3)))
    ax.legend(loc="upper right", fontsize=10)
    fig.savefig(str(outdir / "fig3_itpc_3conditions.png"), dpi=200, bbox_inches="tight")


def plot_trials(outdir, t_ep, ep_b, ep_s, ep_ssd, nb, ns, ref):
    """Fig 4: single-trial image plots for all 3 conditions.
        t_ep: time vector for epochs (in seconds)
        ep_b, ep_s, ep_ssd: (n_trials, n_timepoints) arrays of analytic signal values for each condition
        nb, ns: number of valid trials in baseline and stim conditions (for y-axis limits)

        This code calculate the 95th percentile of the absolute values across 
        all trials and time points for each condition to determine 
        a common color scale limit (vmin, vmax) for the images. 
        This ensures that the color representation of amplitude is consistent across conditions, 
        allowing for a more meaningful visual comparison of single-trial activity patterns.
    """
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), constrained_layout=True)
    fig.suptitle("Raster Plot of 10 Hz Amplitude", fontsize=15, fontweight="bold")
    for ax, data, n, title in [
        (axes[0], np.real(ep_b),   nb, f"NO STIM - 10 Hz"),
        (axes[1], np.real(ep_s),   ns, f"STIM - 10 Hz"),
        (axes[2], np.real(ep_ssd), ns, "STIM + SSD - 10 Hz"),
    ]:  # Read Color = higher amplitude, blue = lower amplitude
        # 
        vm = np.percentile(np.abs(data), 95)
        ax.imshow(data, aspect="auto", cmap="RdBu_r",
                  extent=[t_ep[0], t_ep[-1], n, 0], vmin=-vm, vmax=vm)
        ax.axvline(0, color="k", ls="--", lw=2)
        ax.set_ylabel("Trial"); ax.set_title(title)
    axes[2].set_xlabel("Time from pulse (s)")
    fig.savefig(str(outdir / "fig4_single_trial_images.png"), dpi=200, bbox_inches="tight")


def plot_plv_group(outdir, labels, phases, plvs, ps, title, filename):
    """Generic polar PLV plot for 2..N conditions."""
    n = len(labels)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 6), subplot_kw=dict(projection="polar"), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()
    colors = ["gray", "steelblue", "seagreen", "darkorange", "slateblue"]
    fig.suptitle(title, fontsize=14, fontweight="bold")
    for i, (ax, lbl, ph, plv, p) in enumerate(zip(axes, labels, phases, plvs, ps)):
        ptxt = "p<0.01" if p < 0.01 else f"p={p:.2f}"
        circplot(ax, ph, plv, p, f"{lbl}: PLV={plv:.2f}, {ptxt}", colors[i % len(colors)])
    fig.savefig(str(outdir / filename), dpi=200, bbox_inches="tight")


def plot_itpc_group(outdir, t_ep, labels, itpcs, chance, title, filename):
    """Generic ITPC line plot for 2..N conditions."""
    fig, ax = plt.subplots(figsize=(20, 6), constrained_layout=True)
    fig.suptitle(title, fontsize=14, fontweight="bold")
    t_ep_ms = t_ep * 1000
    colors = ["gray", "steelblue", "green", "darkorange", "slateblue"]
    styles = ["-", "--", "-", "--", "-."]
    ymax = 0.3
    for i, (lbl, itpc) in enumerate(zip(labels, itpcs)):
        ymax = max(ymax, np.max(itpc) * 1.3)
        ax.plot(t_ep_ms, itpc, color=colors[i % len(colors)], lw=2.3, ls=styles[i % len(styles)], label=lbl)
    ax.axvline(0, color="red", ls="--", lw=2, label="Pulse onset")
    ax.axhline(chance, color="gray", ls=":", lw=1.5, label=f"Chance ({chance:.3f})")
    ax.set(xlabel="Time from pulse (ms)", ylabel="ITPC", ylim=(0, ymax))
    ax.legend(loc="upper right", fontsize=10)
    fig.savefig(str(outdir / filename), dpi=200, bbox_inches="tight")


def plot_exp04_channel_artifact_qc(pre_raw, post_raw, channel_names, output_directory, trace_duration_s=20.0) -> Path:
    """Save a compact raw-trace and PSD QC figure for selected exp04 channels."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    qc_channels = [channel_name for channel_name in channel_names if channel_name in pre_raw.ch_names and channel_name in post_raw.ch_names]
    if not qc_channels:
        raise ValueError("No requested QC channels are present in both pre and post raw recordings.")

    sfreq = float(pre_raw.info["sfreq"])
    trace_samples = int(round(trace_duration_s * sfreq))
    fig_qc, axes_qc = plt.subplots(len(qc_channels), 2, figsize=(10.8, 3.2 * len(qc_channels)), constrained_layout=True)
    if len(qc_channels) == 1:
        axes_qc = np.asarray([axes_qc], dtype=object)

    for row_index, channel_name in enumerate(qc_channels):
        pre_trace = pre_raw.copy().pick([channel_name]).get_data()[0]
        post_trace = post_raw.copy().pick([channel_name]).get_data()[0]
        pre_trace = pre_trace[:trace_samples] - np.mean(pre_trace[:trace_samples])
        post_trace = post_trace[:trace_samples] - np.mean(post_trace[:trace_samples])
        time_seconds = np.arange(pre_trace.size, dtype=float) / sfreq

        trace_axis = axes_qc[row_index, 0]
        trace_axis.plot(time_seconds, pre_trace * 1e6, color="gray", lw=1.0, label="Pre")
        trace_axis.plot(time_seconds, post_trace * 1e6, color="steelblue", lw=1.0, label="Post")
        trace_axis.set_title(f"{channel_name} raw trace")
        trace_axis.set_xlabel("Time (s)")
        trace_axis.set_ylabel("Amplitude (uV)")
        trace_axis.grid(alpha=0.2)
        trace_axis.legend(loc="upper right")

        psd_axis = axes_qc[row_index, 1]
        pre_freqs, pre_psd = welch(pre_raw.copy().pick([channel_name]).get_data()[0], fs=sfreq, nperseg=min(4096, pre_raw.n_times))
        post_freqs, post_psd = welch(post_raw.copy().pick([channel_name]).get_data()[0], fs=sfreq, nperseg=min(4096, post_raw.n_times))
        visible_mask = (pre_freqs >= 2.0) & (pre_freqs <= 45.0)
        pre_psd_db = 10.0 * np.log10(pre_psd + 1e-30)
        post_psd_db = 10.0 * np.log10(post_psd + 1e-30)
        visible_values = np.concatenate([pre_psd_db[visible_mask], post_psd_db[visible_mask]])
        y_pad = max(0.8, 0.08 * (float(np.max(visible_values)) - float(np.min(visible_values))))
        psd_axis.plot(pre_freqs[visible_mask], pre_psd_db[visible_mask], color="gray", lw=1.4, label="Pre")
        psd_axis.plot(post_freqs[visible_mask], post_psd_db[visible_mask], color="steelblue", lw=1.4, label="Post")
        psd_axis.set_title(f"{channel_name} PSD")
        psd_axis.set_xlabel("Frequency (Hz)")
        psd_axis.set_ylabel("Power (dB)")
        psd_axis.set_xlim(2.0, 45.0)
        psd_axis.set_ylim(float(np.min(visible_values)) - y_pad, float(np.max(visible_values)) + y_pad)
        psd_axis.grid(alpha=0.2)
        psd_axis.legend(loc="upper right")

    output_path = output_directory / "exp04_channel_artifact_qc.png"
    fig_qc.savefig(output_path, dpi=220)
    plt.close(fig_qc)
    return output_path


def plot_trials_group(outdir, t_ep, labels, epochs, title, filename):
    """Generic single-trial raster plot for 2..N conditions."""
    n = len(labels)
    fig, axes = plt.subplots(n, 1, figsize=(14, 4 * n), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()
    fig.suptitle(title, fontsize=15, fontweight="bold")
    for ax, lbl, ep in zip(axes, labels, epochs):
        data = np.real(ep)
        vm = np.percentile(np.abs(data), 95)
        ax.imshow(data, aspect="auto", cmap="RdBu_r",
                  extent=[t_ep[0], t_ep[-1], data.shape[0], 0], vmin=-vm, vmax=vm)
        ax.axvline(0, color="k", ls="--", lw=2)
        ax.set_ylabel("Trial")
        ax.set_title(lbl)
    axes[-1].set_xlabel("Time from pulse (s)")
    fig.savefig(str(outdir / filename), dpi=200, bbox_inches="tight")


def plot_tep_triptych(evoked_pre, evoked_stim, evoked_post, output_path) -> None:
    """Plot three shared-axis butterfly subplots: Pre | Stim | Post."""
    evokeds = [
        ("Pre", evoked_pre, "gray"),
        ("Stim", evoked_stim, "steelblue"),
        ("Post", evoked_post, "seagreen"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharex=True, sharey=True, constrained_layout=True)

    all_traces_uv = [evoked.data * 1e6 for _, evoked, _ in evokeds]
    y_abs_max = max(float(np.max(np.abs(traces_uv))) for traces_uv in all_traces_uv)

    for axis, (label, evoked, color) in zip(axes, evokeds):
        time_ms = evoked.times * 1000.0
        traces_uv = evoked.data * 1e6
        for trace_uv in traces_uv:
            axis.plot(time_ms, trace_uv, color=color, lw=0.9, alpha=0.45)
        axis.plot(time_ms, traces_uv.mean(axis=0), color="black", lw=2.0, label="Average")
        axis.set_title(f"{label} (n={evoked.nave})")
        axis.set_xlabel("Time (ms)")
        axis.set_xticks(np.arange(100, 502, 50))
        axis.grid(alpha=0.2)
        axis.set_ylim(-1.05 * y_abs_max, 1.05 * y_abs_max)
        axis.legend(loc="upper right")

    axes[0].set_ylabel("Amplitude (uV)")
    fig.savefig(Path(output_path), dpi=220)
    plt.close(fig)


def plot_pre_post_dynamics_figures(
    pre_power_summary,
    post_power_summary,
    pre_power_window_summary,
    post_power_window_summary,
    pre_theta_plv_summary,
    post_theta_plv_summary,
    pre_alpha_plv_summary,
    post_alpha_plv_summary,
    stats_rows,
    output_directory,
) -> dict[str, Path]:
    """Save separate PSD, power, and PLV figures for the pre/post dynamics summary."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    stats_lookup = {str(row["metric"]): row for row in stats_rows}
    saved_paths: dict[str, Path] = {}

    # Tighten the PSD view to the actual dB span and mark theta/alpha directly on the spectrum.
    frequencies_hz = np.asarray(pre_power_summary["frequencies_hz"], dtype=float)
    pre_psd = np.asarray(pre_power_summary["roi_mean_psd"], dtype=float)
    post_psd = np.asarray(post_power_summary["roi_mean_psd"], dtype=float)
    pre_psd_db = 10.0 * np.log10(pre_psd + 1e-30)
    post_psd_db = 10.0 * np.log10(post_psd + 1e-30)
    visible_mask = (frequencies_hz >= 1.0) & (frequencies_hz <= 20.0)
    visible_values_db = np.concatenate([pre_psd_db[visible_mask], post_psd_db[visible_mask]])
    visible_min_db = float(np.min(visible_values_db))
    visible_max_db = float(np.max(visible_values_db))
    y_pad = max(0.8, 0.08 * (visible_max_db - visible_min_db))
    y_min = visible_min_db - y_pad
    y_max = visible_max_db + y_pad

    fig_psd, axis_psd = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    axis_psd.axvspan(4.0, 7.0, color="#e6f0fa", alpha=0.9, label="Theta band")
    axis_psd.axvspan(8.0, 12.0, color="#f9e7cc", alpha=0.9, label="Alpha band")
    axis_psd.plot(frequencies_hz, pre_psd_db, lw=2.0, color="gray", label="Pre")
    axis_psd.plot(frequencies_hz, post_psd_db, lw=2.0, color="steelblue", label="Post")
    axis_psd.set_title("ROI Mean PSD")
    axis_psd.set_xlabel("Frequency (Hz)")
    axis_psd.set_ylabel("Power (dB)")
    axis_psd.set_xlim(1.0, 20.0)
    axis_psd.set_ylim(y_min, y_max)
    axis_psd.margins(x=0.01, y=0.0)
    axis_psd.grid(alpha=0.2)
    axis_psd.legend(loc="upper right")
    axis_psd.set_ylim(y_min, y_max)
    psd_path = output_directory / "exp04_pre_post_psd.png"
    fig_psd.savefig(psd_path, dpi=220)
    plt.close(fig_psd)
    saved_paths["psd"] = psd_path

    # Show raw theta/alpha power on a log scale and keep the ratio on its own y-axis.
    bar_width = 0.34
    rng = np.random.default_rng(0)
    fig_power, axis_power = plt.subplots(figsize=(7.4, 4.8), constrained_layout=True)
    axis_ratio = axis_power.twinx()
    power_metrics = ["theta_power", "alpha_power"]
    power_titles = ["Theta", "Alpha"]
    x_power = np.arange(len(power_metrics), dtype=float)
    axis_power.bar(
        x_power - bar_width / 2,
        [float(pre_power_window_summary[key]) for key in power_metrics],
        width=bar_width,
        color="gray",
        alpha=0.85,
        label="Pre",
    )
    axis_power.bar(
        x_power + bar_width / 2,
        [float(post_power_window_summary[key]) for key in power_metrics],
        width=bar_width,
        color="steelblue",
        alpha=0.85,
        label="Post",
    )
    power_window_lookup = {
        "theta_power": (
            np.asarray(pre_power_window_summary["theta_power_per_window"], dtype=float),
            np.asarray(post_power_window_summary["theta_power_per_window"], dtype=float),
        ),
        "alpha_power": (
            np.asarray(pre_power_window_summary["alpha_power_per_window"], dtype=float),
            np.asarray(post_power_window_summary["alpha_power_per_window"], dtype=float),
        ),
    }
    for index, metric in enumerate(power_metrics):
        pre_values, post_values = power_window_lookup[metric]
        pre_jitter = rng.uniform(-0.05, 0.05, size=pre_values.size)
        post_jitter = rng.uniform(-0.05, 0.05, size=post_values.size)
        axis_power.scatter(
            np.full(pre_values.size, x_power[index] - bar_width / 2) + pre_jitter,
            pre_values,
            s=8,
            color="black",
            alpha=0.22,
            linewidths=0,
        )
        axis_power.scatter(
            np.full(post_values.size, x_power[index] + bar_width / 2) + post_jitter,
            post_values,
            s=8,
            color="black",
            alpha=0.22,
            linewidths=0,
        )
    ratio_x = 2.3
    pre_ratio = np.asarray(pre_power_window_summary["theta_alpha_ratio_per_window"], dtype=float)
    post_ratio = np.asarray(post_power_window_summary["theta_alpha_ratio_per_window"], dtype=float)
    axis_ratio.bar(ratio_x - bar_width / 2, float(pre_power_window_summary["theta_alpha_ratio"]), width=bar_width, color="gray", alpha=0.45)
    axis_ratio.bar(ratio_x + bar_width / 2, float(post_power_window_summary["theta_alpha_ratio"]), width=bar_width, color="steelblue", alpha=0.45)
    axis_ratio.scatter(
        np.full(pre_ratio.size, ratio_x - bar_width / 2) + rng.uniform(-0.05, 0.05, size=pre_ratio.size),
        pre_ratio,
        s=9,
        color="black",
        alpha=0.22,
        linewidths=0,
    )
    axis_ratio.scatter(
        np.full(post_ratio.size, ratio_x + bar_width / 2) + rng.uniform(-0.05, 0.05, size=post_ratio.size),
        post_ratio,
        s=9,
        color="black",
        alpha=0.22,
        linewidths=0,
    )
    axis_power.set_title("ROI Band Power")
    axis_power.set_xticks(x_power)
    axis_power.set_xticklabels(power_titles)
    axis_power.set_yscale("log")
    axis_power.set_ylabel("Band power (V^2, log scale)")
    axis_ratio.set_ylabel("Theta / Alpha ratio")
    axis_power.set_xlim(-0.6, 2.9)
    axis_power.text(ratio_x, 0.02, "Theta/Alpha", transform=axis_power.get_xaxis_transform(), ha="center", va="bottom")
    for index, metric in enumerate(power_metrics):
        axis_power.text(
            x_power[index],
            axis_power.get_ylim()[1] / 1.15,
            f"q={float(stats_lookup[metric]['q_value']):.3f}",
            ha="center",
            va="top",
            fontsize=9,
        )
    axis_ratio.text(
        ratio_x,
        axis_ratio.get_ylim()[1] * 0.96,
        f"q={float(stats_lookup['theta_alpha_ratio']['q_value']):.3f}",
        ha="center",
        va="top",
        fontsize=9,
    )
    axis_power.grid(axis="y", alpha=0.2)
    axis_power.legend(loc="upper right")
    power_path = output_directory / "exp04_pre_post_band_power.png"
    fig_power.savefig(power_path, dpi=220)
    plt.close(fig_power)
    saved_paths["band_power"] = power_path

    # Plot PLV magnitudes directly; polar phase-angle histograms do not show
    # the actual scalar PLV summary that is being compared across conditions.
    fig_plv, axes_plv = plt.subplots(1, 2, figsize=(10.2, 4.8), constrained_layout=True, sharey=True)
    plv_panels = [
        (
            axes_plv[0],
            "Theta",
            pre_theta_plv_summary,
            post_theta_plv_summary,
            float(stats_lookup["theta_plv"]["q_value"]),
        ),
        (
            axes_plv[1],
            "Alpha",
            pre_alpha_plv_summary,
            post_alpha_plv_summary,
            float(stats_lookup["alpha_plv"]["q_value"]),
        ),
    ]
    rng_plv = np.random.default_rng(1)
    for axis_plv, label, pre_summary, post_summary, q_value in plv_panels:
        pre_values = np.asarray(pre_summary["window_plv"], dtype=float)
        post_values = np.asarray(post_summary["window_plv"], dtype=float)
        axis_plv.scatter(
            np.full(pre_values.size, 0.0) + rng_plv.uniform(-0.06, 0.06, size=pre_values.size),
            pre_values,
            s=16,
            color="gray",
            alpha=0.5,
            linewidths=0,
            label="Pre",
        )
        axis_plv.scatter(
            np.full(post_values.size, 1.0) + rng_plv.uniform(-0.06, 0.06, size=post_values.size),
            post_values,
            s=16,
            color="steelblue",
            alpha=0.5,
            linewidths=0,
            label="Post",
        )
        axis_plv.plot([0.0, 1.0], [float(pre_summary["mean_plv"]), float(post_summary["mean_plv"])], color="black", lw=1.2)
        axis_plv.scatter([0.0, 1.0], [float(pre_summary["mean_plv"]), float(post_summary["mean_plv"])], s=36, color=["gray", "steelblue"], zorder=3)
        axis_plv.set_xticks([0.0, 1.0])
        axis_plv.set_xticklabels(["Pre", "Post"])
        axis_plv.set_title(f"{label} PLV\nq={q_value:.3f}")
        axis_plv.grid(axis="y", alpha=0.2)
        axis_plv.set_xlim(-0.35, 1.35)
    axes_plv[0].set_ylabel("PLV")
    axes_plv[1].legend(loc="upper right")
    plv_path = output_directory / "exp04_pre_post_plv_summary.png"
    fig_plv.savefig(plv_path, dpi=220)
    plt.close(fig_plv)
    saved_paths["plv"] = plv_path
    return saved_paths


def plot_cz_pipeline_steps(stage_epochs, channel, output_path):
    """Plot one subplot row per pipeline stage for a single channel.

    Parameters
    ----------
    stage_epochs : dict[str, mne.Epochs]
        Ordered dict of {label: Epochs object}. One subplot per entry.
    channel : str
        Channel name to extract (e.g. "Cz").
    output_path : str or Path
        Where to save the figure (PNG).
    """
    from pathlib import Path

    stage_names = list(stage_epochs.keys())
    fig, axes = plt.subplots(
        len(stage_names), 1,
        figsize=(12, 2.8 * len(stage_names)),
        constrained_layout=True,
        sharex=False,   # allow each stage to have its own x range
    )
    axes = np.atleast_1d(axes)

    for ax, name in zip(axes, stage_names):
        epochs = stage_epochs[name]
        # mean across trials, convert V → µV
        trace = epochs.get_data(picks=channel).mean(axis=0).squeeze() * 1e6
        time = epochs.times
        ax.plot(time, trace, lw=1.0, color="steelblue")
        ax.axvline(0, color="k", lw=0.8, ls="--", label="pulse")
        ax.set_title(f"{name}  —  {channel}", fontsize=10)
        ax.set_ylabel("µV")
        ax.grid(alpha=0.25)

    axes[-1].set_xlabel("Time (s)")
    fig.savefig(str(Path(output_path)), dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_stage_overlay_with_ground_truth(
    stage_eeg_traces_uv,
    stage_ground_truth_traces_uv,
    stage_time_axes_seconds,
    zoom_window_s,
    output_path,
    eeg_label="EEG",
    ground_truth_label="ground_truth",
):
    """Plot one zoomed subplot per stage with z-scored EEG and ground_truth overlays."""
    stage_names = list(stage_eeg_traces_uv.keys())
    if not stage_names:
        raise ValueError("stage_eeg_traces_uv is empty.")
    if stage_names != list(stage_ground_truth_traces_uv.keys()):
        raise ValueError("Stage keys mismatch between EEG and ground truth traces.")
    if stage_names != list(stage_time_axes_seconds.keys()):
        raise ValueError("Stage keys mismatch between traces and time axes.")

    fig, axes = plt.subplots(
        len(stage_names),
        1,
        figsize=(12, 2.8 * len(stage_names)),
        constrained_layout=True,
        sharex=False,
    )
    axes = np.atleast_1d(axes)

    for axis, stage_name in zip(axes, stage_names):
        time_seconds = np.asarray(stage_time_axes_seconds[stage_name], dtype=float).ravel()
        eeg_trace_uv = np.asarray(stage_eeg_traces_uv[stage_name], dtype=float).ravel()
        gt_trace_uv = np.asarray(stage_ground_truth_traces_uv[stage_name], dtype=float).ravel()
        if time_seconds.size != eeg_trace_uv.size or time_seconds.size != gt_trace_uv.size:
            raise ValueError(f"Time and trace length mismatch in stage '{stage_name}'.")

        zoom_mask = (time_seconds >= zoom_window_s[0]) & (time_seconds <= zoom_window_s[1])
        if not np.any(zoom_mask):
            raise ValueError(f"Zoom window does not overlap stage '{stage_name}'.")

        zoom_time = time_seconds[zoom_mask]
        eeg_zoom = eeg_trace_uv[zoom_mask]
        gt_zoom = gt_trace_uv[zoom_mask]

        eeg_std = float(np.std(eeg_zoom))
        gt_std = float(np.std(gt_zoom))
        eeg_z = (eeg_zoom - float(np.mean(eeg_zoom))) / (eeg_std if eeg_std > 0 else 1.0)
        gt_z = (gt_zoom - float(np.mean(gt_zoom))) / (gt_std if gt_std > 0 else 1.0)

        axis.plot(zoom_time, eeg_z, lw=1.1, color="steelblue", label=eeg_label)
        axis.plot(zoom_time, gt_z, lw=1.1, color="darkorange", label=ground_truth_label)
        axis.axvline(0.0, color="k", lw=0.8, ls="--")
        axis.set_title(stage_name, fontsize=10)
        axis.set_ylabel("z")
        axis.grid(alpha=0.25)
        axis.legend(loc="upper right")

    axes[-1].set_xlabel("Time (s)")
    fig.savefig(str(Path(output_path)), dpi=220, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# QC helpers migrated from preprocessing.py
# ---------------------------------------------------------------------------

def plot_timecourse_raw_hpf_ica(
    raw_eeg,
    raw_hpf,
    raw_ica,
    sampling_rate_hz: float,
    channel_name: str,
    channel_index: int,
    t0_seconds: float,
    t1_seconds: float,
    output_path: str | Path,
) -> None:
    """QC plot: continuous raw vs HPF vs ICA-clean for one channel."""
    n_times = int(raw_eeg.n_times)
    i0 = max(0, int(round(t0_seconds * sampling_rate_hz)))
    i1 = min(n_times, int(round(t1_seconds * sampling_rate_hz)))
    if i1 <= i0:
        raise ValueError(f"Invalid time window: {(t0_seconds, t1_seconds)} s")
    time_seconds = np.arange(i0, i1, dtype=float) / sampling_rate_hz
    fig, axis = plt.subplots(figsize=(12, 4), constrained_layout=True)
    axis.plot(time_seconds, raw_eeg.get_data()[channel_index, i0:i1] * 1e6, lw=0.8, alpha=0.8, label="Raw")
    axis.plot(time_seconds, raw_hpf.get_data()[channel_index, i0:i1] * 1e6, lw=1.0, label="HPF")
    axis.plot(time_seconds, raw_ica.get_data()[channel_index, i0:i1] * 1e6, lw=1.1, label="ICA-clean")
    axis.set_title(f"{channel_name}: raw vs HPF vs ICA ({t0_seconds:.0f}-{t1_seconds:.0f} s)")
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Amplitude (uV)")
    axis.grid(alpha=0.2)
    axis.legend(loc="upper right")
    fig.savefig(Path(output_path), dpi=220)
    plt.close(fig)


def plot_epoch_step_subplots(
    step_epoch_data: dict[str, np.ndarray],
    step_time_axes_seconds: dict[str, np.ndarray],
    channel_index: int,
    channel_name: str,
    output_path: str | Path,
) -> None:
    """Plot one subplot per processing step (independent x/y scaling)."""
    step_names = list(step_epoch_data.keys())
    if not step_names:
        raise ValueError("step_epoch_data is empty.")
    fig, axes = plt.subplots(len(step_names), 1, figsize=(12, 2.4 * len(step_names)), constrained_layout=True)
    axes = np.atleast_1d(axes)
    for axis, step_name in zip(axes, step_names):
        step_data = np.asarray(step_epoch_data[step_name], dtype=float)
        step_time = np.asarray(step_time_axes_seconds[step_name], dtype=float).ravel()
        if step_data.ndim != 3 or step_data.shape[-1] != step_time.size:
            raise ValueError(f"Invalid shape/time axis for step '{step_name}'.")
        step_trace_uv = step_data[:, channel_index, :].mean(axis=0) * 1e6
        axis.plot(step_time, step_trace_uv, lw=1.0, color="steelblue")
        axis.set_title(f"{step_name} ({channel_name})")
        axis.set_xlabel("Time (s)")
        axis.set_ylabel("uV")
        axis.grid(alpha=0.2)
    fig.savefig(Path(output_path), dpi=220)
    plt.close(fig)


def plot_exp04_split_segment_spectral_summary(
    epoch_times_s,
    cp6_epochs,
    roi_epochs,
    spectral_summary,
    output_directory,
):
    """Save QC, ERSP, and band-summary figures for the exp04 split-segment analysis."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    saved_paths: dict[str, Path] = {}

    epoch_times = np.asarray(epoch_times_s, dtype=float).ravel()
    cp6_data = np.asarray(cp6_epochs, dtype=float)
    roi_data = np.asarray(roi_epochs, dtype=float)
    if cp6_data.ndim != 2 or roi_data.ndim != 3:
        raise ValueError("Invalid epoch shapes for the exp04 timing QC plot.")
    if cp6_data.shape[-1] != epoch_times.size or roi_data.shape[-1] != epoch_times.size:
        raise ValueError("Epoch time axis length does not match CP6/ROI data.")

    qc_path = output_directory / "exp04_stim_timing_qc.png"
    fig_qc, axes_qc = plt.subplots(2, 1, figsize=(10.5, 6.2), sharex=True, constrained_layout=True)
    axes_qc[0].plot(epoch_times, cp6_data.mean(axis=0) * 1e6, color="black", lw=1.1)
    axes_qc[0].axvline(-1.0, color="darkorange", lw=1.0, ls="--")
    axes_qc[0].axvline(0.08, color="crimson", lw=1.0, ls="--")
    axes_qc[0].set_title("CP6 trial mean with split boundaries")
    axes_qc[0].set_ylabel("Amplitude (uV)")
    axes_qc[0].grid(alpha=0.2)

    roi_mean_uv = roi_data.mean(axis=(0, 1)) * 1e6
    axes_qc[1].plot(epoch_times, roi_mean_uv, color="steelblue", lw=1.2)
    axes_qc[1].axvline(-1.0, color="darkorange", lw=1.0, ls="--", label="Stim onset")
    axes_qc[1].axvline(0.08, color="crimson", lw=1.0, ls="--", label="Excluded post edge")
    axes_qc[1].set_title("ROI trial mean with excluded stimulation interval")
    axes_qc[1].set_xlabel("Time from pulse (s)")
    axes_qc[1].set_ylabel("Amplitude (uV)")
    axes_qc[1].grid(alpha=0.2)
    axes_qc[1].legend(loc="upper right")
    fig_qc.savefig(qc_path, dpi=220)
    plt.close(fig_qc)
    saved_paths["timing_qc"] = qc_path

    post_times = np.asarray(spectral_summary["post_times_s"], dtype=float)
    valid_post_mask = np.asarray(spectral_summary["valid_post_time_mask"], dtype=bool)
    frequencies_hz = np.asarray(spectral_summary["frequencies_hz"], dtype=float)
    post_power_logratio = np.asarray(spectral_summary["post_power_logratio"], dtype=float)
    mean_post_logratio = post_power_logratio.mean(axis=(0, 1))
    if valid_post_mask.ndim == 1:
        display_time_mask = valid_post_mask
        display_map = mean_post_logratio[:, display_time_mask]
        if display_map.shape[-1] != int(display_time_mask.sum()):
            raise RuntimeError("Post ERSP display map and time mask disagree.")
    elif valid_post_mask.ndim == 2:
        if valid_post_mask.shape != mean_post_logratio.shape:
            raise RuntimeError("Frequency-aware post mask shape does not match the ERSP map.")
        display_time_mask = valid_post_mask.any(axis=0)
        display_map = np.ma.masked_where(~valid_post_mask[:, display_time_mask], mean_post_logratio[:, display_time_mask])
    else:
        raise ValueError("valid_post_time_mask must be 1D or 2D.")
    display_times = post_times[display_time_mask]

    ersp_path = output_directory / "exp04_post_ersp.png"
    fig_ersp, axis_ersp = plt.subplots(figsize=(10.5, 5.4), constrained_layout=True)
    image = axis_ersp.imshow(
        display_map,
        aspect="auto",
        origin="lower",
        extent=[float(display_times[0]), float(display_times[-1]), float(frequencies_hz[0]), float(frequencies_hz[-1])],
        cmap="RdBu_r",
    )
    axis_ersp.set_title("Post ERSP (log-ratio vs pre-off baseline)")
    axis_ersp.set_xlabel("Time from pulse (s)")
    axis_ersp.set_ylabel("Frequency (Hz)")
    axis_ersp.grid(alpha=0.15)
    colorbar = fig_ersp.colorbar(image, ax=axis_ersp)
    colorbar.set_label("Power change (dB)")
    fig_ersp.savefig(ersp_path, dpi=220)
    plt.close(fig_ersp)
    saved_paths["post_ersp"] = ersp_path

    metric_rows = spectral_summary["band_window_metrics"]
    if not isinstance(metric_rows, list) or not metric_rows:
        raise ValueError("band_window_metrics must contain at least one metrics row.")
    band_names = list(spectral_summary["band_definitions_hz"].keys())
    window_names = list(spectral_summary["summary_windows_s"].keys())
    colors = {"early": "#4C78A8", "late": "#F58518"}
    fig_band, axis_band = plt.subplots(figsize=(8.8, 4.8), constrained_layout=True)
    x_positions = np.arange(len(band_names), dtype=float)
    bar_width = 0.34
    for window_index, window_name in enumerate(window_names):
        means = []
        for band_name in band_names:
            values = np.asarray(
                [
                    float(row["post_logratio_db"])
                    for row in metric_rows
                    if row["band"] == band_name and row["window"] == window_name
                ],
                dtype=float,
            )
            means.append(float(values.mean()))
            jitter = np.linspace(-0.05, 0.05, values.size) if values.size > 1 else np.array([0.0], dtype=float)
            axis_band.scatter(
                np.full(values.size, x_positions[len(means) - 1] + (window_index - 0.5) * bar_width) + jitter,
                values,
                s=9,
                color="black",
                alpha=0.18,
                linewidths=0,
            )
        axis_band.bar(
            x_positions + (window_index - 0.5) * bar_width,
            means,
            width=bar_width,
            color=colors.get(window_name, "gray"),
            alpha=0.85,
            label=window_name.capitalize(),
        )
    axis_band.axhline(0.0, color="black", lw=0.8)
    axis_band.set_xticks(x_positions)
    axis_band.set_xticklabels([band_name.replace("_", "\n") for band_name in band_names])
    axis_band.set_ylabel("Post change vs pre baseline (dB)")
    axis_band.set_title("Band-specific post-window summary")
    axis_band.grid(axis="y", alpha=0.2)
    axis_band.legend(loc="upper right")
    band_path = output_directory / "exp04_post_band_summary.png"
    fig_band.savefig(band_path, dpi=220)
    plt.close(fig_band)
    saved_paths["band_summary"] = band_path
    return saved_paths


def plot_exp04_pre_post_resting_summary(
    frequencies_hz,
    roi_mean_psd_by_condition,
    band_power_rows,
    summary_rows,
    wpli_rows,
    wpli_pair_rows,
    node_strength_rows,
    output_directory,
) -> dict[str, Path]:
    """Save PSD, band-power, and wPLI summary figures for the exp04 resting analysis."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    saved_paths: dict[str, Path] = {}

    summary_lookup = {}
    for row in summary_rows:
        summary_lookup[(str(row["condition"]), str(row["metric_family"]), str(row["metric_name"]), str(row["roi_or_network"]))] = float(row["mean"])

    # PSD figure
    visible_mask = (frequencies >= 2.0) & (frequencies <= 45.0)
    if not np.any(visible_mask):
        raise ValueError("PSD frequencies do not overlap the visible plotting range.")

    visible_frequencies = frequencies[visible_mask]
    visible_db_values = []
    fig_psd, axes_psd = plt.subplots(1, 2, figsize=(11.0, 4.4), constrained_layout=True, sharey=True)
    for axis, roi_name, title in zip(axes_psd, ("left_motor", "right_motor"), ("Left Motor ROI PSD", "Right Motor ROI PSD"), strict=True):
        pre_psd = np.asarray(roi_mean_psd_by_condition["Pre"][roi_name], dtype=float)
        post_psd = np.asarray(roi_mean_psd_by_condition["Post"][roi_name], dtype=float)
        pre_psd_db = 10.0 * np.log10(pre_psd + 1e-30)
        post_psd_db = 10.0 * np.log10(post_psd + 1e-30)
        visible_db_values.extend([pre_psd_db[visible_mask], post_psd_db[visible_mask]])
        axis.plot(visible_frequencies, pre_psd_db[visible_mask], color="gray", lw=2.0, label="Pre")
        axis.plot(visible_frequencies, post_psd_db[visible_mask], color="steelblue", lw=2.0, label="Post")
        axis.axvspan(8.0, 12.0, color="#f9e7cc", alpha=0.55)
        axis.axvspan(13.0, 30.0, color="#ddebf7", alpha=0.45)
        axis.axvspan(30.0, 40.0, color="#f7d9d9", alpha=0.35)
        axis.set_title(title)
        axis.set_xlabel("Frequency (Hz)")
        axis.set_xlim(2.0, 45.0)
        axis.grid(alpha=0.2)
        axis.legend(loc="upper right")

    all_visible_db = np.concatenate(visible_db_values)
    visible_min_db = float(np.min(all_visible_db))
    visible_max_db = float(np.max(all_visible_db))
    y_pad = max(0.8, 0.08 * (visible_max_db - visible_min_db))
    for axis in axes_psd:
        axis.set_ylim(visible_min_db - y_pad, visible_max_db + y_pad)
    axes_psd[0].set_ylabel("Power (dB)")
    psd_path = output_directory / "exp04_pre_post_psd.png"
    fig_psd.savefig(psd_path, dpi=220)
    plt.close(fig_psd)
    saved_paths["psd"] = psd_path

    # Power figure
    power_categories = [
        ("left_motor", "alpha_absolute", "L alpha abs"),
        ("left_motor", "beta_absolute", "L beta abs"),
        ("left_motor", "low_gamma_absolute", "L gamma abs"),
        ("right_motor", "alpha_absolute", "R alpha abs"),
        ("right_motor", "beta_absolute", "R beta abs"),
        ("right_motor", "low_gamma_absolute", "R gamma abs"),
        ("left_motor", "alpha_relative", "L alpha rel"),
        ("left_motor", "beta_relative", "L beta rel"),
        ("left_motor", "low_gamma_relative", "L gamma rel"),
        ("right_motor", "alpha_relative", "R alpha rel"),
        ("right_motor", "beta_relative", "R beta rel"),
        ("right_motor", "low_gamma_relative", "R gamma rel"),
    ]
    x_power = np.arange(len(power_categories), dtype=float)
    pre_power_values = [
        summary_lookup[("Pre", "power", metric_name, roi_name)] for roi_name, metric_name, _ in power_categories
    ]
    post_power_values = [
        summary_lookup[("Post", "power", metric_name, roi_name)] for roi_name, metric_name, _ in power_categories
    ]
    fig_power, axis_power = plt.subplots(figsize=(14.0, 4.8), constrained_layout=True)
    bar_width = 0.38
    axis_power.bar(x_power - bar_width / 2, pre_power_values, width=bar_width, color="gray", alpha=0.85, label="Pre")
    axis_power.bar(x_power + bar_width / 2, post_power_values, width=bar_width, color="steelblue", alpha=0.85, label="Post")
    axis_power.set_xticks(x_power)
    axis_power.set_xticklabels([label for _, _, label in power_categories], rotation=35, ha="right")
    axis_power.set_ylabel("Power")
    axis_power.set_title("Band-power summary")
    axis_power.grid(axis="y", alpha=0.2)
    axis_power.legend(loc="upper right")
    power_path = output_directory / "exp04_pre_post_band_power_summary.png"
    fig_power.savefig(power_path, dpi=220)
    plt.close(fig_power)
    saved_paths["power"] = power_path

    # Power epoch distributions
    power_distribution_categories = [
        ("left_motor", "alpha_absolute", "L alpha abs"),
        ("left_motor", "beta_absolute", "L beta abs"),
        ("left_motor", "low_gamma_absolute", "L gamma abs"),
        ("right_motor", "alpha_absolute", "R alpha abs"),
        ("right_motor", "beta_absolute", "R beta abs"),
        ("right_motor", "low_gamma_absolute", "R gamma abs"),
    ]
    fig_power_dist, axis_power_dist = plt.subplots(figsize=(12.8, 5.0), constrained_layout=True)
    x_power_dist = np.arange(len(power_distribution_categories), dtype=float)
    rng_power = np.random.default_rng(2)
    for category_index, (roi_name, metric_name, label) in enumerate(power_distribution_categories):
        band_name = metric_name.replace("_absolute", "")
        pre_values = np.asarray(
            [
                float(row["value"])
                for row in band_power_rows
                if row["condition"] == "Pre" and row["roi"] == roi_name and row["band"] == band_name and row["power_type"] == "absolute"
            ],
            dtype=float,
        )
        post_values = np.asarray(
            [
                float(row["value"])
                for row in band_power_rows
                if row["condition"] == "Post" and row["roi"] == roi_name and row["band"] == band_name and row["power_type"] == "absolute"
            ],
            dtype=float,
        )
        axis_power_dist.scatter(
            np.full(pre_values.size, x_power_dist[category_index] - 0.16) + rng_power.uniform(-0.05, 0.05, size=pre_values.size),
            pre_values,
            s=14,
            color="gray",
            alpha=0.45,
            linewidths=0,
        )
        axis_power_dist.scatter(
            np.full(post_values.size, x_power_dist[category_index] + 0.16) + rng_power.uniform(-0.05, 0.05, size=post_values.size),
            post_values,
            s=14,
            color="steelblue",
            alpha=0.45,
            linewidths=0,
        )
        axis_power_dist.plot(
            [x_power_dist[category_index] - 0.22, x_power_dist[category_index] - 0.10],
            [np.median(pre_values), np.median(pre_values)],
            color="black",
            lw=2.0,
        )
        axis_power_dist.plot(
            [x_power_dist[category_index] + 0.10, x_power_dist[category_index] + 0.22],
            [np.median(post_values), np.median(post_values)],
            color="black",
            lw=2.0,
        )
    axis_power_dist.set_xticks(x_power_dist)
    axis_power_dist.set_xticklabels([label for _, _, label in power_distribution_categories], rotation=35, ha="right")
    axis_power_dist.set_ylabel("Absolute band power")
    axis_power_dist.set_title("Epoch-by-epoch band-power stability")
    axis_power_dist.grid(axis="y", alpha=0.2)
    power_distribution_path = output_directory / "exp04_pre_post_band_power_distributions.png"
    fig_power_dist.savefig(power_distribution_path, dpi=220)
    plt.close(fig_power_dist)
    saved_paths["power_distributions"] = power_distribution_path

    # wPLI figure
    pair_means = {}
    for row in wpli_pair_rows:
        pair_key = (
            str(row["condition"]),
            str(row["band"]),
            str(row["channel_a"]),
            str(row["channel_b"]),
        )
        pair_means.setdefault(pair_key, []).append(float(row["value"]))

    montage = mne.channels.make_standard_montage("standard_1020")
    montage_positions = montage.get_positions()["ch_pos"]
    channel_names = sorted(
        {
            str(row["channel_a"])
            for row in wpli_pair_rows
        }
        | {
            str(row["channel_b"])
            for row in wpli_pair_rows
        }
    )
    xy_positions = {
        channel_name: np.asarray(montage_positions[channel_name][:2], dtype=float)
        for channel_name in channel_names
    }
    max_radius = max(np.linalg.norm(position) for position in xy_positions.values())
    scalp_positions = {
        channel_name: xy_positions[channel_name] / max_radius * 0.82
        for channel_name in channel_names
    }

    def draw_scalp_connectivity(axis, band_name, condition_name, is_delta=False):
        axis.set_aspect("equal")
        axis.axis("off")
        head = plt.Circle((0.0, 0.0), 1.0, facecolor="white", edgecolor="black", lw=1.1)
        axis.add_patch(head)
        axis.plot([-0.08, 0.0, 0.08], [0.99, 1.12, 0.99], color="black", lw=1.0)
        axis.plot([-1.02, -1.08, -1.08, -1.02], [0.18, 0.16, -0.16, -0.18], color="black", lw=1.0)
        axis.plot([1.02, 1.08, 1.08, 1.02], [0.18, 0.16, -0.16, -0.18], color="black", lw=1.0)

        pair_values = []
        ordered_pairs = []
        for pair_key, values in pair_means.items():
            pair_condition, pair_band, channel_a, channel_b = pair_key
            if pair_band != band_name:
                continue
            if is_delta:
                pre_values = pair_means.get(("Pre", band_name, channel_a, channel_b))
                post_values = pair_means.get(("Post", band_name, channel_a, channel_b))
                if pre_values is None or post_values is None:
                    continue
                pair_value = float(np.mean(post_values) - np.mean(pre_values))
            else:
                if pair_condition != condition_name:
                    continue
                pair_value = float(np.mean(values))
            ordered_pairs.append((channel_a, channel_b))
            pair_values.append(pair_value)

        if not pair_values:
            raise ValueError(f"No pairwise wPLI values available for {band_name} {condition_name}.")

        pair_values_array = np.asarray(pair_values, dtype=float)
        if is_delta:
            color_limit = max(np.max(np.abs(pair_values_array)), 1e-6)
            color_norm = matplotlib.colors.TwoSlopeNorm(vmin=-color_limit, vcenter=0.0, vmax=color_limit)
            color_map = plt.cm.RdBu_r
        else:
            band_pre_values = [
                float(np.mean(values))
                for pair_key, values in pair_means.items()
                if pair_key[0] == "Pre" and pair_key[1] == band_name
            ]
            band_post_values = [
                float(np.mean(values))
                for pair_key, values in pair_means.items()
                if pair_key[0] == "Post" and pair_key[1] == band_name
            ]
            color_limit = max(band_pre_values + band_post_values)
            color_norm = matplotlib.colors.Normalize(vmin=0.0, vmax=color_limit)
            color_map = plt.cm.viridis

        for (channel_a, channel_b), pair_value in zip(ordered_pairs, pair_values, strict=True):
            position_a = scalp_positions[channel_a]
            position_b = scalp_positions[channel_b]
            line_strength = abs(pair_value) / color_limit if is_delta else pair_value / color_limit
            axis.plot(
                [position_a[0], position_b[0]],
                [position_a[1], position_b[1]],
                color=color_map(color_norm(pair_value)),
                lw=1.5 + 3.5 * line_strength,
                alpha=0.95,
                solid_capstyle="round",
                zorder=2,
            )

        for channel_name, position in scalp_positions.items():
            axis.scatter(position[0], position[1], s=18, color="black", zorder=3)
            axis.text(position[0], position[1] + 0.07, channel_name, ha="center", va="bottom", fontsize=8)

        title_suffix = "Delta" if is_delta else condition_name
        axis.set_title(f"{band_name.replace('_', ' ').title()} {title_suffix}", pad=12)
        return plt.cm.ScalarMappable(norm=color_norm, cmap=color_map)

    wpli_band_order = ["theta", "alpha", "beta", "low_gamma"]
    fig_wpli, axes_wpli = plt.subplots(len(wpli_band_order), 3, figsize=(11.8, 13.2), constrained_layout=True)
    for row_index, band_name in enumerate(wpli_band_order):
        pre_scalar = draw_scalp_connectivity(axes_wpli[row_index, 0], band_name, "Pre")
        draw_scalp_connectivity(axes_wpli[row_index, 1], band_name, "Post")
        delta_scalar = draw_scalp_connectivity(axes_wpli[row_index, 2], band_name, "Delta", is_delta=True)
        fig_wpli.colorbar(pre_scalar, ax=axes_wpli[row_index, :2], shrink=0.84, location="right", label="wPLI")
        fig_wpli.colorbar(delta_scalar, ax=axes_wpli[row_index, 2], shrink=0.84, location="right", label="Post - Pre")
    wpli_path = output_directory / "exp04_pre_post_wpli_summary.png"
    fig_wpli.savefig(wpli_path, dpi=220)
    plt.close(fig_wpli)
    saved_paths["wpli"] = wpli_path

    # wPLI family distributions
    wpli_family_order = ["within_left", "within_right", "interhemispheric", "anterior_posterior"]
    wpli_band_order = ["theta", "alpha", "beta", "low_gamma"]
    fig_wpli_dist, axes_wpli_dist = plt.subplots(len(wpli_band_order), 1, figsize=(11.5, 12.5), constrained_layout=True, sharex=True)
    rng_wpli = np.random.default_rng(3)
    for axis_wpli_dist, band_name in zip(axes_wpli_dist, wpli_band_order, strict=True):
        x_family = np.arange(len(wpli_family_order), dtype=float)
        for family_index, family_name in enumerate(wpli_family_order):
            pre_values = np.asarray(
                [
                    float(row["value"])
                    for row in wpli_rows
                    if row["condition"] == "Pre" and row["band"] == band_name and row["summary_type"] == family_name
                ],
                dtype=float,
            )
            post_values = np.asarray(
                [
                    float(row["value"])
                    for row in wpli_rows
                    if row["condition"] == "Post" and row["band"] == band_name and row["summary_type"] == family_name
                ],
                dtype=float,
            )
            axis_wpli_dist.scatter(
                np.full(pre_values.size, x_family[family_index] - 0.16) + rng_wpli.uniform(-0.05, 0.05, size=pre_values.size),
                pre_values,
                s=12,
                color="gray",
                alpha=0.45,
                linewidths=0,
            )
            axis_wpli_dist.scatter(
                np.full(post_values.size, x_family[family_index] + 0.16) + rng_wpli.uniform(-0.05, 0.05, size=post_values.size),
                post_values,
                s=12,
                color="steelblue",
                alpha=0.45,
                linewidths=0,
            )
            axis_wpli_dist.plot(
                [x_family[family_index] - 0.22, x_family[family_index] - 0.10],
                [np.median(pre_values), np.median(pre_values)],
                color="black",
                lw=2.0,
            )
            axis_wpli_dist.plot(
                [x_family[family_index] + 0.10, x_family[family_index] + 0.22],
                [np.median(post_values), np.median(post_values)],
                color="black",
                lw=2.0,
            )
        axis_wpli_dist.set_title(f"{band_name.replace('_', ' ').title()} wPLI families")
        axis_wpli_dist.set_ylabel("wPLI")
        axis_wpli_dist.grid(axis="y", alpha=0.2)
        axis_wpli_dist.set_xticks(x_family)
        axis_wpli_dist.set_xticklabels(["within left", "within right", "inter", "A-P"])
    wpli_distribution_path = output_directory / "exp04_pre_post_wpli_distributions.png"
    fig_wpli_dist.savefig(wpli_distribution_path, dpi=220)
    plt.close(fig_wpli_dist)
    saved_paths["wpli_distributions"] = wpli_distribution_path

    # Node strength figure
    node_strength_lookup = {}
    for row in node_strength_rows:
        node_key = (
            str(row["condition"]),
            str(row["band"]),
            str(row["channel"]),
        )
        node_strength_lookup.setdefault(node_key, []).append(float(row["value"]))

    def draw_node_strength(axis, band_name, condition_name, is_delta=False):
        axis.set_aspect("equal")
        axis.axis("off")
        head = plt.Circle((0.0, 0.0), 1.0, facecolor="white", edgecolor="black", lw=1.1)
        axis.add_patch(head)
        axis.plot([-0.08, 0.0, 0.08], [0.99, 1.12, 0.99], color="black", lw=1.0)
        axis.plot([-1.02, -1.08, -1.08, -1.02], [0.18, 0.16, -0.16, -0.18], color="black", lw=1.0)
        axis.plot([1.02, 1.08, 1.08, 1.02], [0.18, 0.16, -0.16, -0.18], color="black", lw=1.0)

        node_names = list(scalp_positions.keys())
        node_values = []
        for channel_name in node_names:
            if is_delta:
                pre_values = node_strength_lookup[("Pre", band_name, channel_name)]
                post_values = node_strength_lookup[("Post", band_name, channel_name)]
                node_values.append(float(np.mean(post_values) - np.mean(pre_values)))
            else:
                node_values.append(float(np.mean(node_strength_lookup[(condition_name, band_name, channel_name)])))

        node_values_array = np.asarray(node_values, dtype=float)
        if is_delta:
            color_limit = max(np.max(np.abs(node_values_array)), 1e-6)
            color_norm = matplotlib.colors.TwoSlopeNorm(vmin=-color_limit, vcenter=0.0, vmax=color_limit)
            color_map = plt.cm.RdBu_r
            size_strength = np.abs(node_values_array) / color_limit
        else:
            color_limit = max(np.max(node_values_array), 1e-6)
            color_norm = matplotlib.colors.Normalize(vmin=0.0, vmax=color_limit)
            color_map = plt.cm.viridis
            size_strength = node_values_array / color_limit

        for channel_name, node_value, node_scale in zip(node_names, node_values, size_strength, strict=True):
            position = scalp_positions[channel_name]
            axis.scatter(
                position[0],
                position[1],
                s=60.0 + 260.0 * float(node_scale),
                color=color_map(color_norm(node_value)),
                edgecolor="black",
                linewidths=0.8,
                zorder=3,
            )
            axis.text(position[0], position[1] + 0.08, channel_name, ha="center", va="bottom", fontsize=8)

        title_suffix = "Delta" if is_delta else condition_name
        axis.set_title(f"{band_name.replace('_', ' ').title()} {title_suffix}", pad=12)
        return plt.cm.ScalarMappable(norm=color_norm, cmap=color_map)

    fig_strength, axes_strength = plt.subplots(len(wpli_band_order), 3, figsize=(11.8, 13.2), constrained_layout=True)
    for row_index, band_name in enumerate(wpli_band_order):
        pre_strength_scalar = draw_node_strength(axes_strength[row_index, 0], band_name, "Pre")
        draw_node_strength(axes_strength[row_index, 1], band_name, "Post")
        delta_strength_scalar = draw_node_strength(axes_strength[row_index, 2], band_name, "Delta", is_delta=True)
        fig_strength.colorbar(pre_strength_scalar, ax=axes_strength[row_index, :2], shrink=0.84, location="right", label="Node strength")
        fig_strength.colorbar(delta_strength_scalar, ax=axes_strength[row_index, 2], shrink=0.84, location="right", label="Post - Pre")
    node_strength_path = output_directory / "exp04_pre_post_node_strength.png"
    fig_strength.savefig(node_strength_path, dpi=220)
    plt.close(fig_strength)
    saved_paths["node_strength"] = node_strength_path
    return saved_paths
