use rppal::i2c::I2c;

use crate::config;

const PSU_ADDRESS: u16 = 0x5f;

pub struct PowerSupply {
    bus: Option<I2c>,
}

impl PowerSupply {
    pub fn new() -> Self {
        if config::SMBUS_PSU_CONNECTED == 1 {
            let mut bus = I2c::new().unwrap();
            bus.set_slave_address(PSU_ADDRESS).unwrap();
            PowerSupply { bus: Some(bus) }
        } else {
            PowerSupply { bus: None }
        }
    }

    pub fn read_current(&mut self) -> f64 {
        if let Some(bus) = &self.bus {
            PowerSupply::linear11_to_f64(bus.smbus_read_word(0x8C).unwrap())
        } else {
            f64::NAN
        }
    }

    pub fn read_power(&mut self) -> f64 {
        if let Some(bus) = &self.bus {
            PowerSupply::linear11_to_f64(bus.smbus_read_word(0x96).unwrap())
        } else {
            f64::NAN
        }
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
