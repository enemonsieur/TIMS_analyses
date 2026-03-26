% Main Script to Run All SimNIBS Steps Sequentially
% This script sequentially calls all the scripts necessary to complete the
% SimNIBS analysis in a HPC Environment. 

% Code to use for the HPC

% cd /fs/dss/home/nodi2384/SUBS_OPTITACS/code/
% job_id=$(sbatch --output=slurm.%j.out --error=slurm.%j.err run_all_steps.job | awk '{print $NF}')
% 
% # Wait until SLURM output file appears
% while [ ! -f "slurm.${job_id}.out" ]; do
%     sleep 5
% done
% 
% # Use unbuffered, real-time output for both stdout and stderr
% stdbuf -oL -eL tail -f "slurm.${job_id}.out" & stdbuf -oL -eL tail -f "slurm.${job_id}.err"

%%
% Here you have to define the part of the anaylsis you wanna do, inside the
% main_simnibs and run it. It's extremely inneficient, but thats what I use
% for debugging.


function main_simnibs() %_opt

    % Load workflow configuration
    wkf_cfg = setup_workflow();
    setup_environment(wkf_cfg);

    fprintf('[TEST] optimize_montage for all control subjects ...\n');
    drawnow; pause(0.01); system('echo ""');
    
    % Only process control subjects
    subjects = {'MNI152'};
    % subjects = { 'control2',  'control4',  'control5',  'control6', ...
    %              'control7',  'control8',  'control9',  'control10', 'control11', ...
    %              'control13', 'control14', 'control15', 'control16', 'control17', ...
    %              'control18', 'control19', 'control21', 'control22', ...
    %              'patient1',  'patient2',  'patient3',  'patient4',  'patient5', ...
    %              'patient6',  'patient7',  'patient8'};

    % subjects = {'patient1',  'patient2',  'patient3',  'patient4',  'patient5', ...
    %              'patient6',  'patient7',  'patient8'};

    wkf_cfg.output_path_MNI = fullfile(wkf_cfg.output_path,'o_CFM');

    for i = 1:numel(subjects)

        subject_id = subjects{i};
        fprintf('[PROCESSING] Running Optimization for subject: %s\n', subject_id);

        % Define MNI coordinates 
        mni_coords = wkf_cfg.mni_coords; 
        % Run Optimization %the opt.parameters are in initialize optimization config
        opt_name = 'anat_starstim';
        opt_type = 'anat';
        leadfield_path = 'leadfield_64c';

        try
            optimize_montage(wkf_cfg.main_path, subject_id, ...
                wkf_cfg.output_path_MNI, mni_coords, opt_name, ...
                opt_type,leadfield_path);
            fprintf('[TEST PASSED] optimize_montage for %s executed successfully.\n', subject_id);

        catch ME
            warning('[ERROR] CHARM failed for %s: %s', subject_id, ME.message);
            continue;
        end

    end

    fprintf('[TEST PASSED] optimize_montage executed.\n');
    drawnow; pause(0.01); system('echo ""');
end




function main_simnibs_leadfields() %
    % Run leadfields!
    % Load real workflow configuration

    wkf_cfg = setup_workflow();
    setup_environment(wkf_cfg);

    wkf_cfg.lf_pathfem = 'leadfield_starstim';
    wkf_cfg.lf_EEG_cap = 'EEG10-20_Neuroelectrics.csv';

    % Restrict subjects to control6 - control9
    % or subjects = get_subject_list(wkf_cfg.main_path, wkf_cfg.subject_pattern);
    % !!!!!!!!!!! , 'patient1' missing !!!!!!!!!!!!!!!!!1111
    subjects = {'MNI152'};
                % ', 'control11',  'control13', ... 
                % 'control14', 'control15', 'control16', 'control17', ...
                % 'control18', 'control19', 'control20', 'control21', ...
                % 'control22', 'control5','control12'};  
    conductivity_idx = 51; 

    for i = 1:numel(subjects)
        subject_id = subjects{i};

        fprintf('[PROCESSING] Computing leadfield for subject: %s\n', subject_id);
        

        % !!! Change the lesion conductivity index to the index of the
        % stroke patient in compute leadfield !!
        % Run leadfield computation
        compute_leadfield(wkf_cfg.main_path, subject_id, ...
                          wkf_cfg.output_path, wkf_cfg.lesion_conductivity, ...
                          wkf_cfg.code_path, wkf_cfg.lf_pathfem, ...
                          wkf_cfg.lf_EEG_cap, conductivity_idx);

        fprintf('[TEST PASSED] Leadfield computation for %s executed successfully.\n', subject_id);
        drawnow; pause(0.01); system('echo ""');
    end

    fprintf('[TEST PASSED] Leadfield computation logic executed successfully for all subjects.\n');
    drawnow; pause(0.01); system('echo ""');
