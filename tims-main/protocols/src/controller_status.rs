use byteorder::{BigEndian, ByteOrder};
use serde::{Deserialize, Serialize};

use crate::{M, MachineConfig, N, TIMSError, V, W, config};

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct MonitorChannel {
    pub index: usize,
    pub samples: Vec<i16>,
}

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct MonitorData {
    pub channels: [MonitorChannel; M],
}

#[derive(Clone, Copy, PartialEq, Deserialize, Serialize, Debug)]
pub enum ControllerState {
    Idle,
    Active,
    Error(TIMSError),
}

impl Default for ControllerState {
    fn default() -> Self {
        ControllerState::Idle
    }
}

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct ControllerStatus {
    pub idx: u64,
    pub state: ControllerState,
    pub packet_valid: bool,
    pub monitor_data: MonitorData,
    pub session_progress: f64,
    pub flow_rate: Option<Vec<f64>>,
    pub temperature: Option<Vec<f64>>,
    pub supply_current: Option<f64>,
    pub supply_power: Option<f64>,
}

impl MonitorData {
    fn from_buffer(rx_buffer: &[u8]) -> Self {
        let mut channels = core::array::from_fn(|i| MonitorChannel {
            index: i,
            samples: vec![0; N],
        });

        for i in 0..N {
            let w = &rx_buffer[i * W..(i + 1) * W];

            for j in 0..M {
                channels[j].samples[i] = BigEndian::read_i16(&w[j * 2..(j + 1) * 2]);
            }
        }

        MonitorData { channels }
    }
}

impl ControllerStatus {
    pub fn default_and_from_buffer(rx_buffer: &[u8], machine_config: &MachineConfig) -> Self {
        let monitor_data = MonitorData::from_buffer(rx_buffer);

        let mut flow_rate = vec![0.0; machine_config.num_flow_rate_sensors];
        let mut packet_valid = false;

        for c in 0..config::INTERFACE_CONFIG_NUM_WORDS as usize {
            let status_word = &rx_buffer[N * M * 2 + c * W..N * M * 2 + (c + 1) * W];

            if c == 0 {
                // first status word
                if status_word == config::INTERFACE_PACKET_VALID_KEY {
                    packet_valid = true;
                } else {
                    log::error!("Invalid SPI packet validation received: {status_word:?}");
                    packet_valid = false;
                }
            }
            if c == 1 {
                // second status word
                for k in 0..machine_config.num_flow_rate_sensors {
                    let period = 2 * BigEndian::read_u32(&status_word[k * V..(k + 1) * V]) as u64;

                    if period > 0 {
                        let freq = config::FLOW_SENSOR_MEAS_FREQ / period as f64;
                        let lpm = config::FLOW_SENSOR_SLOPE * (freq * 60.0)
                            + config::FLOW_SENSOR_INTERCEPT;
                        flow_rate[k] = lpm / 60.0;
                    } else {
                        flow_rate[k] = 0.0;
                    }
                }
            }
        }

        ControllerStatus {
            monitor_data,
            packet_valid,
            flow_rate: if !flow_rate.is_empty() {
                Some(flow_rate)
            } else {
                None
            },
            ..Default::default()
        }
    }
}
