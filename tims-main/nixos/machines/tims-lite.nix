{ globals, ... }:
{
  imports = [ ./default.nix ];

  networking.hostName = "tims-lite";
  networking.networkmanager.enable = true;
  users.users.${globals.username}.extraGroups = [ "networkmanager" ];

  environment.sessionVariables = {
    TIMS_SUPPLY_VOLTAGE = "48";
    TIMS_NUM_COILS = "1";
    TIMS_CAPACITORS = "470";
    TIMS_NUM_EXTERNAL_SIGNAL_SOURCES = "0";
    TIMS_SMBUS_PSU_CONNECTED = "false";
    TIMS_NUM_TEMPERATURE_SENSORS ="0";
    TIMS_NUM_FLOW_RATE_SENSORS = "0";
    TIMS_SAFETY_CHECKS_ENABLED = "true";
    TIMS_MAX_INTENSITY_SETPOINT = "0.15";
    TIMS_MAX_CARRIER_FREQUENCY = "35";
    TIMS_MAX_CURRENT = "0.5";
    TIMS_MAX_TEMPERATURE = "32";
    TIMS_MIN_FLOW_RATE = "70";
    TIMS_MAX_POWER = "520";
    TIMS_COIL_L53 = "53 0.3 38"; # inductance in uH, max_current, max carrier freq in kHz
  };
}
