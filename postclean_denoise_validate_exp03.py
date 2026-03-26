from __future__ import annotations

from pathlib import Path
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

from preprocessing import (
    compute_coherence_band,
    detect_stim_onsets,
)


# ---- config ----
stim_vhdr_path = Path(
    r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
)
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_pulse_centered_analysis_run03")
cleaned_epochs_path = output_directory / "stim_epochs_presync_cut_demean_maincut-epo.fif"

epoch_window_s = (-2.0, 1.0)
baseline_window_s = (-0.70, -0.10)
validation_window_s = (0.03, 1.00)
presync_cut_window_s = (-0.985, -0.968)
main_cut_window_s = (-0.002, 0.025)
metric_band_hz = (8.0, 12.0)

# Optional HPF after cut+demean and before denoising; set None to disable.
high_pass_hz: float | None = 1.0

# Denoiser defaults.
ica_n_components: float | int = 0.99
ica_random_state = 42
ica_method = "fastica"
ica_auto_exclude_top_n = 2
ssp_n_eeg = 2


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


def _bandpass_1d(signal_1d: np.ndarray, sfreq: float, low_hz: float, high_hz: float, order: int = 4) -> np.ndarray:
    sos = butter(order, [low_hz, high_hz], btype="bandpass", fs=sfreq, output="sos")
    return sosfiltfilt(sos, np.asarray(signal_1d, dtype=float).ravel())


def _zscore_safe(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float).ravel()
    std = float(np.std(x))
    if std <= 0:
        return np.zeros_like(x)
    return (x - float(np.mean(x))) / std


def _validate_against_ground_truth(
    method_name: str,
    epochs_data: np.ndarray,
    gt_epochs: np.ndarray,
    times: np.ndarray,
    sfreq: float,
    reference_index: int,
    notes: str = "",
) -> dict[str, float | str | int]:
    ref_epochs = epochs_data[:, reference_index, :]

    baseline_mask = _mask(times, baseline_window_s, "baseline_window_s")
    validation_mask = _mask(times, validation_window_s, "validation_window_s")
    main_mask = _mask(times, main_cut_window_s, "main_cut_window_s")
    presync_mask = _mask(times, presync_cut_window_s, "presync_cut_window_s")

    ref_mean = ref_epochs.mean(axis=0)
    gt_mean = gt_epochs.mean(axis=0)
    ref_flat = ref_epochs[:, validation_mask].reshape(-1)
    gt_flat = gt_epochs[:, validation_mask].reshape(-1)

    coh_8_12 = compute_coherence_band(
        signal_a=ref_flat,
        signal_b=gt_flat,
        sampling_rate_hz=sfreq,
        low_hz=metric_band_hz[0],
        high_hz=metric_band_hz[1],
    )

    ref_bp = _bandpass_1d(ref_flat, sfreq, metric_band_hz[0], metric_band_hz[1])
    gt_bp = _bandpass_1d(gt_flat, sfreq, metric_band_hz[0], metric_band_hz[1])
    phase_diff = np.angle(hilbert(ref_bp)) - np.angle(hilbert(gt_bp))
    plv_8_12 = float(np.abs(np.mean(np.exp(1j * phase_diff))))

    ref_val = ref_mean[validation_mask]
    gt_val = gt_mean[validation_mask]
    if float(np.std(ref_val)) > 0 and float(np.std(gt_val)) > 0:
        corr_val = float(np.corrcoef(ref_val, gt_val)[0, 1])
    else:
        corr_val = float("nan")

    row: dict[str, float | str | int] = {
        "method": method_name,
        "status": "ok",
        "n_epochs": int(epochs_data.shape[0]),
        "n_channels": int(epochs_data.shape[1]),
        "coherence_8_12": float(coh_8_12),
        "plv_8_12": float(plv_8_12),
        "timecorr_validation_window": corr_val,
        "ref_baseline_rms_uv": float(np.sqrt(np.mean((ref_mean[baseline_mask] * 1e6) ** 2))),
        "ref_presync_peak_abs_uv": float(np.max(np.abs(ref_mean[presync_mask] * 1e6))),
        "ref_main_peak_abs_uv": float(np.max(np.abs(ref_mean[main_mask] * 1e6))),
        "notes": notes,
    }
    return row


def _run_sound_if_available(epochs: mne.Epochs) -> tuple[mne.Epochs | None, str]:
    try:
        import sound  # type: ignore  # noqa: F401
    except Exception as exc:
        return None, f"SOUND unavailable in environment: {exc}"
    return None, "SOUND package detected but no repo-integrated SOUND pipeline is implemented."


