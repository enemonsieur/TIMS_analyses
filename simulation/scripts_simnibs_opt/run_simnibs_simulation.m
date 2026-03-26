function run_simnibs_simulation(Mainpath, subject_id, PATHOUT_gen, lesion, montage_cfg, wkf_cfg)
    %% run_simnibs_simulation: Runs SimNIBS simulation with detailed debugging!
    % the main fuction to run the simNIBS Current Flow Modelling
    % it inputs the subjects ID and some config files (check
    % workflow_configuration)
    %output the .msh of the CFM

    %CHAGNGE: there are tonsof sanity checks here; which makes reading
    %tedious

    fprintf('Step 1: Validating inputs...\n');
    drawnow; pause(0.01); system('echo ""');
    if nargin < 6 || isempty(Mainpath) || isempty(subject_id) || isempty(PATHOUT_gen) || isempty(lesion) || isempty(montage_cfg) || isempty(wkf_cfg)
        error('Invalid inputs: All arguments (Mainpath, subject_id, PATHOUT_gen, lesion, montage_cfg, wkf_cfg) are required.');
    end

    % Check if simulation results already exist.
    fprintf('Step 2: Checking if simulation results exist for subject %s...\n', subject_id);
    drawnow; pause(0.01); system('echo ""');
    if results_exist(PATHOUT_gen, subject_id, 'simulation')
        fprintf('Results already exist for subject %s. Skipping simulation.\n', subject_id);
        drawnow; pause(0.01); system('echo ""');
        return;
    end

    % Setup paths.
    fprintf('Step 3: Setting up paths for subject %s...\n', subject_id);
    drawnow; pause(0.01); system('echo ""');
    [PATHTOMRI, PATHOUT] = setup_simnibs_paths(Mainpath, subject_id, PATHOUT_gen, wkf_cfg);
    fprintf('PATHTOMRI: %s\nPATHOUT: %s\n', PATHTOMRI, PATHOUT);
    drawnow; pause(0.01); system('echo ""');

    % Initialize SimNIBS session.
    fprintf('Step 4: Initializing SimNIBS session...\n');
    drawnow; pause(0.01); system('echo ""');
    S = initialize_simnibs_session(PATHTOMRI, PATHOUT);
    fprintf('SimNIBS session initialized.\n');
    drawnow; pause(0.01); system('echo ""');

    % Configure electrode montage.
    fprintf('Step 5: Configuring electrode montage...\n');
    drawnow; pause(0.01); system('echo ""');
    
    % Debug: Print montage_cfg contents.
    fprintf('montage_cfg contents:\n');
    disp(montage_cfg);
    drawnow; pause(0.01); system('echo ""');
    
    % If montage_cfg is a structure array, use only the first element.
    if numel(montage_cfg) > 1
        fprintf('Warning: montage_cfg is a structure array with %d elements. Using the first element only.\n', numel(montage_cfg));
        drawnow; pause(0.01); system('echo ""');
        montage_cfg = montage_cfg(1);
    end
    
    S = configure_montage(S, montage_cfg);
    fprintf('Electrode montage configured.\n');
    drawnow; pause(0.01); system('echo ""');

    % Debug: Check montage configuration.
    debug_check_montage(S, montage_cfg);

    % Add lesion conductivity if required.
    
    fprintf('Step 6: Lesion mapping enabled. Adding lesion conductivity...\n');
    drawnow; pause(0.01); system('echo ""');
    if contains(subject_id, 'patient')
        S = add_lesion_conductivity(S, montage_cfg.cond_value);
        fprintf('Lesion conductivity added.\n');
        drawnow; pause(0.01); system('echo ""');
    end


    % Run simulation.
    fprintf('Step 7: Running SimNIBS simulation for subject %s...\n', subject_id);
    drawnow; pause(0.01); system('echo ""');
    run_simnibs(S);
    fprintf('SimNIBS simulation completed successfully for subject %s.\n', subject_id);
    drawnow; pause(0.01); system('echo ""');

    %% Nested Function: initialize_simnibs_session
    function S = initialize_simnibs_session(PATHTOMRI, PATHOUT)
        S = sim_struct('SESSION');
        S.subpath = PATHTOMRI;
        S.pathfem = PATHOUT;
        S.fields = 'eE';
        S.map_to_vol = true;
        S.map_to_MNI = true;
        S.tissues_in_nifitis = 'all';
        S.map_to_surf = true;
        S.map_to_fsavg = true;
        fprintf('Initialized SimNIBS session structure.\n');
        drawnow; pause(0.01); system('echo ""');
    end

    %% Nested Function: setup_simnibs_paths
    function [PATHTOMRI, PATHOUT] = setup_simnibs_paths(Mainpath, subject_id, PATHOUT_gen, wkf_cfg)
        fprintf('Setting environment variables and adding required toolboxes...\n');
        drawnow; pause(0.01);
        
        % Set environment variables for Windows
        setenv('SIMNIBSPYTHON', fullfile('C:', 'Users', 'njeuk', 'SimNIBS-4.1', 'simnibs_env', 'python.exe'));
    
        % Add SimNIBS MATLAB tools to path
        addpath(wkf_cfg.simnibs_path);
        addpath(wkf_cfg.fieldtrip_path);
        addpath(wkf_cfg.spm_path);
    
        % Define paths
        PATHTOMRI = fullfile(Mainpath, subject_id, ['m2m_' subject_id]);
        PATHOUT = fullfile(PATHOUT_gen, subject_id);
        fprintf('Defined paths: PATHTOMRI = %s, PATHOUT = %s\n', PATHTOMRI, PATHOUT);
    
        % Create output directory if it doesn't exist
        if ~exist(PATHOUT, 'dir')
            mkdir(PATHOUT);
            fprintf('Created output directory: %s\n', PATHOUT);
        end
    
        % Check for existing SimNIBS files
        if check_existing_simnibs(PATHOUT)
            fprintf('Warning: Existing SimNIBS .mat files detected in %s.\n', PATHOUT);
        end
    
        fprintf('SimNIBS paths configured successfully.\n');
    end

    %% Nested Function: configure_montage
    function S = configure_montage(S, montage_cfg)
        fprintf('Inside configure_montage...\n');
        drawnow; pause(0.01); system('echo ""');
        S.poslist{1} = sim_struct('TDCSLIST');
        S.poslist{1}.currents = montage_cfg.currents;
        if ~iscell(montage_cfg.positions)
            error('montage_cfg.positions must be a cell array.');
        end
        numPositions = length(montage_cfg.positions);
        fprintf('Number of electrode positions: %d\n', numPositions);
        drawnow; pause(0.01); system('echo ""');
        for i = 1:numPositions
            fprintf('Configuring electrode %d...\n', i);
            drawnow; pause(0.01); system('echo ""');
            S.poslist{1}.electrode(i).channelnr = i;
            if isscalar(montage_cfg.dimensions)
                expectedDimensions = [montage_cfg.dimensions, montage_cfg.dimensions];
            else
                expectedDimensions = montage_cfg.dimensions;
            end
            S.poslist{1}.electrode(i).dimensions = expectedDimensions;
            S.poslist{1}.electrode(i).shape = montage_cfg.shape;
            S.poslist{1}.electrode(i).thickness = montage_cfg.thickness;
            S.poslist{1}.electrode(i).centre = montage_cfg.positions{i};
            fprintf('Electrode %d configured: channelnr=%d, dimensions=%s, shape=%s, thickness=%g, centre=%s\n', ...
                i, S.poslist{1}.electrode(i).channelnr, mat2str(expectedDimensions), ...
                S.poslist{1}.electrode(i).shape, S.poslist{1}.electrode(i).thickness, ...
                mat2str(S.poslist{1}.electrode(i).centre));
            drawnow; pause(0.01); system('echo ""');
        end
    end

    %% Nested Function: add_lesion_conductivity
    function S = add_lesion_conductivity(S, cond_value)
        fprintf('Adding lesion conductivity: %.3f S/m\n', cond_value);
        drawnow; pause(0.01); system('echo ""');
        S.poslist{1}.cond(51).value = 1.654;  %cond_value;
        S.poslist{1}.cond(51).name = 'Lesion';
        fprintf('Lesion conductivity assigned at index ???.\n');
        drawnow; pause(0.01); system('echo ""');
    end

    %% Nested Function: debug_check_montage
    function debug_check_montage(S, montage_cfg)
        fprintf('*** Running debug check for montage configuration ***\n');
        drawnow; pause(0.01); system('echo ""');
        if ~isequal(S.poslist{1}.currents, montage_cfg.currents)
            error('Mismatch in currents: S.poslist{1}.currents = %s, expected = %s', ...
                mat2str(S.poslist{1}.currents), mat2str(montage_cfg.currents));
        else
            fprintf('Currents match: %s\n', mat2str(S.poslist{1}.currents));
        end
        drawnow; pause(0.01); system('echo ""');
        nExpected = length(montage_cfg.positions);
        nActual = length(S.poslist{1}.electrode);
        if nActual ~= nExpected
            error('Mismatch in number of electrodes: %d configured, expected %d', nActual, nExpected);
        else
            fprintf('Number of electrodes match: %d\n', nExpected);
        end
        drawnow; pause(0.01); system('echo ""');
        for j = 1:nExpected
            electrode = S.poslist{1}.electrode(j);
            if electrode.channelnr ~= j
                error('Mismatch at electrode %d: channelnr = %d, expected %d', j, electrode.channelnr, j);
            end
            if isscalar(montage_cfg.dimensions)
                expectedDims = [montage_cfg.dimensions, montage_cfg.dimensions];
            else
                expectedDims = montage_cfg.dimensions;
            end
            if ~isequal(electrode.dimensions, expectedDims)
                error('Mismatch at electrode %d: dimensions = %s, expected = %s', j, mat2str(electrode.dimensions), mat2str(expectedDims));
            end
            if ~strcmp(electrode.shape, montage_cfg.shape)
                error('Mismatch at electrode %d: shape = %s, expected %s', j, electrode.shape, montage_cfg.shape);
            end
            if electrode.thickness ~= montage_cfg.thickness
                error('Mismatch at electrode %d: thickness = %g, expected %g', j, electrode.thickness, montage_cfg.thickness);
            end
            if ischar(montage_cfg.positions{j})
                if ~strcmp(electrode.centre, montage_cfg.positions{j})
                    error('Mismatch at electrode %d: centre = %s, expected %s', j, electrode.centre, montage_cfg.positions{j});
                end
            elseif isnumeric(montage_cfg.positions{j})
                if ~isequal(electrode.centre, montage_cfg.positions{j})
                    error('Mismatch at electrode %d: centre = %s, expected %s', j, mat2str(electrode.centre), mat2str(montage_cfg.positions{j}));
                end
            else
                error('Unknown data type for montage_cfg.positions{%d}', j);
            end
            fprintf('Electrode %d passed all checks.\n', j);
            drawnow; pause(0.01); system('echo ""');
        end
        fprintf('*** All montage configuration tests passed successfully ***\n');
        drawnow; pause(0.01); system('echo ""');
    end

end

%% Local Function: check_existing_simnibs
function already_exists = check_existing_simnibs(PATHOUT)
    mat_files = dir(fullfile(PATHOUT, '*.mat'));
    already_exists = ~isempty(mat_files);
    fprintf('Found %d SimNIBS .mat file(s) in %s.\n', numel(mat_files), PATHOUT);
    drawnow; pause(0.01); system('echo ""');
end
