# NixOS Module
{ inputs, pkgs, globals, ... }:
{
  environment.sessionVariables.TIMS_TARGET_MACHINE = "1";

  # Boot and kernel configuration
  boot = {
    loader.raspberry-pi.bootloader = "kernel";

    # Real-time kernel
    kernelPatches = [
      {
        name = "realtime-config";
        patch = null;
        extraConfig = ''
          PREEMPT_VOLUNTARY n
          PREEMPT_RT y
          CPU_FREQ_GOV_INTERACTIVE n
          FAIR_GROUP_SCHED n
          CPU_FREQ_TIMES n
        '';
      }
    ];

    kernelParams = [
      "spidev.bufsiz=65536"
    ];
  };

  # Nix settings
  nix = {
    settings = {
      download-buffer-size = 200000000;
      auto-optimise-store = true;
      experimental-features = [
        "nix-command"
        "flakes"
      ];
      trusted-users = [
        "root"
        "${globals.username}"
      ];
    };
  };

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # User configuration
  users = {
    mutableUsers = true;
    users.${globals.username} = {
      uid = globals.userUID;
      isNormalUser = true;
      description = "${globals.userDescription}";
      extraGroups = [
        "wheel"
      ];
      shell = pkgs.fish; # set default shell to fish
      ignoreShellProgramCheck = true;
      initialHashedPassword = "$y$j9T$yLS6u3wFQ6h5VXilLX/iI.$lSmsXhX6dfNV1uMo85TqjlkiWHaiYgP62K45v5d9hFB";
      openssh.authorizedKeys.keys = [
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMHL6+vtrOsjN4WC1PW+/eCBPmXSLUwjvtgakT22/hXk nasrk@yoyo"
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIL+sDL0yYN9ZpprywzEe2FhEoVhxD29ufj4b5MYq5L/A nasrk@toobig"
      ];
    };
  };

  # Auto login
  services.getty.autologinUser = "${globals.username}";

  # Minimal X11 desktop
  services.xserver.enable = true;
  services.xserver.displayManager.lightdm.enable = true;
  services.xserver.displayManager.xserverArgs = [ "-nocursor" "-s 0 dpms" ];
  services.xserver.windowManager.openbox.enable = true;
  services.displayManager.defaultSession = "none+openbox";
  services.displayManager.autoLogin.enable = true;
  services.displayManager.autoLogin.user = "${globals.username}";

  # Allow SSH
  services.openssh = {
    enable = true;
  };

  # Home manager
  imports = [ inputs.home-manager.nixosModules.home-manager ];
  home-manager = {
    useUserPackages = true;
    useGlobalPkgs = true;
    backupFileExtension = "backup";
    users.${globals.username} = {
      home = {
        username = "${globals.username}";
        homeDirectory = "/home/${globals.username}";
        stateVersion = "${globals.stateVersion}";
      };
    };
    extraSpecialArgs = {
      inherit inputs;
      inherit globals;
    };
  };

  system.stateVersion = "${globals.stateVersion}";
}
