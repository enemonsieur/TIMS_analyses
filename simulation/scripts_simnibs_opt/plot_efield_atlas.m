function plot_efield_atlas(Mainpath, atlasPath, ROI_INDEX, SubjectID, PATHOUT, FIELDTRIP, NIFTI)
    dbstop if error
    try
        %% Setup and Initialization
        addpath(FIELDTRIP);
        addpath('/fs/dss/home/nodi2384/SUBS_OPTITACS/code/NIfTI_20140122/');
        ft_defaults;
        addpath(genpath(NIFTI));
        spm('defaults', 'FMRI');
        spm_get_defaults;

        if exist('load_untouch_nii', 'file') ~= 2
            error('NIfTI toolbox not found. Please check the path.');
        end

        %% Load Dependencies
        AtlasOutPath = fullfile(PATHOUT, SubjectID, 'results_atlas_analysis');
        if ~isfolder(AtlasOutPath), mkdir(AtlasOutPath); end

        brainnetome = ft_read_atlas(atlasPath); % Load brain atlas

        MRI_file = dir(fullfile(Mainpath, SubjectID, '*T1*.nii*'));
        if isempty(MRI_file)
            error('MRI file not found for subject %s', SubjectID);
        end
        mri_mni = ft_read_mri(fullfile(MRI_file.folder, MRI_file.name));
        mri_mni.coordsys = 'ras';

        % Load E-field Data
        magnE_path = dir(fullfile(PATHOUT, SubjectID, 'subject_volumes', [SubjectID '_TDCS_1_scalar_magnE.nii.gz']));
        efield_path = dir(fullfile(PATHOUT, SubjectID, 'subject_volumes', [SubjectID '_TDCS_1_scalar_E.nii.gz']));

        if isempty(magnE_path) || isempty(efield_path)
            error('E-field data files not found for subject %s', SubjectID);
        end

        calc_efield_scalarE = load_untouch_nii(fullfile(efield_path.folder, efield_path.name));

        %% Extract E-field Components and Compute θ_Z Volume
        efield_reshaped = reshape(calc_efield_scalarE.img, size(calc_efield_scalarE.img, 1), size(calc_efield_scalarE.img, 2), size(calc_efield_scalarE.img, 3), []);
        E_x = efield_reshaped(:, :, :, 1);
        E_y = efield_reshaped(:, :, :, 2);
        E_z = efield_reshaped(:, :, :, 3);

        % Compute θ_Z volume
        magnitude = sqrt(E_x.^2 + E_y.^2 + E_z.^2) + 1e-10; % Avoid division by zero
        theta_z_volume = acosd(E_z ./ magnitude); % Elevation angle

        % Initialize θ_Z volume in mri_mni and assign
        mri_mni.fun = theta_z_volume;

        %% Normalize MRI and θ_Z Volume
        cfg = [];
        mri_norm = ft_volumenormalise(cfg, mri_mni); % Normalize both anatomy and θ_Z
        mri_mni = ft_convert_coordsys(mri_norm, 'mni');

        %% Interpolate Atlas into MRI Space
        cfg = [];
        cfg.interpmethod = 'nearest';
        cfg.parameter = 'tissue';
        ATLAS_interp = ft_sourceinterpolate(cfg, brainnetome, mri_mni);

        %% Isolate ROI and Mask θ_Z
        ROI_INDEX_LIST = [178 180]; % Define ROI indices
        roi_index = ismember(ATLAS_interp.tissue, ROI_INDEX_LIST); % Create binary mask for ROI

        % Mask θ_Z volume outside ROI
        mri_mni.fun(~roi_index) = NaN;
        mri_mni.mask = roi_index;

        %% Generate ft_sourceplot for θ_Z Visualization
        cfg = [];
        cfg.method = 'ortho';
        cfg.funparameter = 'fun'; % Use θ_Z for visualization
        cfg.maskparameter = 'mask';
        cfg.funcolorlim = [0 180]; % θ_Z range
        ft_sourceplot(cfg, mri_mni);
        colormap(flipud(jet)); % Reverse colormap for clarity
        title(sprintf('Elevation Angle (θ_Z) Visualization for ROI (%s)', SubjectID));

        % Save the plot
        plot_filename = fullfile(AtlasOutPath, ['ThetaZ_Plot_', SubjectID, '.png']);
        saveas(gcf, plot_filename);
        fprintf('ft_sourceplot saved as: %s\n', plot_filename);
        close(gcf);

        %% Create 3D Vector Plot
        % Extract ROI coordinates
        [x, y, z] = ind2sub(size(mri_mni.fun), find(mri_mni.mask));

        % Compute mean magnitude and scale factor
        magnitudes = sqrt(E_x(roi_index).^2 + E_y(roi_index).^2 + E_z(roi_index).^2);
        avg_magnitude = mean(magnitudes, 'omitnan');
        ScaleFactor = max(0.1 / avg_magnitude, 1); % Dynamic scaling

        % Generate quiver3 plot
        figure;
        quiver3(x, y, z, ...
                E_x(roi_index), ...
                E_y(roi_index), ...
                E_z(roi_index), ...
                'AutoScale', 'on', ...
                'AutoScaleFactor', ScaleFactor, ...
                'Color', [0 0 1], ...
                'LineWidth', 0.5, ...
                'MaxHeadSize', 0.3);
        xlabel('X (Left-Right)');
        ylabel('Y (Anterior-Posterior)');
        zlabel('Z (Superior-Inferior)');
        title(sprintf('3D E-field Vectors in ROI (%s)', SubjectID));
        grid on;
        axis equal;

        % Save the vector plot
        vector_plot_file = fullfile(AtlasOutPath, ['Vector_Plot_', SubjectID, '.png']);
        saveas(gcf, vector_plot_file);
        fprintf('3D vector plot saved as: %s\n', vector_plot_file);
        close(gcf);

    catch ME
        fprintf('Error in %s at line %d\n', ME.stack(1).file, ME.stack(1).line);
        fprintf('Error Message: %s\n', ME.message);
        rethrow(ME);
    end
end
