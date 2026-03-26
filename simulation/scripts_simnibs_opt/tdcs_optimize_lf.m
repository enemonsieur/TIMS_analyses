function optimize_montage(Mainpath, SubjectID, PATHOUT, mni_coords)

    addpath('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/lib/python3.11/site-packages/simnibs/matlab_tools');
    setenv('LD_LIBRARY_PATH', sprintf('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/external/lib/linux:%s', getenv('LD_LIBRARY_PATH')));
    disp(getenv('SIMNIBSPYTHON'));
    disp(getenv('PYTHONPATH'));

    % Start independent logging timer
    t = timer('ExecutionMode', 'fixedRate', ...
              'Period', 200, ... % Log every X minutes
              'TimerFcn', @(~,~) fprintf('[%s] Elapsed time: %.2f minutes\n', datestr(now), toc / 60));
    start(t);
    tic; % Start computation timer

    try
        % Step 1: Construct and Validate leadfield and m2m files

        if numel(leadfield_file) > 1
            warning('Multiple leadfield files found. Using the first one: %s', leadfield_file(1).name);
        end
        leadfield_file = fullfile(leadfield_file(1).folder, leadfield_file(1).name);
        
        % mesh_file = dir(fullfile(Mainpath, SubjectID, 'subject_volumes', '*scalar_fsavg*'));
        % if isempty(mesh_file)
        %     error('No mesh file containing "scalar_fsavg" found in: %s', fullfile(Mainpath, SubjectID, 'subject_volumes'));
        % end
        % mesh_file = fullfile(mesh_file(1).folder, mesh_file(1).name);

        % Define the m2m folder path
        m2m_path = fullfile(Mainpath, SubjectID, ['m2m_', SubjectID]);
      

        % Step 2: Initialize tDCS Optimization Structure
        fprintf('[%s] Initializing tDCS optimization structure...\n', datestr(now));
        opt = opt_struct('TDCSoptimize');
        opt.leadfield_hdf = leadfield_file; 
        opt.name = fullfile(PATHOUT, SubjectID, ['_',SubjectID,'ACC_opt']);

        % current flow opt
        opt.max_total_current = 2e-3;
        opt.max_individual_current = 1e-3;
        opt.max_active_electrodes = 8;

        % Define ACC target region
        subject_coords = mni2subject_coords(mni_coords, m2m_path);
        if isempty(subject_coords)
            error('Failed to transform MNI coordinates for subject %s.', SubjectID);
        end
        opt.target.positions = subject_coords; %[-50.7, 5.1, 55.5]; %

        % Display the transformed coordinates
        disp('Transformed MNI coordinates to subject space:');
        disp(opt.target.positions);
        

        % target opt
        opt.target.directions = 'normal'; % Optimize for normal E-field direction
        opt.target.intensity = 0.2; % Target intensity (V/m)
        opt.target.radius = 5; % Target radius in mm

        
        % Define avoid region (occipital lobe)
        avoid_positions_mni = [
            -15, -90, 30;  % Left occipital
            15, -90, 30;   % Right occipital
            0, -95, 20;    % Center posterior
        ];
        avoid_positions_subject = mni2subject_coords(avoid_positions_mni,m2m_path);

        % Assign avoid regions with radius
        opt.avoid(1).positions = avoid_positions_subject; % Transformed positions
        opt.avoid(1).radius = 20; % Radius in mm
        opt.avoid(1).weight = 1.0; % Default weight

        % Step 3: Run the Optimization
        fprintf('[%s] Running SimNIBS optimization...\n', datestr(now));
        run_simnibs(opt);
        
        % Confirm setup
        disp('Avoid region setup:');
        disp(opt.avoid);

        % Log success
        fprintf('[%s] Optimization completed successfully! Results saved in: %s\n', ...
                datestr(now), PATHOUT);
    catch ME
        fprintf('Error in function %s at line %d\n', ME.stack(1).file, ME.stack(1).line);
        fprintf('Error message: %s\n', ME.message);
        for i = 2:length(ME.stack)
            fprintf('Called by %s at line %d\n', ME.stack(i).file, ME.stack(i).line);
        end
        rethrow(ME);
    end

    % Stop and clean up the logging timer
    stop(t);
    delete(t);
    fprintf('[%s] Total optimization time: %.2f minutes\n', datestr(now), toc / 60);
end
