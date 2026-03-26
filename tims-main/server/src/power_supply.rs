use std::error;

use protocols::config;
use rppal::i2c::I2c;

type Result<T> = std::result::Result<T, Box<dyn error::Error>>;

pub struct PowerSupply {
    bus: I2c,
}

impl PowerSupply {
    pub fn new() -> Result<Self> {
        let mut bus = I2c::new()?;
        bus.set_slave_address(config::SMBUS_PSU_ADDRESS as u16)?;
        Ok(PowerSupply { bus })
    }

    pub fn read_current_and_power(&mut self) -> Result<(f64, f64)> {
        let current = PowerSupply::linear11_to_f64(
            self.bus
                .smbus_read_word(config::SMBUS_PSU_CURRENT_READ_CMD as u8)?,
        );

        let power = PowerSupply::linear11_to_f64(
            self.bus
                .smbus_read_word(config::SMBUS_PSU_POWER_READ_CMD as u8)?,
        );

        Ok((current, power))
    }

    fn linear11_to_f64(raw: u16) -> f64 {
        // Extract the exponent (bits 15–11)
        let exp_raw = ((raw >> 11) & 0x1F) as i8;
        // Sign-extend the 5-bit exponent to 8-bit signed
        let exponent = if exp_raw & 0x10 != 0 {
            exp_raw | !0x1F // negative number
        } else {
            exp_raw
        };

        // Extract the mantissa (bits 10–0)
        let man_raw = (raw & 0x7FF) as i16;
        // Sign-extend the 11-bit mantissa to 16-bit signed
        let mantissa = if man_raw & 0x400 != 0 {
            man_raw | !0x7FF // negative number
        } else {
            man_raw
        };

        // Convert to floating-point value
        (mantissa as f64) * 2f64.powi(exponent as i32)
    }
}
