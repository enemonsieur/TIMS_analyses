function opt_config = create_opt_config(varargin)
    % CHANGE THIS BY SIMPLY CALLING THE SIMNIBS Env. (using wkf_cfg.environments)
    % And calling simnibs env, then call strct     setup_environment(wkf_cfg);

    % tdcs_optimize struct;     opt = opt_struct('TDCSoptimize');  
    %   and the .target and the .avoid strcts, to 
    % use THEIR Struct, to be able to directly create that. So we have the
    % Perfect structure, that has all the parrameters and I can just add
    % them.
    %
    % Usage Example:
    %   opt_config = create_opt_config('target_intensity', 0.3, 'max_active_electrodes', 1);
    
    % Load default parameters
    opt_config = initialize_optimization_config();

    % Override parameters dynamically
    for i = 1:2:length(varargin)
        param_name = varargin{i};
        param_value = varargin{i+1};

        if isfield(opt_config, param_name)
            opt_config.(param_name) = param_value;
        else
            error('Invalid parameter: %s', param_name);
        end
    end
end
