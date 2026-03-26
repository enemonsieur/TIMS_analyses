% Load real workflow configuration
wkf_cfg = setup_workflow();
setup_environment(wkf_cfg);

fprintf('[TEST] Verifying run_simnibs for all subjects with real inputs (without computation)...\n');
drawnow; pause(0.01); system('echo ""');

subjects = {'control4'}; %,'control6', 'control7', 'control8', 'control9'}; %patient3','patient4', 'control6', 'control7', 'control8', 'control9'}; 
%subjects = {'patient7','patient8'}; 
%subjects = {'control21','control22', 'control5'};

wkf_cfg.output_path_MNI = fullfile(wkf_cfg.output_path,'s_CFM','starstim');

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
        %continue;
    else
        fprintf('youre good dude. Duuude');
    end

    fprintf('[PROCESSING] Running SimNIBS for subject: %s\n', subject_id);
   
    % please change the conductivity index to 305 or 51 (patients)
    run_simnibs_simulation(wkf_cfg.main_path, subject_id, ...
                           wkf_cfg.output_path_MNI, wkf_cfg.run_lesion_mapping, ...
                           wkf_cfg.montage_starstim, wkf_cfg);

    fprintf('[TEST PASSED] run_simnibs_simulation for %s logic executed successfully.\n', subject_id);
    drawnow; pause(0.01); system('echo ""');

end
fprintf('[SUCCESS] run_simnibs_simulation  executed successfully.\n');
drawnow; pause(0.01); system('echo ""');
