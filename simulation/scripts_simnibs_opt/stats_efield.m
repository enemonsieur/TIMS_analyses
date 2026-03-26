function stats_efield(SubjectID, PATHOUT, atlasPath, ROI_INDEX, Mainpath,FIELD_TRIP,NIFTI)
    try
        % Initialize
        %subjects = {'patient1', 'control1', 'control2'};
        % Load and Validate Paths
        addpath(FIELD_TRIP);
        addpath(NIFTI);
        ft_defaults;
        
        % Add SimNIBS MATLAB tools
        addpath('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/lib/python3.11/site-packages/simnibs/matlab_tools');
        setenv('LD_LIBRARY_PATH', sprintf('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/external/lib/linux:%s', getenv('LD_LIBRARY_PATH')));
        setenv('SIMNIBSPYTHON', '/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/bin/python3');
        setenv('SIMNIBS_RESOURCES', '/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/lib/python3.11/site-packages/simnibs/resources/templates/');

        disp(getenv('SIMNIBSPYTHON'));
        disp(getenv('PYTHONPATH'));


        % Verify Inputs

        % fsavg Overlay Files for Magnitude and Normal Components
        fsavgDir = fullfile(PATHOUT, SubjectID, 'fsavg_overlays');  % Directory for fsavg overlay files
        lhMagnFile = fullfile(fsavgDir, ['lh.' SubjectID '_TDCS_1_scalar.fsavg.E.magn']);
        lhNormalFile = fullfile(fsavgDir, ['lh.' SubjectID '_TDCS_1_scalar.fsavg.E.normal']);
        rhMagnFile = fullfile(fsavgDir, ['rh.' SubjectID '_TDCS_1_scalar.fsavg.E.magn']);
        rhNormalFile = fullfile(fsavgDir, ['rh.' SubjectID '_TDCS_1_scalar.fsavg.E.normal']);
        
        % Validate fsavg Overlay Files
        if ~isfile(lhMagnFile) || ~isfile(lhNormalFile) || ~isfile(rhMagnFile) || ~isfile(rhNormalFile)
            error('fsavg overlay files not found for subject %s in directory: %s', SubjectID, fsavgDir);
        end

        % Load Atlas (e.g., Brainnetome)
        atlas = ft_read_atlas(atlasPath);  % Path to the atlas
        disp('Atlas loaded successfully.');
        fprintf('All inputs loaded and validated successfully.\n');
        




        %% PART 2: Testing the Loading codes

        % Load left and right hemisphere magnitude data
        x_magn_lh = mesh_load_fsresults(lhMagnFile);  % Left hemisphere magnitude
        x_magn_rh = mesh_load_fsresults(rhMagnFile);  % Right hemisphere magnitude
        x_magn.node_data{1}.data = [x_magn_lh.node_data{1}.data; x_magn_rh.node_data{1}.data];  % Combine magnitudes
        
        % Load left and right hemisphere normal component data
        x_norm_lh = mesh_load_fsresults(lhNormalFile);  % Left hemisphere normal component
        x_norm_rh = mesh_load_fsresults(rhNormalFile);  % Right hemisphere normal component
        x_norm.node_data{1}.data = [x_norm_lh.node_data{1}.data; x_norm_rh.node_data{1}.data];  % Combine normals

        % Prepare FieldTrip structure for E-field data
        scr = [];
        scr.coordsys = 'tal';  % SimNIBS default coordinate system
        scr.pow = x_magn.node_data{1}.data;  % Assign magnitude as "power" for FieldTrip compatibility
        disp('E-field magn loaded and prepared.');
        
        % Step 3: Interpolate E-Field Data Directly onto Atlas
        cfg = [];
        cfg.parameter = 'pow';  % Interpolate the "power" parameter
        scr = ft_sourceinterpolate(cfg, scr, atlas);  % Align E-field data with atlas
        disp('E-field data interpolated onto atlas.');
        
        % Step 4: Create ACC Mask
        ROI_INDEX = [177, 178, 179, 180];  % Brainnetome ACC region indices
        roi_index = ismember(atlas.tissue, ROI_INDEX);  % Binary mask for ACC
        
        % Apply Mask to E-Field Data
        scr.mask = roi_index;  % Mask for ACC region
        scr.pow(~roi_index) = NaN;  % Set values outside ACC to NaN
        disp('ACC mask applied to E-field data.');
        
        % Step 5: Visualize Results
        figure;
        ft_plot_mesh(atlas, 'vertexcolor', double(roi_index), 'facealpha', 0.3); hold on;  % Plot ACC mask
        ft_plot_mesh(scr, 'vertexcolor', scr.pow, 'facealpha', double(scr.mask));  % Plot E-field data
        colormap(jet);
        colorbar;
        title('E-field Magnitudes in ACC');
        disp('Visualization completed.');
        
        % Step 6: Extract Top 300 Voxels in ACC
        % Flatten E-field data within ACC mask
        acc_values = scr.pow(roi_index);
        % Sort and select the top 300 highest values
        sorted_values = sort(acc_values, 'descend');
        top_300_values = sorted_values(1:min(300, length(sorted_values)));  % Handle fewer voxels if ACC is small
        disp('Top 300 voxels extracted from ACC.');
        

        %%
        % results = struct;
        % 
        % % Add SimNIBS MATLAB tools
        % addpath('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/lib/python3.11/site-packages/simnibs/matlab_tools');
        % setenv('LD_LIBRARY_PATH', sprintf('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/external/lib/linux:%s', getenv('LD_LIBRARY_PATH')));
        % setenv('SIMNIBSPYTHON', '/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/bin/python3');
        % 
        % disp(getenv('SIMNIBSPYTHON'));
        % disp(getenv('PYTHONPATH'));
        % 
        % % Process each subject
        % for i = 1:length(subjects)
        %     subj = subjects{i};
        %     disp(['Processing ', subj]);
        % 
        %     % Define paths
        %     subject_overlay_path = fullfile(PATHOUT, subj, 'subject_overlays');
        %     surface_file = fullfile(subject_overlay_path, [subj '_TDCS_1_scalar_central.msh']);
        % 
        %     % Load the mesh file
        %     surf = mesh_load_gmsh4(surface_file);
        % 
        %     % Load atlas and define ROI
        %     [labels, snames] = subject_atlas(surf,fullfile(Mainpath, subj, ['m2m_' subj]), 'HCP_MMP1');
        %     roi_mask = ismember(labels.node_data{end}.data, ROI_INDEX); % Combine ROI indices
        % 
        %     % Extract magnitude and normal components
        %     magn_field_idx = get_field_idx(surf, 'E_magn', 'node');
        %     norm_field_idx = get_field_idx(surf, 'E_normal', 'node');
        % 
        %     field_data_magn = surf.node_data{magn_field_idx}.data;
        %     field_data_normal = surf.node_data{norm_field_idx}.data;
        % 
        %     % Filter data within ROI
        %     field_data_magn_roi = field_data_magn(roi_mask);
        %     field_data_normal_roi = field_data_normal(roi_mask);
        % 
        %     % Save in struct
        %     results(i).id = subj;
        %     results(i).E_magn = field_data_magn_roi;
        %     results(i).E_normal = field_data_normal_roi;
        % end
        % 
        % % Truncate data to smallest size across subjects
        % min_nodes = min(cellfun(@length, {results.E_normal}));
        % for i = 1:length(results)
        %     results(i).E_normal_truncated = results(i).E_normal(1:min_nodes);
        % end
        % 
        % % Save results in the PATHOUT directory
        % results_file = fullfile(PATHOUT, 'electric_field_results.mat');
        % save(results_file, 'results');
        % disp(['Results saved to ', results_file]);
        % 
        %  % Perform t-tests with FDR
        % pairings = {[1, 2], [1, 3], [2, 3]};
        % pair_names = {'patient1 vs control1', 'patient1 vs control2', 'control1 vs control2'};
        % pair_p_values = [];
        % t_values = [];
        % mean_std_data = [];
        % 
        % for p = 1:length(pairings)
        %     group1 = pairings{p}(1);
        %     group2 = pairings{p}(2);
        % 
        %     % Get truncated data for groups
        %     data1 = results(group1).E_normal_truncated;
        %     data2 = results(group2).E_normal_truncated;
        % 
        %     % Perform t-test
        %     [~, p_value, ~, stats] = ttest2(data1, data2);
        % 
        %     % Store p-value and t-statistic
        %     pair_p_values = [pair_p_values; p_value];
        %     t_values = [t_values; stats.tstat];
        % 
        %     % Store mean and std for plotting
        %     mean_std_data(p).means = [mean(data1), mean(data2)];
        %     mean_std_data(p).stds = [std(data1), std(data2)];
        % end
        % 
        % % Apply FDR correction
        % fdr_corrected_p = mafdr(pair_p_values, 'BHFDR', true);
        % 
        % % Plot the results
        % figure;
        % for p = 1:length(pairings)
        %     subplot(1, 3, p);
        % 
        %     % Extract data for this pairing
        %     data = mean_std_data(p);
        % 
        %     % Bar plot with error bars
        %     bar(1:2, data.means, 'FaceColor', 'flat');
        %     hold on;
        %     errorbar(1:2, data.means, data.stds, 'k', 'LineStyle', 'none');
        %     hold off;
        % 
        %     % Add annotations
        %     title(pair_names{p});
        %     ylabel('Mean E_normal');
        %     xlabel('Groups');
        %     xticks(1:2);
        %     xticklabels({'Group1', 'Group2'});
        %     legend({sprintf('p = %.3f', fdr_corrected_p(p)), sprintf('t = %.3f', t_values(p))});
        % end
        % 
        % 
        % disp('Finished processing and plotting! Feel free to cry loudly now.');
        % %% SAVE the data and plot with version control
        % 
        % % Get Today's Date in the Correct Format
        % today_date = datetime("now", "Format", "ddMMMyy");  % Example: '14Nov24'
        % 
        % % Define Output Paths
        % AtlasOutPath = PATHOUT;  % Make sure PATHOUT is passed dynamically
        % 
        % % Check for Existing Files and Determine the Next Version
        % data_file_pattern = fullfile(AtlasOutPath, ['results_atlas_analysis_*-', char(today_date), '.mat']);
        % plot_file_pattern = fullfile(AtlasOutPath, ['Mean_Efield_Plot_*-', char(today_date), '.png']);
        % 
        % % Check for Existing Data Files
        % existing_data_files = dir(data_file_pattern);
        % if isempty(existing_data_files)
        %     version_num = 1; % First version of the day
        % else
        %     % Extract version numbers from existing files
        %     version_numbers = regexp({existing_data_files.name}, ['v(\d+)-', char(today_date)], 'tokens');
        %     version_numbers = cellfun(@(x) str2double(x{1}), version_numbers);
        %     version_num = max(version_numbers) + 1; % Increment version
        % end
        % 
        % % Construct the Version String
        % version_str = ['v' num2str(version_num) '-' char(today_date)];
        % 
        % % Save Data with Version Control
        % data_savename = fullfile(AtlasOutPath, ['results_atlas_analysis_' version_str '.mat']);
        % save(data_savename, 'results');
        % fprintf('Data saved as: %s\n', data_savename);
        % 
        % % Save Plot with Version Control
        % plot_filename = fullfile(AtlasOutPath, ['Mean_Efield_Plot_' version_str '.png']);
        % saveas(gcf, plot_filename);
        % fprintf('Plot saved as: %s\n', plot_filename);
        % 
        % % Close the plot to free memory
        % close(gcf);

    catch ME
        fprintf('An error occurred:\n');
        fprintf('Error in %s at line %d\n', ME.stack(1).file, ME.stack(1).line);
        fprintf('Error Message: %s\n', ME.message);
        rethrow(ME);
    end
end
