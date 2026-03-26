{
  description = "TIMS NixOS configuration and development environment";

  inputs = {
    # For NixOS configuration
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixos-raspberrypi = {
      url = "github:nvmd/nixos-raspberrypi/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Rust
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # For development shell
    nixvim.url = "github:nix-community/nixvim/nixos-25.11";
    nixvim.inputs.nixpkgs.follows = "nixpkgs";
    kn-nixos-config.url = "github:khalednasr/nixos-config";
    kn-nixos-config.inputs.nixpkgs.follows = "nixpkgs";
  };

  nixConfig = {
    extra-substituters = [
      "https://nixos-raspberrypi.cachix.org"
    ];
    extra-trusted-public-keys = [
      "nixos-raspberrypi.cachix.org-1:4iMO9LXa8BqhU+Rpg6LQKiGa2lsNh/j2oiYLNOQ5sPI="
    ];
  };

  outputs =
    { nixpkgs, ... }@inputs:
    let
      # Supported systems for project development
      allSystems = [
        "x86_64-linux" # 64-bit Intel/AMD Linux
        "aarch64-linux" # 64-bit ARM Linux
        "x86_64-darwin" # 64-bit Intel macOS
        "aarch64-darwin" # 64-bit ARM macOS
      ];

      # Helper to provide system-specific attributes
      forAllSystems =
        f:
        nixpkgs.lib.genAttrs allSystems (
          system:
          f {
            pkgs = import nixpkgs {
              inherit system;
              config.allowUnfree = true;
              overlays = [ inputs.rust-overlay.overlays.default ];
            };
          }
        );

      # NixOS configuration for target system
      mkNixOSConfig =
        machine:
        inputs.nixos-raspberrypi.lib.nixosSystem {
          specialArgs = {
            inherit inputs;
            nixos-raspberrypi = inputs.nixos-raspberrypi;
            globals = import ./nixos/globals.nix;
          };

          modules = [
            ./nixos
            ./nixos/machines/${machine}.nix
            inputs.nixos-raspberrypi.nixosModules.sd-image
          ];
        };

      mkInstallerImage = machine: (mkNixOSConfig machine).config.system.build.sdImage;

      # list of all module names in ./nixos/machines/
      machines = builtins.map (name: builtins.substring 0 ((builtins.stringLength name) - 4) name) (
        builtins.filter (name: builtins.match ".*\\.nix" name != null) (
          builtins.attrNames (builtins.readDir ./nixos/machines)
        )
      );
    in
    {
      # Output for generating a new SD card image
      installerImages = builtins.listToAttrs (
        map (machine: {
          name = machine;
          value = mkInstallerImage machine;
        }) machines
      );

      # For rebuilding existing system using nixos-rebuild
      nixosConfigurations = builtins.listToAttrs (
        map (machine: {
          name = machine;
          value = mkNixOSConfig machine;
        }) machines
      );

      devShells = forAllSystems (
        { pkgs }:
        {
          targetMachine = pkgs.mkShell {
            inputsFrom = [ (pkgs.callPackage ./package.nix { }) ];
            LD_LIBRARY_PATH = (pkgs.callPackage ./package.nix { }).libraryPath;
            shellHook = "python config.py";
            DISPLAY = ":0";
          };

          developmentMachine = pkgs.mkShell {
            inputsFrom = [ (pkgs.callPackage ./package.nix { }) ];
            LD_LIBRARY_PATH = (pkgs.callPackage ./package.nix { }).libraryPath;
            shellHook = "python config.py";

            packages = with pkgs; [
              # Rust formatting
              rustfmt

              # Python testing
              python313Packages.pytest
              python313Packages.cocotb
              python313Packages.matplotlib
              python313Packages.pyside6

              # FPGA development
              verilator
              zlib
              gtkwave

              # STM32
              gcc-arm-embedded
              cmake
              openocd
              dfu-util
              stm32cubemx

              # Circuit design
              ngspice
              kicad
            ];

            # For STM32CubeMX to display well on tiling window managers
            _JAVA_AWT_WM_NONREPARENTING = 1;
          };
        }
      );

      packages = forAllSystems (
        { pkgs }:
        {
          default = pkgs.callPackage ./package.nix { };
        }
      );
    };
}
