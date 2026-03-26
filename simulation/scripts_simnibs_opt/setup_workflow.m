
function wkf_cfg = setup_workflow()

    % INITIALIZE_CONFIG Define all paths and parameters of the whole
    % Workflow
    
    wkf_cfg = struct(); % a simple struc.
    
    % Primary paths that will contain the rest
    % --- Original GRK paths (commented out) ---
    % wkf_cfg.main_path = 'C:\Users\njeuk\OneDrive\Documents\GRK\SUBS_OPTITACS\StartStim_Optimization\s_CFM';
    % wkf_cfg.output_path = 'C:\Users\njeuk\OneDrive\Documents\GRK\SUBS_OPTITACS\StartStim_Optimization\';
    % wkf_cfg.code_path = 'C:\Users\njeuk\OneDrive\Documents\GRK\SUBS_OPTITACS\Charm_and_Simulation_scripts\back_up04_02_25\code';

    % --- Fernanda / ID_270 head modelling ---
    wkf_cfg.main_path = 'C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\Fernanda_head_modelling';
    wkf_cfg.output_path = 'C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\Fernanda_head_modelling';
    wkf_cfg.code_path = 'C:\Users\njeuk\OneDrive\Documents\GRK\SUBS_OPTITACS\Charm_and_Simulation_scripts\code';
    
    % Toolboxes: Super important but they aren't call in the main function
    % because they're too heavy! 
    wkf_cfg.fieldtrip_path = 'C:\Users\njeuk\OneDrive\Documents\GRK\fieldtrip-20240110\fieldtrip-20240110';
    wkf_cfg.spm_path = [wkf_cfg.fieldtrip_path 'external/spm12/'];
    wkf_cfg.simnibs_path = 'C:\Users\njeuk\SimNIBS-4.1\simnibs_env\Lib\site-packages\simnibs\matlab_tools';
    
    % Subject parameters: Group (since we do group level); Lesions for
    % patients
    wkf_cfg.subject_group = 'control';  % or 'patient' 
    wkf_cfg.has_lesion = strcmp(wkf_cfg.subject_group, 'patient');
    wkf_cfg.subject_pattern = [wkf_cfg.subject_group '*'];
    
    % Atlas parameters
    wkf_cfg.atlas_path = 'C:\Users\njeuk\OneDrive\Documents\GRK\SUBS_OPTITACS\MNI152_Opt_Montage\MNI152_std_Montage_32c_20_02\BNA_MPM_thr25_1.25mm.nii.gz';
    %wkf_cfg.roi_indices = [177, 178, 179, 180];

    % ===== Define MNI Coordinates for ACC Targeting =====
    % Based on Brainnetome (BNA) for electrode targeting (I think)
    % and corresponds to HCP-MMP1 regions 
    
    wkf_cfg.mni_coords = [  
        -6, 34, 21;  % Left Pregenual ACC (CG-3) → HCP: p32pr, 33pr
         5, 28, 27;  % Right Pregenual ACC (CG-3) 32p → HCP: p32pr, 33pr
        -4, 39, -2;  % Left Subgenual ACC 32 (CG-7) → HCP: a24, d32
         5, 41, 6    % Right Subgenual ACC (CG-7) → HCP: a24, d32
    ];
    
    wkf_cfg.lesion_conductivity = 1.654;



    % wkf_cfg.montage = struct( ...
    % 'positions', {{'Fz', 'F7', 'Fp1', 'Fp2', 'F8'}}, ... % Electrode positions (10)
    % 'currents', [2e-3, -0.5e-3, -0.5e-3, -0.5e-3, -0.5e-3], ... % Current values (A)
    % 'dimensions', 10, ... % Electrode size (mm)
    % 'shape', 'ellipse', ... % Electrode shape
    % 'thickness', 2, ... % Electrode thickness (mm)
    % 'cond_value', 1.654 ... % Lesion conductivity (S/m)

    % Opt_Montage of MNI152
    wkf_cfg.montage = struct( ...
    'positions', {{'F2', 'FT7'}}, ... % as 14.02.25 params opt from MNI152
    'currents', [0.001, -0.001], ... % Updated current values
    'dimensions', 10, ... % Electrode size (mm)
    'shape', 'ellipse', ... % Electrode shape
    'thickness', 2, ... % Electrode thickness (mm)
    'cond_value', 1.654 ... % Lesion conductivity (S/m)
    );

    wkf_cfg.lf_pathfem = 'leadfield'; %folder output of the leadfield compute
    wkf_cfg.lf_EEG_cap = 'EEG10-20_Okamoto_2004.csv';

    % Updated workflow configuration based on the final montage solution; 
    % This is the standard CFM you ajust based on the optimal parameters
    % you  found this will be pass in simNIBS
    wkf_cfg.montage_starstim = struct( ...
    'positions', {{'Cz', 'Fp2', 'Fz', 'F3', 'F4', 'F7', 'F8', 'Fp1', 'C3', 'C4', 'T7', 'T8', ...
                   'Pz', 'P3', 'P4', 'P7', 'P8', 'O1', 'O2'}}, ... 
    'currents', [ -0.000293,      ... % Cz
                   0.000246,      ... % Fp2
                   0.000307,      ... % Fz
                   0.000307,      ... % F3
                   0.000307,      ... % F4
                  -0.000293,      ... % F7
                   0.0,          ... % F8
                   0.000244,      ... % Fp1
                  -0.000293,      ... % C3
                   0.000307,      ... % C4
                   0.0,          ... % T7
                   0.0,          ... % T8
                  -0.000293,      ... % Pz
                  -0.000293,      ... % P3
                   0.0,          ... % P4
                   0.000307,      ... % P7
                  -0.000293,      ... % P8
                   0.0,          ... % O1
                  -0.000267      ... % O2 (adjusted to ensure sum = 0)
    ], ...
        'dimensions', 20, ...       % Electrode size (mm)
        'shape', 'ellipse', ...      % Electrode shape
        'thickness', 2, ...         % Electrode thickness (mm)
        'cond_value', 1.654 ...     % Conductivity (S/m)
    );


end

