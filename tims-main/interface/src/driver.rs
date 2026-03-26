// use circular_buffer::CircularBuffer;
use crate::{config, power_supply};
use crate::protocol::Protocol;
use crate::temperature_sensors;
use byteorder::{BigEndian, ByteOrder};
use rppal::gpio::Gpio;
use rppal::spi::{Bus, Mode, SlaveSelect, Spi};
use std::sync::mpsc::{Receiver, channel};
use std::sync::{Arc, Mutex};
use std::thread;

// SPI packet parameter shorthands
// Number of bytes in a word
const W: usize = (config::INTERFACE_WORD_NBITS / 8) as usize;
// Number of setpoint/monitor samples per packet
const N: usize = config::INTERFACE_DATA_NUM_SAMPLES as usize;
// Number of setpoint/monitor channels
const M: usize = config::INTERFACE_DATA_NUM_CHANNELS as usize;
// Number of configuration words
const C: usize = config::INTERFACE_CONFIG_NUM_WORDS as usize;
// Number of bytes in each configuration parameters
const V: usize = (config::INTERFACE_CONFIG_BIT_ALIGNMENT / 8) as usize;
// Total number of bytes in a packet
const PACKET_NBYTES: usize = config::INTERFACE_PACKET_NBYTES as usize;

// GPIO Pins
const GPIO_TRIG: u8 = 27;

// Flow sensor calibration
// flow_rate_lpm = slope * rpm + intercept
pub const NUM_FLOW_RATE_SENSORS: usize = 4;
const FLOW_SENSOR_SLOPE: f64 = 5.5021;
const FLOW_SENSOR_INTERCEPT: f64 = 57.425;
const FLOW_SENSOR_MEAS_FREQ: f64 =
    config::FPGA_FCLK as f64 / config::FLOW_SENSOR_CLK_DIVIDER as f64;

#[derive(Clone, Copy, PartialEq, serde::Deserialize, serde::Serialize, Debug)]
pub enum StimulationMode {
    TI,
    AM,
}

#[derive(Clone, Copy, PartialEq, serde::Deserialize, serde::Serialize, Debug)]
pub enum SignalSource {
    Internal,
    External,
}

#[derive(Clone, Copy, PartialEq, Debug)]
pub struct DriverConfig {
    pub system_enabled: bool,
    pub controller_enabled_a: bool,
    pub controller_enabled_b: bool,
    pub play_protocol: bool,
    pub stimulation_mode: StimulationMode,
    pub amplitude_signal_source: SignalSource,
    pub external_ampitude_equal_currents: bool,
    pub modulation_signal_source: SignalSource,
    pub clk_ticks_per_sample_a: usize,
    pub clk_ticks_per_sample_b: usize,
    pub p_factor: f64,
    pub i_factor: f64,
    pub power_a1: f64,
    pub power_a2: f64,
    pub power_b1: f64,
    pub power_b2: f64,
}

impl Default for DriverConfig {
    fn default() -> Self {
        DriverConfig {
            system_enabled: true,
            controller_enabled_a: false,
            controller_enabled_b: false,
            play_protocol: false,
            stimulation_mode: StimulationMode::TI,
            amplitude_signal_source: SignalSource::Internal,
            external_ampitude_equal_currents: false,
            modulation_signal_source: SignalSource::Internal,
            clk_ticks_per_sample_a: config::MIN_CLK_TICKS_PER_SAMPLE,
            clk_ticks_per_sample_b: config::MIN_CLK_TICKS_PER_SAMPLE,
            p_factor: 0.0,
            i_factor: 0.0,
            power_a1: 0.0,
            power_a2: 0.0,
            power_b1: 0.0,
            power_b2: 0.0,
        }
    }
}

pub struct DriverStatus {
    pub monitor_channels: [[f32; N]; M],
    pub session_progress: f64,
    pub flow_rate: [f64; NUM_FLOW_RATE_SENSORS],
    pub temperature: [f64; temperature_sensors::NUM_SENSORS],
    pub supply_current: f64,
    pub supply_power: f64,
}

