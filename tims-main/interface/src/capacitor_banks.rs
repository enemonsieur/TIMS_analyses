use crate::config;
use rppal::i2c::I2c;
use std::thread;
use std::time::Duration;

const N: usize = 4;
const ADDRESSES: [u16; N] = [0x26, 0x25, 0x24, 0x23];

const IODIRA: u8 = 0x00;
const OLATA: u8 = 0x14;

const RELAY_PULSE_DURATION: u64 = 400;

pub struct CapacitorBanks {
    buses: [Option<I2c>; N],
}

impl CapacitorBanks {
    pub fn new() -> Self {
        CapacitorBanks {
            buses: core::array::from_fn(|i| {
                if i < config::NUM_CAPACITOR_BANKS as usize {
                    let mut bus = I2c::new().unwrap();
                    bus.set_slave_address(ADDRESSES[i]).unwrap();
                    bus.block_write(IODIRA, &[0x00]).unwrap();
                    Some(bus)
                } else {
                    None
                }
            }),
        }
    }

    pub fn set(&mut self, values: &[usize; N]) {
        for ch in 0..values.len() {
            if let Some(bus) = &self.buses[ch] {
                let mut pin_states: u8 = 0;

                for cap_index in 0..config::AVAILABLE_CAPACITANCES.len() {
                    if (values[ch] >> cap_index & 1) == 1 {
                        pin_states = pin_states | (0b10 << (cap_index * 2));
                    } else {
                        pin_states = pin_states | (0b01 << (cap_index * 2));
                    }
                }
                bus.block_write(OLATA, &[pin_states]).unwrap();
                thread::sleep(Duration::from_millis(RELAY_PULSE_DURATION));
                bus.block_write(OLATA, &[0x00]).unwrap();
            }
        }
    }
}
