# Settings that can vary from machine to machine
{ lib, ... }:
{
  environment.sessionVariables = {
    TIMS_SUPPLY_VOLTAGE = lib.mkDefault "80";
    TIMS_NUM_COILS = lib.mkDefault "2";
    TIMS_CAPACITORS = lib.mkDefault "100 150 220 330"; # nF
    TIMS_NUM_EXTERNAL_SIGNAL_SOURCES = lib.mkDefault "6";
    TIMS_SMBUS_PSU_CONNECTED = lib.mkDefault "true";
    TIMS_NUM_TEMPERATURE_SENSORS = lib.mkDefault "16";
    TIMS_NUM_FLOW_RATE_SENSORS = lib.mkDefault "0";
    TIMS_SAFETY_CHECKS_ENABLED = lib.mkDefault "true";
    TIMS_MAX_INTENSITY_SETPOINT = lib.mkDefault "0.3";
    TIMS_MAX_CARRIER_FREQUENCY = lib.mkDefault "35"; # kHz
    TIMS_MAX_CURRENT = lib.mkDefault "0.5";
    TIMS_MAX_TEMPERATURE = lib.mkDefault "32";
    TIMS_MIN_FLOW_RATE = lib.mkDefault "70";
    TIMS_MAX_POWER = lib.mkDefault "520";
  };

  networking = {
    hostName = lib.mkDefault "tims";
    firewall.enable = true;
    firewall.allowedTCPPorts = [ 8080 ];

    interfaces."end0" = {
      useDHCP = lib.mkDefault false;
      ipv4.addresses = [
        {
          address = lib.mkDefault "192.168.14.5";
          prefixLength = lib.mkDefault 24;
        }
      ];
    };

    # defaultGateway = {
    #   address = lib.mkDefault "192.168.14.1";
    #   interface = lib.mkDefault "end0";
    # };

    nameservers = lib.mkDefault [ "8.8.8.8" ];
  };

  # Time zone and internationalisation properties
  time.timeZone = lib.mkDefault "Europe/Berlin";
  i18n.defaultLocale = lib.mkDefault "en_US.UTF-8";

  # Keyboard layouts
  console.keyMap = lib.mkDefault "de";
  services.xserver.xkb = {
    layout = lib.mkDefault "de";
    variant = lib.mkDefault "";
  };
}
