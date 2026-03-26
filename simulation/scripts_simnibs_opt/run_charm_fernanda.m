function run_charm_fernanda()
% RUN_CHARM_FERNANDA Wrapper to run CHARM segmentation + lesion injection
% for Fernanda subject ID_270 using the existing scripts in this folder.
%
% Usage (interactive MATLAB):
%   addpath('scripts_simnibs_opt');
%   run_charm_fernanda();
%
% Usage (non-interactive / shell):
%   matlab -batch "run_charm_fernanda"
% or
%   matlab -nosplash -nodisplay -r "addpath('scripts_simnibs_opt'); run_charm_fernanda; exit;"

try
    wkf_cfg = setup_workflow();
    setup_environment(wkf_cfg);

    subjectID = 'control_270';
    fprintf('Running CHARM + lesion injection for %s (main_path=%s)\n', subjectID, wkf_cfg.main_path);
    run_charm_and_backup(wkf_cfg.main_path, subjectID);

    fprintf('Finished CHARM processing for %s.\n', subjectID);
catch ME
    fprintf('Error while running CHARM for subject: %s\n', ME.message);
    fprintf('%s\n', getReport(ME));
    rethrow(ME);
end
end