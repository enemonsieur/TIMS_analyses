function run_charm_and_backup(mainPath, subjectID)
    % RUN_CHARM Executes CHARM pipeline with simple debugging.
    %   mainPath: Root directory containing subject data.
    %   subjectID: Subject folder identifier.
    %

    % Input Handling
    if nargin < 2
        error('mainPath and subjectID are required.');
    end

    % Path Setup
    subjectPath = fullfile(mainPath, subjectID);
    settingsFile = fullfile(subjectPath, ['m2m_' subjectID], 'settings.ini');

    % Validate MRI files (niftiT1 is required; niftiT2 is optional)
    [niftiT1, niftiT2, lesionPath] = validateNiftiFiles(subjectPath);

    
    % Pass mainPath to executeCharmCommand to fix undefined variable issue.
    executeCharmCommand(mainPath, subjectID, niftiT1, niftiT2, settingsFile);

    fprintf('CHARM execution complete for %s.\n', subjectID);

    % Process the lesion file
    processLesionFile(mainPath, subjectID, lesionPath);

    %% ======= Nested Functions =========

    function processLesionFile(mainPath, subjectID, lesionPath)
        % Process the lesion file using a fixed offset value.

        % Get tissue label files; creates a backup if missing.
        [tissueLabelFile, ~] = checkLabelFiles(mainPath, subjectID);

        % Pass lesionPath to RunLesionCharm to resolve its undefined usage.
        RunLesionCharm(subjectID, tissueLabelFile, lesionPath);
    end

    function [tissueLabelFile, backupTissueLabelFile] = checkLabelFiles(mainPath, subjectID)
        % Construct paths for tissue labeling files.
        tissueLabelFile = fullfile(mainPath, subjectID, ['m2m_' subjectID], 'label_prep', 'tissue_labeling_upsampled.nii.gz');
        backupTissueLabelFile = fullfile(mainPath, subjectID, ['m2m_' subjectID], 'label_prep', 'tissue_labeling_upsampled_orig.nii.gz');
        
        % Check if the original file exists; if so, create a backup if needed.
        %copyfile(backupTissueLabelFile,tissueLabelFile);

        if isfile(tissueLabelFile)
            if ~isfile(backupTissueLabelFile)
                copyfile(tissueLabelFile, backupTissueLabelFile);
                fprintf('Created backup: %s\n', backupTissueLabelFile);
            else
                fprintf('Backup already exists: %s\n', backupTissueLabelFile);
            end
        else
            error('The original tissue labeling file does not exist: %s\n', tissueLabelFile);
        end
    end


    function RunLesionCharm(subjectID, tissueLabelFile, lesionPath)
        % Run lesion processing command.
        % Corrected: Added lesionPath as parameter and used consistent variable names.
        sub_path = fullfile(mainPath, subjectID);
        cd(sub_path);
        add_tissue_cmd = ['add_tissues_to_upsampled -i "' lesionPath '" -t "' tissueLabelFile '" -o "' tissueLabelFile '" --offset 50'];
        [status, cmdout] = system(add_tissue_cmd);
        
        % Check if lesion addition was successful.
        if status == 0 && isfile(tissueLabelFile)
            fprintf('Lesion successfully added to tissue label for %s\n', subjectID);
        else
            error('Error adding lesion to tissue label for %s: %s\n', subjectID, cmdout);
        end
        
        % Recreate mesh using CHARM after adding the lesion.
        mesh_cmd = ['charm ' subjectID ' --mesh'];
        [status, cmdout] = system(mesh_cmd);
        
        % Define expected mesh output path (corrected from previous inconsistent naming).
        meshOutputPath = fullfile(mainPath, subjectID, [subjectID '.msh']);
        if status == 0 && exist(meshOutputPath, 'file') == 2
            fprintf('Mesh successfully created for %s\n', subjectID);
        else
            error('Error recreating mesh for %s: %s\n', subjectID, cmdout);
        end
    end

end

%% External Functions

function [niftiT1, niftiT2, lesion] = validateNiftiFiles(subjectPath)
    % Returns paths for T1 and T2 NIfTI files; lesion file is optional.
    % Corrected: Pass subjectPath to getLesionFile instead of using an undefined variable.
    niftiT1 = getFirstNifti(subjectPath, '*T1*.nii*');
    niftiT2 = getFirstNifti(subjectPath, '*T2*.nii*');
    lesion = getLesionFile(subjectPath);
    
    if isempty(niftiT1)
        error('Missing T1 file in %s.', subjectPath);
    end
    if isempty(niftiT2)
        fprintf('Warning: T2 file not found in %s. Proceeding without T2.\n', subjectPath);
    end
end

function lesion = getLesionFile(subjectPath)
    % searches for lesion files.
    lesionFiles = dir(fullfile(subjectPath, 'Lesions', '*lesion*.nii*'));
    if ~isempty(lesionFiles)
        lesion = fullfile(subjectPath, 'Lesions', lesionFiles(1).name);
    else
        fprintf('Lesion files not found for subject in %s\n', subjectPath);
        lesion = [];
    end
end

function filePath = getFirstNifti(folder, pattern)
    % Returns the first matching NIfTI file path in the specified folder.
    files = dir(fullfile(folder, pattern));
    if ~isempty(files)
        filePath = fullfile(folder, files(1).name);
    else
        filePath = [];
    end
end

function executeCharmCommand(mainPath, subjectID, t1, t2, settingsFile)
    % Constructs and executes the CHARM command.
    cd(fullfile(mainPath, subjectID));  % Change directory to subject folder.
    cmd = sprintf('charm "%s" "%s"', subjectID, t1);
    
    % Include the T2 file if provided.
    if ~isempty(t2)
        cmd = sprintf('%s "%s"', cmd, t2);
    end
    
    % Include the settings file if it exists.
    if isfile(settingsFile)
        cmd = sprintf('%s --usesettings "%s"', cmd, settingsFile);
    end
    
    % Apply both qform and sform fixes.
    cmd = sprintf('%s --forceqform --forcerun', cmd);
    fprintf('Executing: %s\n', cmd);
    
    % Run CHARM command.
    status = system(cmd);
    if status ~= 0
        error('CHARM execution failed for %s. Check SLURM output.', subjectID);
    end
end
