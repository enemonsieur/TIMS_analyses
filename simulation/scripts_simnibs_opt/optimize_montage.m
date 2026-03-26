function optimize_montage(main_path, subject_id, output_path, mni_coords, opt_name, opt_type, leadfield_path)
    
    % This function optimizes the montages of a subject to output an excel
    % with the ideal Parameters ( positions of electrodes and intensity of
    % current )

    %%
    % CHANGE THE init opt config and this, to input the key opt. values you
    % want. 
    %                      ====== MAIN CODE ======
    if ~results_exist(output_path, subject_id, 'montage')

        fprintf('Preparing montage optimization...\n');
        drawnow; pause(0.01); system('echo ""');

        %setup_environment();

        fprintf(' Loading subject data...\n');
        [leadfield_file, m2m_path] = load_subject_data();
    
        % Initialize optimization with defined parameters
        fprintf('Initializing optimization...\n');
        drawnow; pause(0.01); system('echo ""');
        
        %change for 'func' if you need to use the functional map
        opt = initialize_optimization_config(opt_type);    
    
        % Apply subject-specific transformations
        fprintf(' Applying subject-specific transformations...\n');
        drawnow; pause(0.01); system('echo ""');

        opt = apply_subject_specific_settings(opt, subject_id, leadfield_file, output_path, mni_coords, m2m_path, opt_type);
        

        % Run the optimization
        fprintf('Running actual optimization computation...\n');
        run_optimization();


    else
        fprintf('Skipping montage optimization for %s: Results already exist.\n', subject_id);

    end

    % Always stop the timer if it was started
    if exist('elapsed_timer', 'var') && isvalid(elapsed_timer)
        stop_elapsed_timer(elapsed_timer, timer_start);
    end
    

    %%              ======= Nested functions ======

        function run_optimization()
            fprintf('[%s] Running SimNIBS optimization...\n', datestr(now));
            run_simnibs(opt);
            drawnow; pause(0.01); system('echo ""');
            close all;

            fprintf('[%s] Optimization completed successfully! Results saved in: %s\n', datestr(now), output_path);
        end
    
        function [leadfield_file, m2m_path] = load_subject_data()
            % LOAD_SUBJECT_DATA Loads leadfield file and m2m path of a subject.
            %
            % Inputs:
            %   - main_path:  base path where subject data is stored.
            %   - subject_id:  subject identifier.
            %   - output_path: directory where output files are saved.
            
            % Outputs:
            %   - leadfield_file: path to the leadfield file.
            %   - m2m_path:  path to the subject's m2m directory.
        
            % Define m2m path
            m2m_path = fullfile(main_path, subject_id, ['m2m_', subject_id]);
        
            % Locate the leadfield file
            leadfield_file_info = dir(fullfile(output_path,subject_id, leadfield_path, '*.hdf5'));
            if isempty(leadfield_file_info)
                error('No leadfield file (.hdf5) found somehwere in: %s', fullfile(output_path,subject_id, leadfield_path));
            end
            
            leadfield_file = fullfile(leadfield_file_info(1).folder, leadfield_file_info(1).name);
            fprintf('leadfield file (.hdf5) file is: %s \n', leadfield_file);

        end
        
        
        function opt = apply_subject_specific_settings(opt, subject_id, leadfield_file, output_path, mni_coords, m2m_path, opt_type)
            % APPLY_SUBJECT_SPECIFIC_SETTINGS Updates the optimization structure with subject-specific details.
            % we use the general leadfile obtained from the charm 
            % CFM with anything standard
            % Assign subject-specific settings
            fprintf('Applying leadfield %s \n for subject: %s ...\n', leadfield_file,subject_id);

            opt.leadfield_hdf = leadfield_file;
            opt.name = fullfile(output_path, subject_id, [subject_id, opt_name]);
            opt.subpath = m2m_path;
            fprintf('M2M_path for subject: %s is...\n', subject_id);
            disp(m2m_path);
            
            if strcmp(opt_type, 'anat')  % Corrected condition syntax
                % Target MNI coordinates to subject space
                opt.target.positions = mni2subject_coords(mni_coords, m2m_path);
            
                % Convert avoid region MNI coordinates to subject space
                if ~isempty(opt.avoid) && ~isempty(opt.avoid(1).positions)  % check for non-empty struct
                    opt.avoid(1).positions = mni2subject_coords(opt.avoid(1).positions, m2m_path);
                end
            
                % Display transformed coordinates
                fprintf('Applied Anat Opt. for subject: %s\n', subject_id);
                disp(opt.target.positions);
            
            elseif strcmp(opt_type, 'funct')  % Corrected condition syntax
               
                fprintf('Applying Functional Opt. for subject: %s\n', subject_id); 

            end

            disp(opt);


        end

        function setup_environment()
            addpath('C:\Users\njeuk\SimNIBS-4.1\simnibs_env\Lib\site-packages\simnibs\matlab_tools');
            setenv('LD_LIBRARY_PATH', sprintf('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/external/lib/linux:%s', getenv('LD_LIBRARY_PATH')));
        end
end


%% Helper function to initialize optimization structure values

% Boring stuff
function stop_elapsed_timer(elapsed_timer, timer_start)
    
% STOP_ELAPSED_TIMER Stops the elapsed timer and displays the final time.
    if exist('elapsed_timer', 'var') && isvalid(elapsed_timer)
        stop(elapsed_timer);
        delete(elapsed_timer);
    end
    elapsed_time = toc(timer_start);
    fprintf('Total elapsed time: %.2f seconds (%.2f minutes)\n', elapsed_time, elapsed_time / 60);
end

function elapsed_timer = start_elapsed_timer(timer_start)
    % START_ELAPSED_TIMER Starts a timer that displays elapsed time every 2 minutes.
    elapsed_timer = timer('ExecutionMode', 'fixedRate', ...
        'Period', 120, ... % Every 2 minutes
        'TimerFcn', @(~,~) display_elapsed_time(timer_start)); 
    start(elapsed_timer);
end

function display_elapsed_time(timer_start)
    fprintf('Elapsed time: %.2f minutes\n', toc(timer_start) / 60);
end