def main() -> int:
    output_directory.mkdir(parents=True, exist_ok=True)
    _require_file(stim_vhdr_path, "dataset import stage / verify stim_vhdr_path")
    _require_file(cleaned_epochs_path, "main_analysis_exp03.py")

    cleaned_epochs = mne.read_epochs(str(cleaned_epochs_path), preload=True, verbose=False)
    sfreq = float(cleaned_epochs.info["sfreq"])
    times = cleaned_epochs.times.copy()
    cleaned_data = cleaned_epochs.get_data()

    if cleaned_data.ndim != 3:
        raise RuntimeError("Unexpected cleaned epochs shape.")

    # Ground-truth epoching aligned by stim-marker onset detection.
    raw = mne.io.read_raw_brainvision(str(stim_vhdr_path), preload=True, verbose=False)
    stim_ch = next((ch for ch in raw.ch_names if "stim" in ch.lower()), None)
    gt_ch = next((ch for ch in raw.ch_names if "ground_truth" in ch.lower() or ch.lower() == "gt"), None)
    if stim_ch is None:
        raise RuntimeError("Stim marker channel not found in recording.")
    if gt_ch is None:
        raise RuntimeError("ground_truth channel not found in recording.")
    if float(raw.info["sfreq"]) != sfreq:
        raise RuntimeError("Sampling-rate mismatch between cleaned epochs and raw recording.")

    stim_marker = raw.copy().pick([stim_ch]).get_data()[0]
    ground_truth = raw.copy().pick([gt_ch]).get_data()[0]
    stim_onsets_samples, _, _, _ = detect_stim_onsets(stim_marker=stim_marker, sampling_rate_hz=sfreq)
    # Inline epoch extraction for ground-truth channel
    start_offset = int(round(epoch_window_s[0] * sfreq))
    end_offset = int(round(epoch_window_s[1] * sfreq))
    n_samples = end_offset - start_offset
    gt_epochs = np.array([ground_truth[int(o) + start_offset : int(o) + start_offset + n_samples]
                          for o in stim_onsets_samples
                          if int(o) + start_offset >= 0 and int(o) + start_offset + n_samples <= len(ground_truth)])
    gt_time = np.arange(n_samples) / sfreq + epoch_window_s[0]

    if gt_epochs.shape[0] != cleaned_data.shape[0]:
        raise RuntimeError(
            "Ground-truth epoch count does not match cleaned epoch count "
            f"({gt_epochs.shape[0]} vs {cleaned_data.shape[0]}). Re-run with matching onset settings."
        )
    if gt_epochs.shape[1] != cleaned_data.shape[2]:
        raise RuntimeError("Ground-truth sample-length does not match cleaned epochs.")
    if not np.allclose(gt_time, times):
        raise RuntimeError("Ground-truth epoch time axis does not match cleaned epochs.")

    reference_channel = "Fp1" if "Fp1" in cleaned_epochs.ch_names else ("Cz" if "Cz" in cleaned_epochs.ch_names else cleaned_epochs.ch_names[0])
    reference_index = cleaned_epochs.ch_names.index(reference_channel)

    # Optional HPF applied after cut+demean and before denoising branches.
    if high_pass_hz is not None:
        # IIR avoids FIR length > epoch length distortion warnings on short epochs.
        epochs_input = cleaned_epochs.copy().filter(
            l_freq=high_pass_hz,
            h_freq=None,
            method="iir",
            iir_params={"order": 4, "ftype": "butter"},
            verbose=False,
        )
        input_note = f"HPF (IIR Butterworth order 4) applied at {high_pass_hz:.3f} Hz before denoising."
    else:
        epochs_input = cleaned_epochs.copy()
        input_note = "No HPF applied."

    # Branch 0: clean-only baseline for comparison.
    branch_epochs: dict[str, mne.Epochs] = {"clean_only": epochs_input.copy()}
    branch_notes: dict[str, str] = {"clean_only": input_note}

    # Branch 1: ICA (auto-exclude top artifact-related components).
    ica_model = mne.preprocessing.ICA(
        n_components=ica_n_components, random_state=ica_random_state,
        method=ica_method, max_iter="auto",
    )
    ica_model.fit(epochs_input, verbose=False)
    src = ica_model.get_sources(epochs_input).get_data()
    baseline_mask = _mask(times, baseline_window_s, "baseline_window_s")
    presync_mask = _mask(times, presync_cut_window_s, "presync_cut_window_s")
    main_mask = _mask(times, main_cut_window_s, "main_cut_window_s")
    scores: list[tuple[int, float]] = []
    for comp in range(src.shape[1]):
        comp_epochs = src[:, comp, :]
        base_rms = float(np.sqrt(np.mean(comp_epochs[:, baseline_mask] ** 2)))
        peak = float(max(np.max(np.abs(comp_epochs[:, presync_mask].mean(axis=0))), np.max(np.abs(comp_epochs[:, main_mask].mean(axis=0)))))
        score = float(peak / (base_rms + 1e-30))
        scores.append((comp, score))
    scores_sorted = sorted(scores, key=lambda item: item[1], reverse=True)
    ica_exclude = [comp for comp, _ in scores_sorted[: min(ica_auto_exclude_top_n, len(scores_sorted))]]
    ica_model.exclude = list(ica_exclude)
    branch_epochs["ica_auto"] = ica_model.apply(epochs_input.copy(), verbose=False)
    branch_notes["ica_auto"] = (
        f"{input_note} ICA auto-excluded components={ica_exclude} "
        f"(top {ica_auto_exclude_top_n} by pulse/baseline source score)."
    )

    # Branch 2: SSP from pulse window.
    pulse_epochs = epochs_input.copy().crop(tmin=0.0, tmax=0.03)
    ssp_projs = mne.compute_proj_epochs(
        pulse_epochs,
        n_grad=0,
        n_mag=0,
        n_eeg=ssp_n_eeg,
        verbose=False,
    )
    ssp_epochs = epochs_input.copy()
    ssp_epochs.add_proj(ssp_projs)
    ssp_epochs.apply_proj(verbose=False)
    branch_epochs["ssp"] = ssp_epochs
    branch_notes["ssp"] = f"{input_note} SSP projectors applied: n_eeg={len(ssp_projs)}"

    # Branch 3: SOUND (if available).
    sound_epochs, sound_note = _run_sound_if_available(epochs_input)
    if sound_epochs is not None:
        branch_epochs["sound"] = sound_epochs
        branch_notes["sound"] = f"{input_note} {sound_note}"

    metric_rows: list[dict[str, float | str | int]] = []
    for method_name, epochs_method in branch_epochs.items():
        row = _validate_against_ground_truth(
            method_name=method_name,
            epochs_data=epochs_method.get_data(),
            gt_epochs=gt_epochs,
            times=times,
            sfreq=sfreq,
            reference_index=reference_index,
            notes=branch_notes.get(method_name, ""),
        )
        metric_rows.append(row)

    if sound_epochs is None:
        metric_rows.append(
            {
                "method": "sound",
                "status": "skipped",
                "n_epochs": int(cleaned_data.shape[0]),
                "n_channels": int(cleaned_data.shape[1]),
                "coherence_8_12": float("nan"),
                "plv_8_12": float("nan"),
                "timecorr_validation_window": float("nan"),
                "ref_baseline_rms_uv": float("nan"),
                "ref_presync_peak_abs_uv": float("nan"),
                "ref_main_peak_abs_uv": float("nan"),
                "notes": sound_note,
            }
        )

    # ---- save metrics csv ----
    metrics_csv = output_directory / "postclean_validation_metrics.csv"
    with metrics_csv.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "method",
            "status",
            "n_epochs",
            "n_channels",
            "coherence_8_12",
            "plv_8_12",
            "timecorr_validation_window",
            "ref_baseline_rms_uv",
            "ref_presync_peak_abs_uv",
            "ref_main_peak_abs_uv",
            "notes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in metric_rows:
            writer.writerow(row)

    # ---- time-domain sanity figure ----
    gt_mean = gt_epochs.mean(axis=0)
    fig_tc, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, constrained_layout=True)
    colors = {
        "clean_only": "steelblue",
        "ica_auto": "darkorange",
        "ssp": "seagreen",
        "sound": "purple",
    }
    for method_name, epochs_method in branch_epochs.items():
        method_mean_uv = epochs_method.get_data()[:, reference_index, :].mean(axis=0) * 1e6
        color = colors.get(method_name, None)
        ax1.plot(times, method_mean_uv, lw=1.0, color=color, label=method_name)
        ax2.plot(times, _zscore_safe(method_mean_uv), lw=1.0, color=color, label=method_name)

    gt_scaled_uv = gt_mean * (float(np.std(branch_epochs["clean_only"].get_data()[:, reference_index, :].mean(axis=0))) / (float(np.std(gt_mean)) + 1e-30)) * 1e6
    ax1.plot(times, gt_scaled_uv, lw=1.1, color="black", ls="--", label="ground_truth (scaled)")
    ax2.plot(times, _zscore_safe(gt_mean), lw=1.1, color="black", ls="--", label="ground_truth (z)")

    for axis in (ax1, ax2):
        axis.axvspan(presync_cut_window_s[0], presync_cut_window_s[1], color="tomato", alpha=0.10)
        axis.axvspan(main_cut_window_s[0], main_cut_window_s[1], color="goldenrod", alpha=0.10)
        axis.axvspan(validation_window_s[0], validation_window_s[1], color="gray", alpha=0.06)
        axis.axvline(0.0, color="k", ls="--", lw=0.8)
        axis.grid(alpha=0.2)

    ax1.set_title(f"Post-clean denoising sanity ({reference_channel} vs ground_truth)")
    ax1.set_ylabel(f"{reference_channel} mean (uV)")
    ax1.legend(loc="upper right", ncol=2, fontsize=8)
    ax2.set_ylabel("Z-scored mean")
    ax2.set_xlabel("Time from pulse (s)")
    tc_path = output_directory / "postclean_validation_timecourse.png"
    fig_tc.savefig(tc_path, dpi=220)
    plt.close(fig_tc)

    # ---- coherence/PLV bar figure ----
    ok_rows = [row for row in metric_rows if row["status"] == "ok"]
    labels = [str(row["method"]) for row in ok_rows]
    coh_vals = [float(row["coherence_8_12"]) for row in ok_rows]
    plv_vals = [float(row["plv_8_12"]) for row in ok_rows]

    fig_bar, (axc, axp) = plt.subplots(2, 1, figsize=(9, 7), constrained_layout=True)
    x = np.arange(len(labels))
    axc.bar(x, coh_vals, color="steelblue", alpha=0.85)
    axc.set_xticks(x)
    axc.set_xticklabels(labels)
    axc.set_ylim(0.0, 1.0)
    axc.set_ylabel("Coherence (8-12 Hz)")
    axc.grid(axis="y", alpha=0.2)
    axc.set_title("Validation vs ground_truth")

    axp.bar(x, plv_vals, color="darkorange", alpha=0.85)
    axp.set_xticks(x)
    axp.set_xticklabels(labels)
    axp.set_ylim(0.0, 1.0)
    axp.set_ylabel("PLV (8-12 Hz)")
    axp.grid(axis="y", alpha=0.2)
    bar_path = output_directory / "postclean_validation_coh_plv.png"
    fig_bar.savefig(bar_path, dpi=220)
    plt.close(fig_bar)

    # ---- summary text ----
    summary_lines = [
        "Post-clean denoising + validation report",
        f"stim_vhdr_path={stim_vhdr_path}",
        f"cleaned_epochs_path={cleaned_epochs_path}",
        f"reference_channel={reference_channel}",
        f"sfreq={sfreq}",
        f"epoch_window_s={epoch_window_s}",
        f"baseline_window_s={baseline_window_s}",
        f"validation_window_s={validation_window_s}",
        f"metric_band_hz={metric_band_hz}",
        f"high_pass_hz={high_pass_hz}",
        f"ica_n_components={ica_n_components}",
        f"ica_method={ica_method}",
        f"ica_random_state={ica_random_state}",
        f"ica_auto_exclude_top_n={ica_auto_exclude_top_n}",
        f"ssp_n_eeg={ssp_n_eeg}",
        f"sound_note={sound_note}",
        f"saved_metrics_csv={metrics_csv}",
        f"saved_timecourse_plot={tc_path}",
        f"saved_coh_plv_plot={bar_path}",
        "results=",
    ]
    for row in metric_rows:
        summary_lines.append(
            f"  {row['method']}: status={row['status']}, "
            f"coh={row['coherence_8_12']}, plv={row['plv_8_12']}, "
            f"corr={row['timecorr_validation_window']}, notes={row['notes']}"
        )
    summary_path = output_directory / "postclean_validation_summary.txt"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Saved {metrics_csv}")
    print(f"Saved {tc_path}")
    print(f"Saved {bar_path}")
    print(f"Saved {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
