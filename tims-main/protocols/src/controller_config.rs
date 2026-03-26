use byteorder::{BigEndian, ByteOrder};
use serde::{Deserialize, Serialize};

use crate::{C, LCSetting, M, N, V, W, config};

#[derive(Clone, Copy, PartialEq, Deserialize, Serialize, Debug)]
pub enum SignalSource {
    Internal(usize),
    External(usize),
}

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct ControllerConfig {
    pub system_enabled: bool,
    pub controller_enabled_a: bool,
    pub controller_enabled_b: bool,
    pub play_protocol: bool,
    pub lc_setting_a: LCSetting,
    pub lc_setting_b: LCSetting,
    pub p_factor: f64,
    pub i_factor: f64,
    pub intensity_a1: f64,
    pub intensity_a2: f64,
    pub intensity_b1: f64,
    pub intensity_b2: f64,
    pub amplitude_a1_source: SignalSource,
    pub amplitude_a2_source: SignalSource,
    pub amplitude_b1_source: SignalSource,
    pub amplitude_b2_source: SignalSource,
    pub modulation_a_source: SignalSource,
    pub modulation_b_source: SignalSource,
}

impl Default for ControllerConfig {
    fn default() -> Self {
        ControllerConfig {
            system_enabled: true,
            controller_enabled_a: false,
            controller_enabled_b: false,
            play_protocol: false,
            lc_setting_a: LCSetting::default(),
            lc_setting_b: LCSetting::default(),
            p_factor: 0.0,
            i_factor: 0.0,
            intensity_a1: 0.0,
            intensity_a2: 0.0,
            intensity_b1: 0.0,
            intensity_b2: 0.0,
            amplitude_a1_source: SignalSource::default(),
            amplitude_a2_source: SignalSource::default(),
            amplitude_b1_source: SignalSource::default(),
            amplitude_b2_source: SignalSource::default(),
            modulation_a_source: SignalSource::default(),
            modulation_b_source: SignalSource::default(),
        }
    }
}

impl Default for SignalSource {
    fn default() -> Self {
        SignalSource::Internal(0)
    }
}

impl SignalSource {
    pub fn to_mux_control(&self) -> usize {
        match self {
            SignalSource::Internal(_) => 0,
            SignalSource::External(ch) => match ch {
                0..6 => *ch,
                _ => 0,
            },
        }
    }

    pub fn to_string(&self) -> String {
        match self {
            SignalSource::Internal(i) => format!("Internal S{i}"),
            SignalSource::External(i) => format!("External A{i}"),
        }
    }
}

impl ControllerConfig {
    pub fn to_buffer(&self, tx_buffer: &mut [u8]) {
        for c in 0..C {
            let config_word = &mut tx_buffer[N * M * 2 + c * W..N * M * 2 + (c + 1) * W];

            if c == 0 {
                // First configuration word must be the data valid key
                for k in 0..W {
                    config_word[k] = config::INTERFACE_PACKET_VALID_KEY[k];
                }
            }

            if c == 1 {
                // Enable bits
                // let enable = self.system_enabled << config::SYSTEM_ENABLE_BIT)
                let mut enable: usize = 0;
                if self.system_enabled {
                    enable |= 1 << config::SYSTEM_ENABLE_BIT;
                }
                if self.controller_enabled_a {
                    enable |= 1 << config::CHA_CONTROLLER_ENABLE_BIT;
                }
                if self.controller_enabled_b {
                    enable |= 1 << config::CHB_CONTROLLER_ENABLE_BIT;
                }

                // Second configuration word
                let vals = [
                    enable, // rst
                    self.lc_setting_a.clk_ticks_per_sample,
                    self.lc_setting_b.clk_ticks_per_sample,
                    ((1 << (config::FP_NBITS + config::FP_EXTRA_BITS))
                        / (self.lc_setting_a.clk_ticks_per_sample as usize
                            * config::SAMPLES_PER_CARRIER_PERIOD)), // phase_step1
                    ((1 << (config::FP_NBITS + config::FP_EXTRA_BITS))
                        / (self.lc_setting_b.clk_ticks_per_sample as usize
                            * config::SAMPLES_PER_CARRIER_PERIOD)), // phase_step2
                    (self.p_factor * (1 << config::PI_CONTROLLER_PARAM_FRACTION_BITS) as f64)
                        as usize,
                    (self.i_factor * (1 << config::PI_CONTROLLER_PARAM_FRACTION_BITS) as f64)
                        as usize,
                ];

                for k in 0..vals.len() {
                    BigEndian::write_u32(&mut config_word[k * V..(k + 1) * V], vals[k] as u32);
                }
            }
            if c == 2 {
                // Third config word
                let vals = [
                    (self.intensity_a1 * config::FP_MAX as f64) as isize,
                    (self.intensity_a2 * config::FP_MAX as f64) as isize,
                    (self.intensity_b1 * config::FP_MAX as f64) as isize,
                    (self.intensity_b2 * config::FP_MAX as f64) as isize,
                ];

                for k in 0..vals.len() {
                    BigEndian::write_u32(&mut config_word[k * V..(k + 1) * V], vals[k] as u32);
                }
            }

            if c == 3 {
                // Fourth config word
                let vals = [
                    self.amplitude_a1_source,
                    self.amplitude_a2_source,
                    self.amplitude_b1_source,
                    self.amplitude_b2_source,
                    self.modulation_a_source,
                    self.modulation_b_source,
                ];

                for k in 0..vals.len() {
                    BigEndian::write_u32(
                        &mut config_word[k * V..(k + 1) * V],
                        vals[k].to_mux_control() as u32,
                    );
                }
            }
        }
    }
}
