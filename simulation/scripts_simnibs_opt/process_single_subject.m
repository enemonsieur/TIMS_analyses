function process_single_subject(wkf_cfg, subject_id,opt_config)
    
        % This function will take ONE subject at a time and execute only the
        % selected steps based on the pipeline settings. It ensures modular execution 
        % for CHARM processing, lesion mapping, FEM/CFM with SimNIBS, leadfield, 
        % and montage optimization.
        %
        % INPUT PARAMETERS:
        % - subject_id: A string representing the subject's identifier.
        % - wkf_cfg: A structure containing execution flags and paths.
        % - opt_config: A structure containing montage optimization parameters.
        %
        % The function dynamically checks `wkf_cfg` to determine which steps 
        % to execute and prints logs for each step being run or skipped.
    
        
        %==================================================
    
       
        % Define step execution map
        step_map = struct( ...
            'run_charm', @() run_charm_and_backup(wkf_cfg.main_path, subject_id), ...
            'run_lesion_mapping', @() add_lesion_and_recreate_mesh(wkf_cfg.main_path, subject_id), ...
            'run_simulation', @() run_simnibs_simulation(wkf_cfg.main_path, subject_id, ...
                wkf_cfg.output_path, wkf_cfg.run_lesion_mapping, wkf_cfg.montage), ...
            'run_leadfield', @() compute_leadfield(wkf_cfg.main_path, subject_id, ...
                wkf_cfg.output_path, wkf_cfg.lesion_conductivity,wkf_cfg.code_path), ...
            'run_montage', @() optimize_montage(wkf_cfg.main_path, subject_id, ...
                wkf_cfg.output_path, wkf_cfg.mni_coords, opt_config) ...
        );
    
        % Loop through the steps and execute only enabled ones
        step_names = fieldnames(step_map);
        for i = 1:numel(step_names)
            step = step_names{i};
            if wkf_cfg.(step)  % Execute only if flag is true
                fprintf('Executing: %s for subject %s\n', step, subject_id);
                step_map.(step)();
            else
                fprintf('Skipping: %s for subject %s\n', step, subject_id);
            end
        end
    end