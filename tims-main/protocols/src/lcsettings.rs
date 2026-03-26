use serde::{Deserialize, Serialize};
use std::f64::consts::PI;

use crate::{TIMSError, config};

#[derive(Clone, Copy, PartialEq, Deserialize, Serialize, Debug)]
pub struct LCSetting {
    pub capacitance: f64,       // nF
    pub carrier_frequency: f64, // kHz
    pub clk_ticks_per_sample: usize,
    pub capacitor_bank_setting: usize,
}

impl Default for LCSetting {
    fn default() -> Self {
        Self {
            capacitance: 0.0,
            carrier_frequency: config::FPGA_FCLK as f64
                / (config::SAMPLES_PER_CARRIER_PERIOD * config::MIN_CLK_TICKS_PER_SAMPLE) as f64,
            clk_ticks_per_sample: config::MIN_CLK_TICKS_PER_SAMPLE,
            capacitor_bank_setting: 0,
        }
    }
}

impl LCSetting {
    pub fn new(inductance: f64, capacitance: f64, capacitor_bank_setting: usize) -> Self {
        let carrier_frequency_ideal =
            1.0 / (2.0 * PI * f64::sqrt(inductance * 1E-6 * capacitance * 1E-9));

        let clk_ticks_per_sample = f64::round(
            config::FPGA_FCLK as f64
                / (carrier_frequency_ideal * config::SAMPLES_PER_CARRIER_PERIOD as f64),
        ) as usize;

        let carrier_frequency = config::FPGA_FCLK as f64
            / (clk_ticks_per_sample * config::SAMPLES_PER_CARRIER_PERIOD) as f64;

        LCSetting {
            capacitance,
            carrier_frequency: carrier_frequency * 1E-3,
            clk_ticks_per_sample,
            capacitor_bank_setting,
        }
    }
}

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct Coil {
    pub name: String,
    pub inductance: f64, // uH
    pub max_current: f64,
    pub max_carrier_frequency: f64, // kHz
    pub settings: Vec<LCSetting>,
}

impl Coil {
    pub fn new(
        name: String,
        inductance: f64,
        max_current: f64,
        max_carrier_frequency: f64,
        possible_capacitances: &Vec<f64>,
    ) -> Result<Self, TIMSError> {
        let mut settings: Vec<LCSetting> = (0..possible_capacitances.len())
            .map(|i| LCSetting::new(inductance, possible_capacitances[i], i+1))
            .filter(|s| s.carrier_frequency <= max_carrier_frequency)
            .collect();

        settings.sort_by_key(|setting| setting.clk_ticks_per_sample);
        settings.reverse();

        if settings.is_empty() {
            log::error!("No valid carrier frequency can be calculated for coil {name}");
            Err(TIMSError::ConfigError)
        } else {
            Ok(Coil {
                name,
                inductance,
                max_current,
                max_carrier_frequency,
                settings,
            })
        }
    }
}

impl Default for Coil {
    fn default() -> Self {
        Coil::new("Default".to_string(), 150.0, 0.1, 40.0, &vec![330.0]).unwrap()
    }
}
