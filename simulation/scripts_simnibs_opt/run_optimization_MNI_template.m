function MNI_results = run_optimization_MNI_template(MNI_opt_config, wkf_cfg,subject_id)
    % RUN_OPTIMIZATION_MNI_TEMPLATE Executes montage optimization for MNI152 template
    % while disabling unnecessary steps like CHARM, lesion mapping, leadfield, and simulation.
    %
    % INPUTS:
    %   - MNI_opt_config: Configuration structure for montage optimization.
    %   - wkf_cfg: Workflow configuration containing paths and execution flags.
    %
    % OUTPUT:
    %   - MNI_results: Results of the montage optimization process.

    % Ensure only montage optimization runs, disable other steps
    wkf_cfg.run_charm = true;          % Run CHARM processing

    wkf_cfg.run_montage = true;
    wkf_cfg.run_simulation = true;      % Run SimNIBS simulation
    wkf_cfg.run_leadfield = true;       % Run leadfield optimization

    % Print execution details
    fprintf('=== Running MNI152 Montage Optimization ===\n');
    
    % Run only montage optimization
    process_single_subject(wkf_cfg, subject_id, MNI_opt_config);

    % Collect results 
    fprintf('Output Files are stored in: %s',fullfile(wkf_cfg.output_path, subject_id));

    fprintf('=== MNI152 Montage Optimization Completed ===\n');
end
