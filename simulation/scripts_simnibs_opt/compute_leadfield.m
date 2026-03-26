function compute_leadfield(Mainpath, subject_id, PATHOUT, lesion_conductivity, Codepath,pathfem,EEG_cap,cond_id)
    
    % OPTIMIZE_LEADFIELD Runs the tDCS leadfield optimization for a given subject.
    %

    %CHANGE. Not GOOD

    % Validate Inputs
    if nargin < 5
        error(['Mainpath, subject_id, PATHOUT, lesion_conductivity,' ...
            ' Codepath are required inputs.']);
    end
    
    %   Validate that no leadfield has been done. You only need one!
    %CHANGE THIS
    if ~results_exist(PATHOUT, subject_id, 'leadfield',pathfem)
        prepare_leadfield_script();

        
        % Initialize subject-specific paths
        paths = initialize_paths();
        fprintf('Initialize Path for subject %s...\n', subject_id);
        drawnow; pause(0.01); system('echo ""');
        
        % Create Output Directory
        create_output_directory(paths.leadfield_dir);
        fprintf('Create Output Directory for subject %s...\n', subject_id);
        drawnow; pause(0.01); system('echo ""');

        % Initialize SimNIBS TDCS Leadfield Structure
        tdcs_lf = initialize_leadfield(paths.m2m_dir, paths.leadfield_dir,EEG_cap);
        
        % Apply lesion conductivity for Patients
        if ~contains(subject_id, 'control')
            fprintf('Applying Lesion Conductivity for subject %s...\n', subject_id);
            drawnow; pause(0.01); system('echo ""');

            tdcs_lf = add_lesion_conductivity(tdcs_lf, lesion_conductivity,cond_id);
        end

        % Start Timer
        timer_start = tic;
        elapsed_timer = start_elapsed_timer(timer_start);
    
        % Run SimNIBS
        fprintf('Contents of tdcs_lf before simulation:\n');
        disp(tdcs_lf);
        drawnow; pause(0.01); system('echo ""');
        
        fprintf('Running tDCS leadfield simulation for subject %s...\n', subject_id);

        run_simnibs(tdcs_lf);

        fprintf('Leadfield simulation completed successfully for subject %s.\n', subject_id);
        drawnow; pause(0.01); system('echo ""');

        % Cleanup Timer & Display Final Elapsed Time
        stop_elapsed_timer(elapsed_timer, timer_start);

    else
        fprintf('Skipping leadfield optimization for %s: Results already exist.\n', subject_id);
    end

    %                ===== NESTED FUNCTIONS ===== %

    function paths = initialize_paths()
        paths = struct();
        
        % Define Subject-Specific Paths
        paths.m2m_dir = fullfile(Mainpath, subject_id, ['m2m_' subject_id]);
        if ~isfolder(paths.m2m_dir)
            fprintf('The m2m folder for subject %s does not exist: %s', subject_id, paths.m2m_dir);
            drawnow; pause(0.01); system('echo ""');
        end
    
        % Define Output Directory
        paths.leadfield_dir = fullfile(PATHOUT, subject_id, pathfem);
    end
    
    % Nested function for creating the output directory
    function create_output_directory(directory)
        if ~exist(directory, 'dir')
            mkdir(directory);
            fprintf('Output directory created: %s\n', directory);
        end

    end
    

    function prepare_leadfield_script()
        % PREPARE_LEADFIELD_SCRIPT Copies the leadfield optimization script to the subject's folder
        
        % Define source and destination paths
        source_file = fullfile(Codepath, 'run_tdcs_leadfield.m');
        dest_folder = fullfile(Mainpath, subject_id, ['m2m_' subject_id]);
        dest_file = fullfile(dest_folder, 'run_tdcs_leadfield.m');
        
        % Check if the script already exists in the destination
        if ~exist(dest_file, 'file')
            % Copy the script if it doesn't exist
            copyfile(source_file, dest_file);
            fprintf('Copied run_tdcs_leadfield.m to %s\n', dest_folder);
        else
            fprintf('run_tdcs_leadfield.m already exists in %s\n', dest_folder);
        end
    end

end


% ====== INIT HELPER FUNCTIONS ====== %




function tdcs_lf = initialize_leadfield(m2m_dir, leadfield_dir,EEG_cap)
    % INITIALIZE_LEADFIELD Initializes SimNIBS TDCS Leadfield structure.
    
    tdcs_lf = sim_struct('TDCSLEADFIELD');
    tdcs_lf.subpath = m2m_dir;  
    tdcs_lf.pathfem = leadfield_dir;  
    %  Specify the EEG cap file 
    tdcs_lf.eeg_cap = fullfile(m2m_dir, 'eeg_positions', EEG_cap);

    % Validate the file exists
    if ~isfile(tdcs_lf.eeg_cap)
        error('EEG Cap file missing: %s', tdcs_lf.eeg_cap);
    end
end

function S = add_lesion_conductivity(S, cond_value,cond_id)
    % ADD_LESION_CONDUCTIVITY Adds lesion conductivity to the SimNIBS session.
    fprintf('Adding lesion conductivity: %.3f S/m\n', cond_value);
    drawnow; pause(0.01); system('echo ""');
    S.cond(cond_id).value = cond_value;
    S.cond(cond_id).name = 'Lesion';
end

% Track the time  for further OPt.
function elapsed_timer = start_elapsed_timer(timer_start)
    % START_ELAPSED_TIMER Starts a timer that displays elapsed time every 2 minutes.
    elapsed_timer = timer('ExecutionMode', 'fixedRate', ...
        'Period', 120, ... % Every 2 minutes
        'TimerFcn', @(~,~) display_elapsed_time(timer_start)); 
    start(elapsed_timer);
end

function stop_elapsed_timer(elapsed_timer, timer_start)
    
% STOP_ELAPSED_TIMER Stops the elapsed timer and displays the final time.
    if exist('elapsed_timer', 'var') && isvalid(elapsed_timer)
        stop(elapsed_timer);
        delete(elapsed_timer);
    end
    elapsed_time = toc(timer_start);
    fprintf('Total elapsed time: %.2f seconds (%.2f minutes)\n', elapsed_time, elapsed_time / 60);
end

function display_elapsed_time(timer_start)
    fprintf('Elapsed time: %.2f minutes\n', toc(timer_start) / 60);
end


