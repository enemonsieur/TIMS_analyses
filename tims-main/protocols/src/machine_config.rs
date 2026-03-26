use serde::{Deserialize, Serialize};

use crate::Coil;

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct MachineConfig {
    pub supply_voltage: f64,
    pub num_coils: usize,
    pub coils: Vec<Coil>,
    pub capacitors: Vec<f64>, // nF
    pub possible_capacitances: Vec<f64>,
    pub num_external_signal_sources: usize,
    pub smbus_psu_connected: bool,
    pub num_temperature_sensors: usize,
    pub num_flow_rate_sensors: usize,
    pub safety_checks_enabled: bool,
    pub max_intensity_setpoint: f64,
    pub max_current: f64,
    pub max_carrier_frequency: f64,
    pub max_temperature: f64,
    pub min_flowrate: f64,
    pub max_power: f64,
}

impl Default for MachineConfig {
    fn default() -> Self {
        Self {
            supply_voltage: 80.0,
            num_coils: 2,
            coils: vec![Coil::default()],
            capacitors: vec![330.0],
            possible_capacitances: vec![330.0],
            num_external_signal_sources: 6,
            smbus_psu_connected: false,
            num_temperature_sensors: 0,
            num_flow_rate_sensors: 0,
            safety_checks_enabled: true,
            max_intensity_setpoint: 0.3,
            max_current: 0.5,
            max_carrier_frequency: 40.0,
            max_temperature: 40.0,
            min_flowrate: 70.0,
            max_power: 520.0,
        }
    }
}