end




function main_simnibs_charm_all_subs() %
    % Load real workflow configuration
    wkf_cfg = setup_workflow();
    setup_environment(wkf_cfg);

    fprintf('[TEST] Verifying CHARM execution for all control subjects...\n');
    drawnow; pause(0.01); system('echo ""');

    % Process only control subjects
    subjects = {'patient5','patient8'}; %'patient6','patient7',,;    
    % !!!! REDO PATIENT: 5,8
    % Process only lesion for Patien6 and Patient7
    for i = 1:numel(subjects)
        subject_id = subjects{i};
        fprintf('[PROCESSING] Running CHARM for subject: %s\n', subject_id);
        drawnow; pause(0.01); system('echo ""');

        %generate flag to skip done subjects
        charm_done = fullfile(wkf_cfg.main_path,subject_id, ...
            ['m2m_', subject_id], '*.msh');

        % if ~isempty(dir(charm_done))
        %     fprintf('Warning: Charm done for %s ... skipping', subject_id)
        %     continue;
        % end

        % Run charm
        try
            run_charm_and_backup(wkf_cfg.main_path, subject_id);
            fprintf('[TEST PASSED] CHARM completed for %s.\n', subject_id);
        catch ME
            warning('[ERROR] CHARM failed for %s: %s', subject_id, ME.message);
        end

        drawnow; pause(0.01); system('echo ""');
    end

    fprintf('CHARM completed successfully for control subjects.\n');
    drawnow; pause(0.01); system('echo ""');
end
% CHANGE


% 
% 
% function main_simnibs_run_simnibs_MNI152_sCFM() %
%     Load real workflow configuration
%     wkf_cfg = setup_workflow();
%     setup_environment(wkf_cfg);
% 
%     fprintf('[TEST] Verifying run_simnibs for all subjects with real inputs (without computation)...\n');
%     drawnow; pause(0.01); system('echo ""');
% 
%     subjects = {'control4','control6', 'control7', 'control8', 'control9'}; %patient3','patient4', 'control6', 'control7', 'control8', 'control9'}; 
%     subjects = {'patient5','patient6','patient7','patient8'}; 
%     subjects = {'control21','control22', 'control5'};
% 
%     wkf_cfg.output_path_MNI = fullfile(wkf_cfg.output_path,'MNI152_std_Montage_32c_20_02');
% 
%     for i = 1:numel(subjects)
%         subject_id = subjects{i};
% 
%         generate flag to skip done subjects
%         contains the .msh directory if it exist
%         cfm_done = dir(fullfile(wkf_cfg.output_path_MNI,subject_id, '*.msh'));
%         charm_done = dir(fullfile(wkf_cfg.main_path,subject_id, ...
%             ['m2m_', subject_id], '*.msh'));
% 
%         if  there's a .msh in output OR no .msh in Input... skips
%         if ~isempty(cfm_done) || isempty(charm_done)
%             fprintf('Warning: can not run simnibs CFM. Check charm or CFM folder of %s ... skipping\n', subject_id)
%             continue;
%         end
% 
%         fprintf('[PROCESSING] Running SimNIBS for subject: %s\n', subject_id);
% 
%         please change the conductivity index to 305 or 51 (patients)
%         run_simnibs_simulation(wkf_cfg.main_path, subject_id, ...
%                                wkf_cfg.output_path_MNI, wkf_cfg.run_lesion_mapping, ...
%                                wkf_cfg.montage_32c);
% 
%         fprintf('[TEST PASSED] run_simnibs_simulation for %s logic executed successfully.\n', subject_id);
%         drawnow; pause(0.01); system('echo ""');
% 
%     end
%     fprintf('[SUCCESS] run_simnibs_simulation  executed successfully.\n');
%     drawnow; pause(0.01); system('echo ""');
% end
% 
% 