impl DriverStatus {
    fn from_buffer(rx_buffer: &[u8]) -> Self {
        const Q: f32 = config::FP_MAX as f32;

        let mut monitor_channels: [[f32; N]; M] = [[0.0; N]; M];

        for i in 0..N {
            let w = &rx_buffer[i * W..(i + 1) * W];

            for j in 0..M {
                let val = BigEndian::read_i16(&w[j * 2..(j + 1) * 2]) as f32 / Q;
                monitor_channels[j][i] = val;
            }
        }

        let mut flow_rate: [f64; NUM_FLOW_RATE_SENSORS] = [0.0; NUM_FLOW_RATE_SENSORS];

        for c in 0..config::INTERFACE_CONFIG_NUM_WORDS as usize {
            let status_word = &rx_buffer[N * M * 2 + c * W..N * M * 2 + (c + 1) * W];

            if c == 0 {
                // first status word
                assert_eq!(status_word, config::INTERFACE_PACKET_VALID_KEY);
            }
            if c == 1 {
                // second status word
                for k in 0..4 {
                    let period = 2 * BigEndian::read_u32(&status_word[k * V..(k + 1) * V]) as u64;

                    if period > 0 {
                        let freq = FLOW_SENSOR_MEAS_FREQ / period as f64;
                        let lpm = FLOW_SENSOR_SLOPE * (freq * 60.0) + FLOW_SENSOR_INTERCEPT;
                        flow_rate[k] = lpm / 60.0;
                    } else {
                        flow_rate[k] = 0.0;
                    }
                }
            }
        }

        DriverStatus {
            monitor_channels,
            session_progress: 0.0,
            flow_rate: flow_rate,
            temperature: [0.0; temperature_sensors::NUM_SENSORS],
            supply_current: 0.0,
            supply_power: 0.0,
        }
    }
}

pub struct Driver {
    config: Arc<Mutex<DriverConfig>>,
    protocol: Arc<Mutex<Protocol>>,
    pub status_receiver: Receiver<DriverStatus>,
}

impl Driver {
    pub fn new() -> Self {
        let (status_sender, status_receiver) = channel();

        let driver = Driver {
            config: Arc::new(Mutex::new(DriverConfig::default())),
            protocol: Arc::new(Mutex::new(Protocol::default())),
            status_receiver,
        };

        let driver_config = driver.config.clone();
        let protocol = driver.protocol.clone();

        if config::DRIVER_CONNECTED == 1 {
            thread::spawn(move || {
                let gpio = Gpio::new().unwrap();
                let spi = Spi::new(
                    Bus::Spi0,
                    SlaveSelect::Ss0,
                    config::INTERFACE_SPI_FREQ as u32,
                    Mode::Mode1,
                )
                .unwrap();

                let mut temp_sensors = temperature_sensors::TemperatureSensors::new();

                let mut psu = power_supply::PowerSupply::new();

                let mut rx_buffer: [u8; PACKET_NBYTES] = [0; PACKET_NBYTES];
                let mut tx_buffer: [u8; PACKET_NBYTES] = [0; PACKET_NBYTES];

                let trig_pin = gpio.get(GPIO_TRIG).unwrap().into_input();

                let mut session_progress = 0.0;

                let mut trig_prev = false;
                loop {
                    let trig = trig_pin.is_high();

                    if trig && !trig_prev {
                        // let now = std::time::Instant::now();

                        // Grab the configuration
                        let dconf = &driver_config.lock().unwrap().clone();

                        // FPGA ready for data transfer
                        // prepare data packet for sending the the FPGA
                        if dconf.play_protocol {
                            session_progress =
                                protocol.lock().unwrap().fill_data_buffer(&mut tx_buffer);
                        } else {
                            for i in 0..tx_buffer.len() {
                                tx_buffer[i] = 0;
                            }
                        }

                        // write configuration words into tx buffer
                        Driver::write_configuration(&dconf, &mut tx_buffer);

                        // Exchange data with FPGA
                        spi.transfer(&mut rx_buffer, &tx_buffer).unwrap();

                        // Read temperatures
                        temp_sensors.read();


                        let mut status = DriverStatus::from_buffer(&rx_buffer);
                        status.session_progress = session_progress;
                        status.temperature = temp_sensors.temperature.clone();
                        status.supply_current = psu.read_current();
                        status.supply_power = psu.read_power();
                        status_sender.send(status).unwrap();

                        // let elapsed = now.elapsed();
                        // println!("Loop time = {:.2?}", elapsed);
                    }
                    trig_prev = trig;
                }
            });
        }
        return driver;
    }

