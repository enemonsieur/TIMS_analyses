function run_tdcs_leadfield(Mainpath, SubjectID, PATHOUT,config)
    % create a leadfield matrix of the subject using its charm results
    % the leadfiled will help theh Optimization later



    % Validate Inputs
    if nargin < 4
        error('Mainpath, SubjectID, PATHOUT, and config are required inputs.');
    end

    % Define Subject-Specific Paths
    m2m_dir = fullfile(Mainpath, SubjectID, ['m2m_' SubjectID]);
    if ~isfolder(m2m_dir)
        error('The m2m folder for subject %s does not exist: %s', SubjectID, m2m_dir);
    end

    % Define Output Directory
    leadfield_dir = fullfile(PATHOUT, SubjectID, 'leadfield');
    if ~exist(leadfield_dir, 'dir')
        mkdir(leadfield_dir);
        fprintf('Output directory created: %s\n', leadfield_dir);
    end

    % Initialize SimNIBS TDCS Leadfield Structure
    tdcs_lf = initialize_leadfield(m2m_dir, leadfield_dir);

    % Apply lesion conductivity dynamically
    if config.has_lesion
        tdcs_lf = add_lesion_conductivity(tdcs_lf, config.lesion_conductivity);
    end

    % Start Timer
    timer_start = tic;
    elapsed_timer = start_elapsed_timer(timer_start);

    % Run SimNIBS
    fprintf('Running tDCS leadfield simulation for subject %s...\n', SubjectID);
    run_simnibs(tdcs_lf);
    fprintf('Leadfield simulation completed successfully for subject %s.\n', SubjectID);

    % Cleanup Timer & Display Final Elapsed Time
    stop_elapsed_timer(elapsed_timer, timer_start);
    end


% ====== INIT HELPER FUNCTIONS ====== %

function tdcs_lf = initialize_leadfield(m2m_dir, leadfield_dir)
    % INITIALIZE_LEADFIELD Initializes SimNIBS TDCS Leadfield structure.
    
    tdcs_lf = sim_struct('TDCSLEADFIELD');
    tdcs_lf.subpath = m2m_dir;  
    tdcs_lf.pathfem = leadfield_dir;  
end

function S = add_lesion_conductivity(S, cond_value)
    % ADD_LESION_CONDUCTIVITY Adds lesion conductivity to the SimNIBS session.
    fprintf('Adding lesion conductivity: %.3f S/m\n', cond_value);
    S.poslist{1}.cond(51).value = cond_value;
    S.poslist{1}.cond(51).name = 'Lesion';
end

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


