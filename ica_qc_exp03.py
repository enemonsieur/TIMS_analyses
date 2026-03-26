from __future__ import annotations

from pathlib import Path
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np


# ---- config ----
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_pulse_centered_analysis_run03")

raw_epochs_path = output_directory / "stim_epochs_raw-epo.fif"
cleaned_epochs_path = output_directory / "stim_epochs_presync_cut_demean_maincut-epo.fif"

# Optional diagnostics-only component list; never written back to pipeline files.
candidate_exclude_components: list[int] = []

n_components = 0.99
ica_method = "fastica"
ica_random_state = 42

presync_cut_window_s = (-0.985, -0.968)
main_cut_window_s = (-0.002, 0.025)
baseline_window_s = (-0.70, -0.10)


def _require_file(path: Path, producer: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}\n"
            f"Run {producer} first."
        )


def _mask(times: np.ndarray, window_s: tuple[float, float], name: str) -> np.ndarray:
    mask = (times >= window_s[0]) & (times <= window_s[1])
    if not np.any(mask):
        raise RuntimeError(f"{name} does not overlap epoch time axis: {window_s}")
    return mask


def _save_mne_figure(fig_or_list: object, outpath: Path) -> None:
    if isinstance(fig_or_list, list):
        figures = fig_or_list
    else:
        figures = [fig_or_list]
    if not figures:
        raise RuntimeError("No figure returned by MNE plotting function.")
    figures[0].savefig(outpath, dpi=200, bbox_inches="tight")
    for fig in figures:
        plt.close(fig)


