function setup_environment(wkf_cfg)
    % SETUP_ENVIRONMENT Configure paths and libraries
    
    % Add SimNIBS MATLAB tools
    addpath(wkf_cfg.simnibs_path);
    
    % Set library path for Linux
    setenv('LD_LIBRARY_PATH', [...
        fullfile(wkf_cfg.simnibs_path, 'external/lib/linux') ':' ...
        getenv('LD_LIBRARY_PATH')]);
    
    % Add neuroimaging toolboxes
    addpath(wkf_cfg.fieldtrip_path);
    addpath(wkf_cfg.spm_path);
    ft_defaults;  % Initialize FieldTrip
    
    % Add custom code
    addpath(wkf_cfg.code_path);
    
    fprintf('=== Environment configured ===\n');
end
