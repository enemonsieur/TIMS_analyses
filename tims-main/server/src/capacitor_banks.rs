use protocols::{LCSetting, config};
use rppal::i2c::I2c;
use std::time::Duration;
use std::{error, thread};

use config::CAPACITOR_BANK_ADDRESSES as ADDRESSES;
use config::CAPACITOR_BANK_IODIRA as IODIRA;
use config::CAPACITOR_BANK_OLATA as OLATA;
use config::CAPACITOR_BANK_RELAY_PULSE_DURATION as DELAY_MS;

type Result<T> = std::result::Result<T, Box<dyn error::Error>>;

#[derive(Default)]
pub struct CapacitorBanks {
    buses: Vec<I2c>,
    num_capacitors: usize,
}

impl CapacitorBanks {
    pub fn new(num_banks: usize, num_capacitors: usize) -> Result<Self> {
        assert!(num_banks >= 1);
        assert!(num_capacitors >= 1);

        Ok(CapacitorBanks {
            buses: if num_capacitors > 1 {
                // more than one capacitor per coil is available
                // use i2c to switch between them to get different capacitances
                // one i2c bus per coil
                let mut buses: Vec<I2c> = Vec::new();
                for i in 0..num_banks {
                    let mut bus = I2c::new()?;
                    bus.set_slave_address(ADDRESSES[i])?;
                    bus.block_write(IODIRA as u8, &[0x00])?;
                    buses.push(bus);
                }
                buses
            } else {
                // one capacitor per coil; no i2c buses needed
                Vec::new()
            },
            num_capacitors,
        })
    }

    pub fn set(&mut self, setting_a: LCSetting, setting_b: LCSetting) -> Result<()> {
        if self.num_capacitors > 1 {
            // if more than one capacitor is available, use i2c to switch
            // between to realize the desired setting
            for ch in 0..self.buses.len() {
                let setting = if ch < 2 { &setting_a } else { &setting_b };

                let mut pin_states: u8 = 0;

                for cap_index in 0..self.num_capacitors {
                    if (setting.capacitor_bank_setting >> cap_index & 1) == 1 {
                        pin_states = pin_states | (0b10 << (cap_index * 2));
                    } else {
                        pin_states = pin_states | (0b01 << (cap_index * 2));
                    }
                }
                self.buses[ch].block_write(OLATA as u8, &[pin_states])?;
                thread::sleep(Duration::from_millis(DELAY_MS as u64));
                self.buses[ch].block_write(OLATA as u8, &[0x00])?;
            }
        }

        Ok(())
    }
}
