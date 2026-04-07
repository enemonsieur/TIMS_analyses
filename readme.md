# TIMS Workspace Entry Point

This repository contains TIMS/TMS-EEG analysis code, experiment notes, and results across multiple experiments. This README is the navigation entry point for the workspace. It tells you where to start and where each kind of work lives. It is not the full scientific record.

## Workflow First

Use the repo in this order:

1. Read the latest memo chain to understand the current decision context.
2. Check the shared documentation files for memo, script, and figure rules.
3. Reuse the shared helper modules before adding logic to analysis scripts.
4. Open the main analyses when you need the scripts behind current conclusions.
5. Open exploratory analyses only when you are tracing probes, failed paths, or method tests.
6. Find outputs by experiment at the top level whenever possible.

## Latest Memo Chain

Memos in this repo are chained decision documents. Each new memo is expected to link the latest relevant earlier memo in its `Latest Shared Information` section, so the right reading order is newest to older, not oldest to newest. The current latest visible chain happens to be exp05, but that should not be assumed to stay true as the repo changes.

- Latest decision memo: [`MEMO_exp05_5_3_ctbs_intensity_decision.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO_exp05_5_3_ctbs_intensity_decision.md)
- Immediate predecessor: [`MEMO_exp05_5_2_ctbs_recovery.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO_exp05_5_2_ctbs_recovery.md)
- Earlier anchor in the same chain: [`MEMO_exp05_analysis.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO_exp05_analysis.md)
- Memo rules/template: [`MEMO.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO.md)

## How To Navigate TIMS

### Docs And Decision Records

- [`docs/memos/MEMO.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO.md): memo template and chaining rules
- [`docs/standards/DATAVIZ_FRAMEWORK.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/standards/DATAVIZ_FRAMEWORK.md): figure planning and claim-first plotting rules
- [`docs/standards/SKRIPT.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/standards/SKRIPT.md): analysis script rules
- [`docs/standards/ANSWER.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/standards/ANSWER.md): response style guide for coding work
- [`docs/reference/TIMS_pilot_pipeline_map.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/reference/TIMS_pilot_pipeline_map.md): I/O-oriented pipeline map for the pilot/dose-response work
- [`docs/experiments/exp05.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/experiments/exp05.md): experiment-specific lab-book style reference for exp05

### Helper/Core Files

Shared reusable logic belongs in the core modules, not in new one-off scripts.

- [`preprocessing.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/preprocessing.py): reusable preprocessing, epoching, timing, and metric helpers
- [`plot_helpers.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/plot_helpers.py): reusable figure and plotting helpers

If logic is reused across analyses, it should be moved into one of these files instead of being copied into experiment scripts.

### Main Analyses

Main analyses are the scripts that support current conclusions or memo-backed outputs.

- [`main_analysis_exp03.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/main_analysis_exp03.py)
- [`postclean_denoise_validate_exp03.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/postclean_denoise_validate_exp03.py)
- [`compare_stim_baseline_exp03.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/compare_stim_baseline_exp03.py)
- [`analyses_TEP_exp04.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyses_TEP_exp04.py)
- [`analyses_spectral_exp04.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyses_spectral_exp04.py)
- [`analyses_dynamics_exp04.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyses_dynamics_exp04.py)
- [`analyses_artifact_exp05.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyses_artifact_exp05.py)
- [`analyses_ssd_exp05.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyses_ssd_exp05.py)

### Exploratory Analyses

Exploratory analyses are probes, method experiments, drafts, and non-decision-driving checks. They are useful for development and evidence, but they should not be treated as the default scientific entry point.

- [`analyses_ssd_exp05_skript.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyses_ssd_exp05_skript.py)
- [`explore_exp05_fc1_baseline_ssd.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/explore_exp05_fc1_baseline_ssd.py)
- [`analyses_ica_topo_exp05.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyses_ica_topo_exp05.py)
- [`compare_baseline_gt_exp05.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/compare_baseline_gt_exp05.py)
- [`analyze_baseline_gt.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/analyze_baseline_gt.py)
- [`plot_channels_epoch_avg_exp05.py`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/plot_channels_epoch_avg_exp05.py)
- [`evidence`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/evidence): comparison runs, probes, and failure evidence
- [`old`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/old): archived analyses and older experiment work

## Where Things Live

### Raw Data

- [`TIMS_data_sync`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/TIMS_data_sync): BrainVision recordings and related synced data

### Protocol Files

- Top-level `.tims` and protocol `.py` files define programmable stimulation protocols used by specific experiments

### Main Results

Experiment outputs should be easy to find from the top level by experiment name.

- `exp03` outputs:
  - [`exp03_pulse_centered_analysis_run03`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/exp03_pulse_centered_analysis_run03)
  - [`exp03_postpulse_fixed_channels`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/exp03_postpulse_fixed_channels)
- `exp04` outputs:
  - [`EXP04_TEP_analysis`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP04_TEP_analysis)
  - [`EXP04_spectral_analysis`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP04_spectral_analysis)
  - [`EXP04_dynamics_analysis`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP04_dynamics_analysis)
- `exp05` outputs:
  - [`EXP05_artifact_characterization`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_artifact_characterization)
  - [`EXP05_baseline_gt_analysis`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_baseline_gt_analysis)
  - [`EXP05_baseline_comparison`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_baseline_comparison)
  - [`EXP05_channel_avg`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_channel_avg)
  - [`EXP05_explore_fc1_baseline_ssd`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_explore_fc1_baseline_ssd)
  - [`EXP05_ica_30pct`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_ica_30pct)
  - [`EXP05_ssd_recovery`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_ssd_recovery)
  - [`EXP05_ssd_recovery_skript`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP05_ssd_recovery_skript)
- `exp06` outputs:
  - [`EXP06_qc_context`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/EXP06_qc_context)

### Exploratory Or Legacy Results

- [`evidence`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/evidence): probe outputs and comparison artifacts
- [`old`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/old): archived or legacy material that is no longer in the active result layout

## Classification Rules

- Main analyses: scripts that directly support current conclusions, memo-backed figures, or decision documents
- Exploratory analyses: probes, method tests, drafts, and diagnostics that help development but are not the default basis for conclusions
- Results: organize by experiment at the top level where possible, and avoid deep nested result trees unless there is a clear need

## Current Layout Issues

The repo now uses top-level experiment result folders more consistently, but there are still cleanup edges to resolve over time. The remaining direction is to keep new outputs experiment-scoped at the top level, avoid loose result files in the repo root, and keep exploratory material clearly separated from main result folders.
