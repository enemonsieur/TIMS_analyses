
use std::{error::Error, fmt::Display};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, PartialEq, Deserialize, Serialize, Debug)]
pub enum TIMSError {
    OverCoilCurrent,
    OverSupplyPower,
    OverTemperature,
    Underflow,
    SPIError,
    GPIOError,
    I2cError,
    TCPError,
    ConfigError,
    ProtocolError,
}

impl Display for TIMSError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TIMSError::OverCoilCurrent => write!(f, "Coil current exceeded the maximum allowed current"),
            TIMSError::OverSupplyPower => write!(f, "Supply power exceeded the maximum allowed power"),
            TIMSError::OverTemperature => write!(f, "Coil water temperature exceeded the maximum allowed temperature"),
            TIMSError::Underflow => write!(f, "Water flow rate is below minimum allowed value - ossible flow obstruction"),
            TIMSError::SPIError => write!(f, "SPI communication error"),
            TIMSError::GPIOError => write!(f, "GPIO Error"),
            TIMSError::I2cError => write!(f, "I2c communication error"),
            TIMSError::TCPError => write!(f, "Network (TCP) communication error"),
            TIMSError::ConfigError => write!(f, "Invalid controller or machine configuration"),
            TIMSError::ProtocolError => write!(f, "Invalid stimulation protocol"),
        }
    }
}

impl Error for TIMSError {
}
