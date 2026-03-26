# Home Manager Module
{ pkgs, ... }:
{
  home.packages = [ 
    pkgs.openfpgaloader
    # (pkgs.callPackage ../package.nix { })
  ];

  home.file.".config/openbox/autostart".text = ''
    LD_LIBRARY_PATH=${(pkgs.callPackage ../package.nix { }).libraryPath} DISPLAY=:0 /home/tims/tims/target/release/tims-interface &
  '';
}