    pub fn set_config(&mut self, driver_config: DriverConfig) {
        *self.config.lock().unwrap() = driver_config;
    }

    pub fn set_protocol(&mut self, protocol: Protocol) {
        *self.protocol.lock().unwrap() = protocol;
    }

    fn write_configuration(fpga_config: &DriverConfig, tx_buffer: &mut [u8]) {
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
                // let enable = fpga_config.system_enabled << config::SYSTEM_ENABLE_BIT)
                let mut enable: usize = 0;
                if fpga_config.system_enabled {
                    enable |= 1 << config::SYSTEM_ENABLE_BIT;
                }
                if fpga_config.controller_enabled_a {
                    enable |= 1 << config::CHA_CONTROLLER_ENABLE_BIT;
                }
                if fpga_config.controller_enabled_b {
                    enable |= 1 << config::CHB_CONTROLLER_ENABLE_BIT;
                }

                let mut mode: usize = 0;
                if fpga_config.stimulation_mode == StimulationMode::TI {
                    mode |= 1 << config::MODE_AM_VS_TI_BIT;
                }
                if fpga_config.amplitude_signal_source == SignalSource::External {
                    mode |= 1 << config::MODE_AMPLITUDE_SETPOINT_INT_VS_EXT_BIT;
                }
                if fpga_config.modulation_signal_source == SignalSource::External {
                    mode |= 1 << config::MODE_MODULATION_SETPOINT_INT_VS_EXT_BIT;
                }
                if fpga_config.external_ampitude_equal_currents {
                    mode |= 1 << config::MODE_EXT_AMPLITUDE_EQUAL_CURRENTS_BIT;
                }

                // Second configuration word
                let vals = [
                    enable, // rst
                    mode,
                    fpga_config.clk_ticks_per_sample_a,
                    fpga_config.clk_ticks_per_sample_b,
                    ((1 << (config::FP_NBITS + config::FP_EXTRA_BITS))
                        / (fpga_config.clk_ticks_per_sample_a as usize
                            * config::SAMPLES_PER_CARRIER_PERIOD)), // phase_step1
                    ((1 << (config::FP_NBITS + config::FP_EXTRA_BITS))
                        / (fpga_config.clk_ticks_per_sample_b as usize
                            * config::SAMPLES_PER_CARRIER_PERIOD)), // phase_step2
                    (fpga_config.p_factor * (1 << config::PI_CONTROLLER_PARAM_FRACTION_BITS) as f64)
                        as usize,
                    (fpga_config.i_factor * (1 << config::PI_CONTROLLER_PARAM_FRACTION_BITS) as f64)
                        as usize,
                ];

                for k in 0..vals.len() {
                    BigEndian::write_u32(&mut config_word[k * V..(k + 1) * V], vals[k] as u32);
                }
            }
            if c == 2 {
                // Second config word
                let vals = [
                    (fpga_config.power_a1 * config::FP_MAX as f64) as isize,
                    (fpga_config.power_a2 * config::FP_MAX as f64) as isize,
                    (fpga_config.power_b1 * config::FP_MAX as f64) as isize,
                    (fpga_config.power_b2 * config::FP_MAX as f64) as isize,
                ];

                for k in 0..vals.len() {
                    BigEndian::write_u32(&mut config_word[k * V..(k + 1) * V], vals[k] as u32);
                }
            }
        }
    }
}
