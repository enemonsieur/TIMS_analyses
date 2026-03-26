use std::env;
use std::str::FromStr;

use protocols::{Coil, MachineConfig, TIMSError};

pub fn from_environment() -> Result<MachineConfig, TIMSError> {
    let capacitors: Vec<f64> = parse_list("TIMS_CAPACITORS")?;
    let possible_capacitances: Vec<f64> = (1..(1 << capacitors.len()))
        .map(|i| {
            // index encodes capacitor bank setting
            // individual bits in index indicate whether the corresponding
            // capacitor is added to the parallel combination that forms
            // the total capacitance
            let mut capacitance = 0.0;
            for j in 0..capacitors.len() {
                capacitance += capacitors[j] * ((i >> j & 1) as f64);
            }
            capacitance
        })
        .collect();

    let max_carrier_frequency: f64 = parse("TIMS_MAX_CARRIER_FREQUENCY")?;
    let coils = parse_coils("TIMS_COIL", &possible_capacitances, max_carrier_frequency)?;

    if coils.is_empty() {
        log::error!(
            "No coil definitions found in machine configuration environment variables. Please add at least one coil"
        );
        return Err(TIMSError::ConfigError);
    }

    Ok(MachineConfig {
        supply_voltage: parse("TIMS_SUPPLY_VOLTAGE")?,
        num_coils: parse("TIMS_NUM_COILS")?,
        coils,
        capacitors,
        possible_capacitances,
        num_external_signal_sources: parse("TIMS_NUM_EXTERNAL_SIGNAL_SOURCES")?,
        smbus_psu_connected: parse("TIMS_SMBUS_PSU_CONNECTED")?,
        num_temperature_sensors: parse("TIMS_NUM_TEMPERATURE_SENSORS")?,
        num_flow_rate_sensors: parse("TIMS_NUM_FLOW_RATE_SENSORS")?,
        safety_checks_enabled: parse("TIMS_SAFETY_CHECKS_ENABLED")?,
        max_intensity_setpoint: parse("TIMS_MAX_INTENSITY_SETPOINT")?,
        max_current: parse("TIMS_MAX_CURRENT")?,
        max_carrier_frequency,
        max_temperature: parse("TIMS_MAX_TEMPERATURE")?,
        min_flowrate: parse("TIMS_MIN_FLOW_RATE")?,
        max_power: parse("TIMS_MAX_POWER")?,
    })
}

fn parse<T>(key: &str) -> Result<T, TIMSError>
where
    T: FromStr,
    T::Err: std::fmt::Debug,
    <T as FromStr>::Err: std::fmt::Display,
{
    let val = env::var(key).map_err(|e| {
        log::error!("Required machine configuration environment {key} variable not found: {e}");
        TIMSError::ConfigError
    })?;

    Ok(val.parse::<T>().map_err(|e| {
        log::error!(
            "Invalid value for machine configuration environment variable {key}={val}: {e}"
        );
        TIMSError::ConfigError
    })?)
}

fn parse_list<T>(key: &str) -> Result<Vec<T>, TIMSError>
where
    T: FromStr,
    T::Err: std::fmt::Debug,
    <T as FromStr>::Err: std::fmt::Display,
{
    let val: String = parse(key)?;

    val.split(" ")
        .map(|s| {
            s.parse::<T>().map_err(|e| {
                log::error!(
                    "Invalid value for list element {s} in machine configuration environment variable {key}={val}: {e}"
                );
                TIMSError::ConfigError
            })
        })
        .collect()
}

fn parse_coils(
    key_start: &str,
    possible_capacitances: &Vec<f64>,
    machine_max_carrier_frequency: f64,
) -> Result<Vec<Coil>, TIMSError> {
    let mut valid_coils: Vec<Coil> = Vec::new();

    for coil in env::vars()
        .filter(|(key, _)| key.starts_with(key_start))
        .map(|(key, val)| {
            let vals: Vec<f64> = parse_list(&key)?;

            if vals.len() != 3 {
                log::error!("Invalid value for machine configuration environment variable {key}={val}");
                log::error!("Coil specifictaion must contain 3 elements: inducance, maximum current, and maximum carrier freqeuncy");
                Err(TIMSError::ConfigError)
            } else {
                Coil::new(
                    key.split("_").last().ok_or(TIMSError::ConfigError)?.to_string(),
                    vals[0],
                    vals[1],
                    f64::min(vals[2], machine_max_carrier_frequency),
                    possible_capacitances,
                )
            }
        }).into_iter()
    {
        match coil {
            Ok(coil) => { valid_coils.push(coil); },
            Err(e) => {
                log::error!("Error loading while loading a coil from machine configuration {e}");
                log::error!("Skipping that coil");
            }
        }
    }

    Ok(valid_coils)
}