def main() -> int:
    output_directory.mkdir(parents=True, exist_ok=True)
    _require_file(raw_epochs_path, "main_analysis_exp03.py")
    _require_file(cleaned_epochs_path, "main_analysis_exp03.py")

    raw_epochs = mne.read_epochs(str(raw_epochs_path), preload=True, verbose=False)
    cleaned_epochs = mne.read_epochs(str(cleaned_epochs_path), preload=True, verbose=False)

    if raw_epochs.ch_names != cleaned_epochs.ch_names:
        raise RuntimeError("Raw and cleaned epochs channel order mismatch.")
    if raw_epochs.get_data().shape[-1] != cleaned_epochs.get_data().shape[-1]:
        raise RuntimeError("Raw and cleaned epochs sample-length mismatch.")

    ica = mne.preprocessing.ICA(
        n_components=n_components, random_state=ica_random_state,
        method=ica_method, max_iter="auto",
    )
    ica.fit(cleaned_epochs, verbose=False)

    source_epochs = ica.get_sources(cleaned_epochs)
    source_data = source_epochs.get_data()  # (n_epochs, n_components, n_times)
    times = source_epochs.times
    if source_data.ndim != 3:
        raise RuntimeError("Unexpected ICA source data shape.")

    baseline_mask = _mask(times, baseline_window_s, "baseline_window_s")
    presync_mask = _mask(times, presync_cut_window_s, "presync_cut_window_s")
    main_mask = _mask(times, main_cut_window_s, "main_cut_window_s")

    component_var = np.var(source_data, axis=(0, 2))
    var_total = float(np.sum(component_var) + 1e-30)
    eps = 1e-30

    metrics_rows: list[dict[str, float | int]] = []
    for component_idx in range(source_data.shape[1]):
        component = source_data[:, component_idx, :]
        baseline_rms = float(np.sqrt(np.mean(component[:, baseline_mask] ** 2)))
        presync_peak_abs = float(np.max(np.abs(component[:, presync_mask].mean(axis=0))))
        main_peak_abs = float(np.max(np.abs(component[:, main_mask].mean(axis=0))))
        suspicious_score = float(max(presync_peak_abs, main_peak_abs) / (baseline_rms + eps))
        metrics_rows.append(
            {
                "component": int(component_idx),
                "variance_proxy": float(component_var[component_idx]),
                "variance_fraction_proxy": float(component_var[component_idx] / var_total),
                "baseline_rms": baseline_rms,
                "presync_peak_abs": presync_peak_abs,
                "main_peak_abs": main_peak_abs,
                "suspicious_score": suspicious_score,
            }
        )

    metrics_rows_sorted = sorted(metrics_rows, key=lambda row: float(row["suspicious_score"]), reverse=True)

    # ---- Figure 1: ICA component topomaps ----
    components_fig = ica.plot_components(show=False)
    components_path = output_directory / "ica_qc_components.png"
    _save_mne_figure(components_fig, components_path)

    # ---- Figure 2: source time courses for top suspicious components ----
    top_count = min(6, source_data.shape[1])
    top_components = [int(row["component"]) for row in metrics_rows_sorted[:top_count]]
    fig_src, axes = plt.subplots(
        top_count,
        1,
        figsize=(12, 2.2 * top_count),
        sharex=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    for axis, component_idx in zip(axes, top_components):
        waveform = source_data[:, component_idx, :].mean(axis=0)
        score = float(next(row["suspicious_score"] for row in metrics_rows_sorted if int(row["component"]) == component_idx))
        axis.plot(times, waveform, lw=1.0, color="slateblue")
        axis.axvspan(presync_cut_window_s[0], presync_cut_window_s[1], color="tomato", alpha=0.12)
        axis.axvspan(main_cut_window_s[0], main_cut_window_s[1], color="goldenrod", alpha=0.12)
        axis.axvspan(baseline_window_s[0], baseline_window_s[1], color="seagreen", alpha=0.08)
        axis.axvline(0.0, color="k", ls="--", lw=0.8)
        axis.set_ylabel(f"IC {component_idx}")
        axis.set_title(f"IC {component_idx} mean source | suspicious_score={score:.2f}", fontsize=10)
        axis.grid(alpha=0.2)
    axes[-1].set_xlabel("Time from pulse (s)")
    fig_src.suptitle("ICA QC source time-courses (top suspicious components)", fontsize=12, fontweight="bold")
    sources_path = output_directory / "ica_qc_sources.png"
    fig_src.savefig(sources_path, dpi=200)
    plt.close(fig_src)

    # ---- Figure 3: reference overlay raw vs cleaned vs ICA-cleaned ----
    ref_ch = "Fp1" if "Fp1" in cleaned_epochs.ch_names else cleaned_epochs.ch_names[0]
    ref_idx = cleaned_epochs.ch_names.index(ref_ch)

    raw_mean_uv = raw_epochs.get_data()[:, ref_idx, :].mean(axis=0) * 1e6
    clean_mean_uv = cleaned_epochs.get_data()[:, ref_idx, :].mean(axis=0) * 1e6

    valid_exclude = sorted(
        set(
            int(idx)
            for idx in candidate_exclude_components
            if 0 <= int(idx) < source_data.shape[1]
        )
    )
    ica_overlay = ica.copy()
    ica_overlay.exclude = valid_exclude
    overlay_epochs = ica_overlay.apply(cleaned_epochs.copy(), verbose=False)
    ica_mean_uv = overlay_epochs.get_data()[:, ref_idx, :].mean(axis=0) * 1e6

    fig_overlay, ax_overlay = plt.subplots(figsize=(12, 4), constrained_layout=True)
    ax_overlay.plot(times, raw_mean_uv, lw=0.9, alpha=0.8, label="Raw mean")
    ax_overlay.plot(times, clean_mean_uv, lw=1.0, label="Clean mean")
    label = f"ICA-clean mean (exclude={valid_exclude})" if valid_exclude else "ICA-clean mean (exclude=[])"
    ax_overlay.plot(times, ica_mean_uv, lw=1.1, label=label)
    ax_overlay.axvspan(presync_cut_window_s[0], presync_cut_window_s[1], color="tomato", alpha=0.12, label="Pre-sync cut")
    ax_overlay.axvspan(main_cut_window_s[0], main_cut_window_s[1], color="goldenrod", alpha=0.12, label="Main cut")
    ax_overlay.axvline(0.0, color="k", ls="--", lw=0.8)
    ax_overlay.set_title(f"ICA QC overlay ({ref_ch})")
    ax_overlay.set_xlabel("Time from pulse (s)")
    ax_overlay.set_ylabel("Amplitude (uV)")
    ax_overlay.grid(alpha=0.2)
    ax_overlay.legend(loc="upper right", ncol=2, fontsize=8)
    overlay_path = output_directory / "ica_qc_overlay_reference.png"
    fig_overlay.savefig(overlay_path, dpi=200)
    plt.close(fig_overlay)

    # ---- Metrics CSV ----
    metrics_csv_path = output_directory / "ica_qc_component_metrics.csv"
    with metrics_csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "component",
            "variance_proxy",
            "variance_fraction_proxy",
            "baseline_rms",
            "presync_peak_abs",
            "main_peak_abs",
            "suspicious_score",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in metrics_rows_sorted:
            writer.writerow(row)

    # ---- Summary TXT ----
    summary_lines = [
        "Exp03 ICA diagnostics (non-destructive)",
        f"raw_epochs_path={raw_epochs_path}",
        f"cleaned_epochs_path={cleaned_epochs_path}",
        f"n_epochs={cleaned_epochs.get_data().shape[0]}",
        f"n_channels={cleaned_epochs.get_data().shape[1]}",
        f"n_samples={cleaned_epochs.get_data().shape[2]}",
        f"ica_n_components_setting={n_components}",
        f"ica_method={ica_method}",
        f"ica_random_state={ica_random_state}",
        f"candidate_exclude_components={candidate_exclude_components}",
        f"valid_exclude_components={valid_exclude}",
        f"reference_channel={ref_ch}",
        f"presync_cut_window_s={presync_cut_window_s}",
        f"main_cut_window_s={main_cut_window_s}",
        f"baseline_window_s={baseline_window_s}",
        "top_suspicious_components=",
    ]
    for row in metrics_rows_sorted[:10]:
        summary_lines.append(
            "  IC{component}: score={suspicious_score:.3f}, "
            "main_peak_abs={main_peak_abs:.6f}, "
            "presync_peak_abs={presync_peak_abs:.6f}, "
            "baseline_rms={baseline_rms:.6f}".format(**row)
        )
    summary_lines.extend(
        [
            f"saved_components_plot={components_path}",
            f"saved_sources_plot={sources_path}",
            f"saved_overlay_plot={overlay_path}",
            f"saved_metrics_csv={metrics_csv_path}",
            "note=No epoch FIF files were modified by this script.",
        ]
    )
    summary_path = output_directory / "ica_qc_summary.txt"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Saved {components_path}")
    print(f"Saved {sources_path}")
    print(f"Saved {overlay_path}")
    print(f"Saved {metrics_csv_path}")
    print(f"Saved {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
