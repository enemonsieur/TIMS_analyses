function exists = results_exist(output_path, subject_id, type, doc)
    % Set default value for 'doc' if not provided
    if nargin < 4
        doc = ''; % Default to an empty string or some meaningful default
    end
    search_paths = struct(...
        'simulation', fullfile(output_path, subject_id, 'ACC_Opt*.msh'), ...
        'leadfield', fullfile(output_path, subject_id, doc, '*.hdf5'), ...
        'montage', fullfile(output_path, subject_id, 'opt_CFM*.csv') ...
    );

    % Validate input type
    if ~isfield(search_paths, type)
        error('Invalid type: Use "simulation", "leadfield", or "montage".');
    end

    % Check if files exist
    exists = ~isempty(dir(search_paths.(type)));
end