function main_simnibs_() %_run_simnibs_MNI152_sCFM
    % Load real workflow configuration
    wkf_cfg = setup_workflow();
    setup_environment(wkf_cfg);

    fprintf('[TEST] Verifying run_simnibs for all subjects with real inputs (without computation)...\n');
    drawnow; pause(0.01); system('echo ""');
    
    %subjects = {'control4','control6', 'control7', 'control8', 'control9'}; %patient3','patient4', 'control6', 'control7', 'control8', 'control9'}; 
    %subjects = {'patient2','patient3','patient4'}; 
    subjects = {'patient1','controlMNI152'}; 

    wkf_cfg.output_path_MNI = fullfile(wkf_cfg.output_path,'MNI152_std_Montage_32c_20_02');
    
    for i = 1:numel(subjects)
        subject_id = subjects{i};

        %generate flag to skip done subjects
        % contains the .msh directory if it exist
        cfm_done = dir(fullfile(wkf_cfg.output_path_MNI,subject_id, '*.msh'));
        charm_done = dir(fullfile(wkf_cfg.main_path,subject_id, ...
            ['m2m_', subject_id], '*.msh'));

        % if  there's a .msh in output OR no .msh in Input... skips
        if ~isempty(cfm_done) || isempty(charm_done)
            fprintf('Warning: can not run simnibs CFM. Check charm or CFM folder of %s ... skipping\n', subject_id)
            continue;
        end

        fprintf('[PROCESSING] Running SimNIBS for subject: %s\n', subject_id);
       
        % please change the conductivity index to 305 or 51 (patients)
        run_simnibs_simulation(wkf_cfg.main_path, subject_id, ...
                               wkf_cfg.output_path_MNI, wkf_cfg.run_lesion_mapping, ...
                               wkf_cfg.montage_32c);

        fprintf('[TEST PASSED] run_simnibs_simulation for %s logic executed successfully.\n', subject_id);
        drawnow; pause(0.01); system('echo ""');

    end
    fprintf('[SUCCESS] run_simnibs_simulation  executed successfully.\n');
    drawnow; pause(0.01); system('echo ""');
end
%





function main_simnibs_run_charm() %
    wkf_cfg = setup_workflow();
    setup_environment(wkf_cfg);

    fprintf('[TEST] charm without lesion with mni not atlas...\n');
    drawnow; pause(0.01); system('echo ""');
    
    subject_id = 'control3'; %, 'control6', 'control7', 'control8', 'control9'}; 

    %generate charm flag

    %wkf_cfg.output_path_MNI = fullfile(wkf_cfg.output_path,'MNI152_std_Montage_18_02');
    executeCharmCommand(wkf_cfg.main_path,subject_id,"/fs/dss/home/nodi2384/SUBS_OPTITACS/MRI_data/patient2/IG05TH18_T1w.nii.gz", ...
        "/fs/dss/home/nodi2384/SUBS_OPTITACS/MRI_data/patient2/IG05TH18_acq-tse_T2w.nii.gz", ...
        "/fs/dss/home/nodi2384/SUBS_OPTITACS/MRI_data/patient2/settings.ini")

    function executeCharmCommand(mainPath, subjectID, t1, t2, settingsFile)
    
        % Constructs and executes the CHARM command.
        cd(fullfile(mainPath, subjectID));  % Change directory to subject folder.
        cmd = sprintf('charm "%s" "%s"', subjectID, t1);
        
        % Include the T2 file if provided.
        if ~isempty(t2)
            cmd = sprintf('%s "%s"', cmd, t2);
        end
        
        % Include the settings file if it exists.
        if isfile(settingsFile)
            cmd = sprintf('%s --usesettings "%s"', cmd, settingsFile);
        end
        
        % Apply both qform and sform fixes.
        cmd = sprintf('%s --forceqform --forcerun', cmd);
        fprintf('Executing: %s\n', cmd);
        
        % Run CHARM command.
        status = system(cmd);
        if status ~= 0
            error('CHARM execution failed for %s. Check SLURM output.', subjectID);
        end
    end
end




%           ====== Level 1 - RUN Analysis PIPELINE ======

%CHANGE




%% 

                %====== HELPER FUNCTIONS ====== %

