function add_lesion_and_recreate_mesh(Mainpath, SubjectID)
%% Script 2: Add Lesion to Tissue Label and Recreate Mesh
% this scripts adds the lesion to the tissue label, 
% If we work with subjects without lesions, they will be skipped.


% Validate inputs
if nargin < 2
    error('Mainpath and SubjectID are required inputs.');
end

% Define Sub, Setting and Log paths
SubjectPath = fullfile(Mainpath, SubjectID);


% Define the paths to the NIfTI files for T1 and T2 and Lesions
nifti_T1 = dir(fullfile(Mainpath, SubjectID, '*T1*.nii*'));
nifti_T2 = dir(fullfile(Mainpath, SubjectID, '*T2*.nii*'));
LesionPath = dir(fullfile(Mainpath, SubjectID, 'Lesions', '*lesion*.nii*'));
% Check if the files were found and retrieve their names
if isempty(nifti_T1) || isempty(nifti_T2) || isempty(LesionPath)
    error('T1, T2, or Lesion files not found for subject %s', SubjectID);
end

% extract the files
nifti_T1 = fullfile(nifti_T1.folder, nifti_T1.name);
nifti_T2 = fullfile(nifti_T2.folder, nifti_T2.name);
LesionPath = fullfile(LesionPath.folder, LesionPath.name);

cd(SubjectPath); % !



% Step 3: Add the lesion to the tissue label using the add_tissues_to_upsampled command
TissueLabelFile = fullfile(Mainpath, SubjectID, ['m2m_' SubjectID], 'label_prep', 'tissue_labeling_upsampled.nii.gz');
BackupTissueLabelFile = fullfile(Mainpath, SubjectID, ['m2m_' SubjectID], 'label_prep', 'tissue_labeling_upsampled_orig.nii.gz');

% Check if the original file exists
if isfile(TissueLabelFile)
    % If the backup file does not exist, create it
    if ~isfile(BackupTissueLabelFile)
        copyfile(TissueLabelFile, BackupTissueLabelFile);
        fprintf('Created backup: %s\n', BackupTissueLabelFile);
    else
        fprintf('Backup already exists: %s\n', BackupTissueLabelFile);
    end
else
    error('The original tissue labeling file does not exist: %s\n', TissueLabelFile);
end

% Run the command to add the Lesion path
offset_value = 50;  
add_tissue_cmd = ['add_tissues_to_upsampled -i "' LesionPath '" -t "' TissueLabelFile '" -o "' TissueLabelFile '" --offset ' num2str(offset_value)];
[status, cmdout] = system(add_tissue_cmd);

% Check if the lesion was successfully added
if status == 0 && exist(TissueLabelFile, 'file') == 2
    fprintf('Lesion successfully added to tissue label for %s\n', SubjectID);
else
    error('Error adding lesion to tissue label for %s: %s\n', SubjectID, cmdout);
end

% Step 4: Recreate the mesh using charm after adding the lesion
mesh_cmd = ['charm ' SubjectID ' --mesh'];
[status, cmdout] = system(mesh_cmd);

% Check if mesh creation was successful
meshOutputPath = fullfile(SubjectPath, 'mesh');
if status == 0 && exist(meshOutputPath, 'dir') == 7
    fprintf('Mesh successfully created for %s\n', SubjectID);
else
    error('Error recreating mesh for %s: %s\n', SubjectID, cmdout);
end

% Log mesh recreation output
fid = fopen(logFile, 'a');
fprintf(fid, 'Mesh successfully created for %s.\n', SubjectID);
fclose(fid);

end
