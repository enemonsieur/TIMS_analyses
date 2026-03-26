{ inputs, globals, ... }:
{
  # NixOS modules
  imports = [
    ./rename-fix.nix
    ./hardware-configuration.nix
    ./system.nix
  ];

  # Home manager modules
  home-manager.users.${globals.username}.imports = [
    inputs.kn-nixos-config.homeModules.devtools
    ./app.nix
  ];
}
