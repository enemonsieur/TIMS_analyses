function opt_config = initialize_optimization_config(mode)
    % INITIALIZE_OPTIMIZATION_CONFIG Initializes the optimization structure based on input mode.
    % mode: 'funct' for functional optimization, 'anat' for anatomical optimization.
    
    if nargin < 1
        error('Mode must be specified as ''funct'' or ''anat''.');
    end
    
    % Setup SimNIBS environment
    setup_environment();

    % Check input mode and initialize correct optimization structure
    switch lower(mode)
        case 'anat'
            opt_config = opt_struct('TDCSoptimize');
            opt_config.name = 'opt_anat_ACC';
            opt_config.open_in_gmsh = false; % opens simnibs

            % Optimization constraints
            opt_config.max_total_current = 4e-3;  % Default: 2 mA
            opt_config.max_individual_current = 1e-3;  % Default: 1 mA per electrode
            opt_config.max_active_electrodes = 32;  % Allow up to XX active electrodes

            opt_config.target(1).positions = [];  % No specific MNI coordinates
            opt_config.target(1).intensity = 0.2;  %  electric field intensity
            opt_config.target(1).directions = 'normal';  % Default field direction
            opt_config.target(1).weight = [];  % No specific weight
            opt_config.target(1).indexes = [];  % No specific ROI indices
            opt_config.target(1).radius = 5;  % target region radius (mm)

            % Define avoid regions
            opt_config.avoid.tissues = 1006;  % Avoid the Eyes
            
            % Avoidance regions for tACS targeting the ACC
            % opt_config.avoid.positions = [
            %     -15, -40, 70;   % Left PoG (trunk representation)
            %      55, -20, 20;   % Right PoG (tongue and larynx)
            %      40, -25, 55;   % Right PrG (upper limb)
            %     -10, -95, 20;   % Left Superior Occipital Gyrus
            %     -35,  10,  2    % Left Insular Cortex
            % ];
            %Default avoidance region radius (mm)

        case 'funct'
            opt_config = opt_struct('TDCSDistributedOptimize');
            opt_config.name = 'opt_func';

            % Optimization constraints
            opt_config.max_total_current = 4e-3;  % Default: 2 mA
            opt_config.max_individual_current = 1e-3; % used to be 3e-4;  % Default: 1 mA per electrode
            opt_config.max_active_electrodes = 32;  % Allow up to 2 active electrodes

            % ** Other Attribute: **
            %opt_config.min_img_value = 2.1;  % Minimum image value for optimization (Ruffini et al., 2014)

            % Image with the field we want
            opt_config.target_image = 'C:\Users\njeuk\OneDrive\Documents\GRK\SUBS_OPTITACS\MRI_data\FMOtarget_c.nii';
            opt_config.mni_space = true; % Set to false if target_image is in subject space
            opt_config.intensity = 0.3; % V/m?
            opt_config.open_in_gmsh = false; % V/m?

            %necessary to map the sub
            opt_config.subpath = [];

        otherwise
            error('Invalid mode. Use ''funct'' or ''anat''.');
    end
end

function setup_environment()
    addpath('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/lib/python3.11/site-packages/simnibs/matlab_tools');
    setenv('LD_LIBRARY_PATH', sprintf('/cm/shared/uniol/sw/zen4/13.1/SimNIBS/4.1.0-foss-2023a/external/lib/linux:%s', getenv('LD_LIBRARY_PATH')));
end
