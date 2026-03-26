(
  { lib, inputs, ... }:
  let
    renamePath = inputs.nixpkgs.outPath + "/nixos/modules/rename.nix";
    renameModule = import renamePath { inherit lib; };
    moduleFilter =
      module:
      lib.attrByPath [ "options" "boot" "loader" "raspberryPi" ] null (module {
        config = null;
        options = null;
      }) == null;
  in
  {
    disabledModules = [ renamePath ];
    imports = builtins.filter moduleFilter renameModule.imports;
  }
)

