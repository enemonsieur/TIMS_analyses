{ pkgs }:
pkgs.rustPlatform.buildRustPackage rec {
  pname = "tims-interface";
  version = "0.1";
  cargoLock.lockFile = ./Cargo.lock;
  src = pkgs.lib.cleanSource ./.;

  preBuild = ''
    python config.py
  '';

  buildInputs = with pkgs; [
    # For Rust interface
    (rust-bin.stable.latest.default.override {
      targets = [ "wasm32-unknown-unknown" ];
    })
    trunk
    wasm-bindgen-cli_0_2_108
    openssl
    openfpgaloader
    alsa-lib

    # For configuration with Python
    python313
    python313Packages.numpy
    python313Packages.scipy
    python313Packages.bitstring
  ];

  nativeBuildInputs = with pkgs; [
    pkg-config
    makeWrapper
    python313
  ];

  libraryInputs = with pkgs; [
    libxkbcommon
    libGL
    xorg.libX11
    xorg.libxcb
    xorg.libXcursor
    xorg.libXrandr
    xorg.libXi
    xorg.xcbutilwm
    xorg.xcbutilimage
    xorg.xcbutil
    xorg.xcbutilkeysyms
    xorg.xcbutilrenderutil
    alsa-lib
    wayland
  ];

  libraryPath = pkgs.lib.makeLibraryPath libraryInputs;

  postInstall = ''
    wrapProgram "$out/bin/tims-interface" --prefix LD_LIBRARY_PATH : "${libraryPath}"
  '';
}
