function run_atlas_analysis(Mainpath, atlasPath, ROI_INDEX, SubjectID, PATHOUT,FIELDTRIP,NIFTI)
    dbstop if error
    try
        addpath(FIELDTRIP);
        addpath('/fs/dss/home/nodi2384/SUBS_OPTITACS/code/NIfTI_20140122/');
        % Initialize FIELDTRIP defaults and NIFTI
        ft_defaults;
        addpath(genpath(NIFTI));
        spm('defaults', 'FMRI');
        spm_get_defaults;
        if exist('load_untouch_nii', 'file') == 2
            disp('NIfTI toolbox initialized successfully.');
        else
            error('NIfTI function not found. Please check the path.');
        end
    
        % LOAD THE DEPENDENCIES
        % Define the Specific Output Path for Atlas Analysis
        AtlasOutPath = fullfile(PATHOUT,SubjectID, 'results_atlas_analysis');
        if ~isfolder(AtlasOutPath)
            mkdir(AtlasOutPath);
        end
        
        % Load Brain Atlas
        brainnetome = ft_read_atlas(atlasPath);
        % Get T1 MRI File for the Subject
    
        fprintf('Getting T1 file...\n'); 
        MRI_file = dir(fullfile(Mainpath, SubjectID, '*T1*.nii*'));
        if isempty(MRI_file)
            error('run atlas: MRI file not found for subject %s', SubjectID);
        end
        
        % Load and Normalize the MRI
        mri_mni = ft_read_mri(fullfile(MRI_file.folder, MRI_file.name));
        mri_mni.coordsys = 'ras';
    
        % Load SimNIBS Simulation Results: Magnetic and Efield
        magnE_path = dir(fullfile(PATHOUT, SubjectID, 'subject_volumes', [SubjectID '_TDCS_1_scalar_magnE.nii.gz']));
        if isempty(magnE_path)
            error('run atlas: SimNIBS magnE file not found for subject %s', SubjectID);
        end
        efield_path = dir(fullfile(PATHOUT, SubjectID, 'subject_volumes', [SubjectID '_TDCS_1_scalar_E.nii.gz']));
        
        % Check if the Files Exist
        disp(fullfile(magnE_path.folder, magnE_path.name));
        if isempty(efield_path)
            error('SimNIBS E-field file not found for subject %s', SubjectID);
        end
        
        % ESTIMATE the Efield from the Magn. field
        calc_efield = load_untouch_nii(fullfile(magnE_path.folder,magnE_path.name));
        mri_mni.fun = calc_efield.img; % in the mni, put the Efields to 
        % superimpose with each MNI voxels
        fprintf('loading Ef data sucess! \n');

    
        %% START THE ATLAS ANALYSIS
    

        % Normalize MRI to MNI Space (so that the subject can fit in to the brain atlas)
        cfg = [];
        mri_norm = ft_volumenormalise(cfg, mri_mni);
        fprintf('Volume of mni normalized! Now converting to MNI space... \n');
    
        mri_mni = ft_convert_coordsys(mri_norm, 'mni');
    
        % ATLAS INTERPOLATION
        % Braintomme = grid of voxels representing the brain’s anatomy,
        % value of braintomme voxel is = tissue type
        % mri_mni = standartized voxels 
        % interpolation: Assign the braintomme label (ex 187 for ACC) to the
        % most corresponding voxel in the mri_mni
        % ATLAS_interp = same size as mri mni, but contain the labels

        cfg = [];
        cfg.interpmethod = 'nearest';
        cfg.parameter = 'tissue';
        ATLAS_interp = ft_sourceinterpolate(cfg, brainnetome, mri_mni);
        
        
        % DEBUGGING STEPS FOR SIZES OF MAT. 
        % disp(['Size of ATLAS_interp.tissue: ', mat2str(size(ATLAS_interp.tissue))]);
        % disp(['Size of mri_mni.fun: ', mat2str(size(mri_mni.fun))]);
        % disp(class(ATLAS_interp));  % Should be 'struct'
        % disp(class(mri_mni));       % Should be 'struct'
        % % Debugging information for ATLAS_interp.tissue and ROI_INDEX
        % fprintf('Inspecting ATLAS_interp.tissue...\n');
        % disp(['Size of ATLAS_interp.tissue: ', mat2str(size(ATLAS_interp.tissue))]);  % Print the size of the tissue array
        % disp(['Class of ATLAS_interp.tissue: ', class(ATLAS_interp.tissue)]);  % Print the type of the tissue data
        % disp(['Unique values in ATLAS_interp.tissue: ', mat2str(unique(ATLAS_interp.tissue))]);  % Print unique values in tissue to see if 187 exists
        % % Debugging information for ROI_INDEX
        % fprintf('Inspecting ROI_INDEX...\n');
        % disp(['ROI_INDEX value: ', num2str(ROI_INDEX)]);  % Print the value of ROI_INDEX
        % %roi_index = (ATLAS_interp.tissue == ROI_INDEX);  % ROI_INDEX = 187 in this case
        % % Debugging: Check the size of roi_index
        % %disp(['Size of roi_index: ', mat2str(size(roi_index))]);
        % %if ~isequal(size(roi_index), size(mri_mni.fun))
        % %    error('Incompatible sizes between ROI mask and E-field data. Check atlas alignment.');
        % %end
    
    
        % EFIELD WITHIN ROI CALCULATIONS

        % Isolate the ROI
        roi_index = (ATLAS_interp.tissue == ROI_INDEX); %create 1 at 187 for ACC and zero otherwise   
        mri_mni.fun(~roi_index) = NaN;                  % Empty the eField out of the ROI 
        mri_mni.mask = roi_index;                       %add a mask to the mri_mni
        mean_efield = mean(mri_mni.fun, 'all', 'omitnan'); %also ID the mean efield
        
        % Print information about the mask
        fprintf('Mask information: Number of true values = %d, Number of false values = %d\n', sum(mri_mni.mask(:)), numel(mri_mni.mask) - sum(mri_mni.mask(:)));
        fprintf('Extracting whole Efield \n');
    
        % Extract E-Field values for ROI for statistical analysis
        efield_acc = mri_mni.fun;                  % take entire acc efield
        efield_values = efield_acc(mri_mni.mask);  % Extract only the E-field values within the ACC ROI
    
        % SANITY CHECKS
        % acc_mask = mri_mni.mask & (ATLAS_interp.tissue == ROI_INDEX);
        % % Find the Maximum E-Field Location
        % [max_efield, max_idx] = max(mri_mni.fun(:));  % Find the maximum value and its index
        % [max_x, max_y, max_z] = ind2sub(size(mri_mni.fun), max_idx);  % Convert to 3D coordinates
        % % Display Max E-Field Information
        % fprintf('Max E-field: %.5f at voxel (X: %d, Y: %d, Z: %d)\n', max_efield, max_x, max_y, max_z);
        % % Check if the Max E-field location is within the ACC mask
        % is_max_in_ACC = mri_mni.mask(max_idx);  % Binary value: 1 for inside ACC, 0 for outside
        % % ACC vs MAx
        % if is_max_in_ACC
        %     fprintf('Max E-field is within the ACC region.\n');
        % else 
        %     fprintf('Max E-field is outside the ACC region \n');
        % end
        % acc_mean_efield = mean(mri_mni.fun(acc_mask), 'omitnan');
        % disp(['Mean E-field in ACC: ', num2str(acc_mean_efield)]);
        % % Compare Mean E-field in ACC to Max E-field
        % mean_efield_ACC = mean(mri_mni.fun(mri_mni.mask), 'omitnan');  % Mean E-field in ACC
        % fprintf('Mean E-field in ACC: %.5f\n', mean_efield_ACC);
        % fprintf('Max E-field is %.2f times the mean E-field in the ACC.\n', max_efield / mean_efield_ACC);
        % mean_value = mean(mri_mni.fun(:), 'omitnan');
        % median_value = median(mri_mni.fun(:), 'omitnan');
        % fprintf('E-field value statistics: Mean = %.5f, Median = %.5f\n', mean_value, median_value);
        % fprintf('ROI Mask information: Number of true values = %d\n', sum(roi_index(:)));

    
    
    
        % PLOTTING the E-field in ACC

        % Init
        figure;

        %cfg.slicedim = 1; %sagg =2, Cor =3
        %cfg.axis = 'off';
        %cfg.nslices = 1;
        %cfg.slicerange = [60 70];
        cfg = [];
        cfg.method = 'ortho';
        cfg.location = 'max';  % Center the plot on the maximum E-field value
        cfg.funparameter = 'fun';
        cfg.maskparameter = 'mask';
        cfg.funcolorlim = 'auto'; %[0 0.8];
        cfg.crosshair = 'yes';

        % use sourceplot : A visualization tool of any SOURCE activity in
        % the MNI space (in our case, the Efield)
        ft_sourceplot(cfg, mri_mni);
        colormap(jet);
        sgtitle([SubjectID ' Mean E-field: ' num2str(mean_efield)]);

        %debugg
        disp(cfg);  % Display the configuration parameters to verify correct settings
        volshow(roi_index)
    
        %% SAVE the data with version control
        
        % Get Today's Date in the Correct Format
        today_date = datetime("now", "Format", "ddMMMyy");  % Example: '14Nov24'
        
        % Check for Existing Files and Determine the Next Version
        file_pattern = fullfile(AtlasOutPath, ['results_atlas_analysis_v*-', char(today_date), '.mat']);
        existing_files = dir(file_pattern);
        
        % Determine the Highest Version Number
        if isempty(existing_files)
            version_num = 1;
        else
            % Extract version numbers from existing files
            version_numbers = regexp({existing_files.name}, ['v(\d+)-', char(today_date)], 'tokens');
            version_numbers = cellfun(@(x) str2double(x{1}), version_numbers);
            version_num = max(version_numbers) + 1;
        end
        
        % Construct the Version String
        version_str = ['v' num2str(version_num) '-' char(today_date)];
        
        % Save the Data with Version Control
        savename = fullfile(AtlasOutPath, ['results_atlas_analysis_' version_str '.mat']);
        results_efield_roi = struct('SubjectID', SubjectID, 'efield_values', efield_values, 'efield_volume', efield_acc, 'mask', roi_index);
        save(savename, 'results_efield_roi');    save(savename, 'results_efield_roi');
        fprintf('Results saved as: %s\n', savename);
        
        % Save the Plot with Version Control
        plot_filename = fullfile(AtlasOutPath, ['Mean_Efield_Plot_' version_str '.png']);
        saveas(gcf, plot_filename);
        fprintf('Plot saved as: %s\n', plot_filename);
        close(gcf);
    catch ME
        % Print error to console
        fprintf('An error occurred in %s at line %d\n', ME.stack(1).file, ME.stack(1).line);
        fprintf('Error Message: %s\n', ME.message);
        rethrow(ME);  % Optionally stop execution after logging

end