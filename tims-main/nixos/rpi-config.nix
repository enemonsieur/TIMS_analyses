{ ... }:
{
  hardware.raspberry-pi.config.all = {
    base-dt-params = {
      i2c_arm = {
        enable = true;
        value = "on";
      };
      spi = {
        enable = true;
        value = "on";
      };
    };

    dt-overlays = {
      spi1-2cs = {
        enable = true;
      };
    };
  };

  hardware.raspberry-pi.extra-config = ''
      [all]
      usb_max_current_enable=1
  '';
}
