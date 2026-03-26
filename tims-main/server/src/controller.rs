use rppal::gpio::Gpio;
use rppal::spi::{Bus, Mode, SlaveSelect, Spi};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::thread;

use crate::power_supply::PowerSupply;
use crate::temperature_sensors::TemperatureSensors;
use crate::{CapacitorBanks, machine_config};
use protocols::{
    ControllerConfig, ControllerState, ControllerStatus, MachineConfig, MonitorData, PACKET_NBYTES,
    StimulationProtocol, TIMSError, config,
};

pub struct Controller {
    config: Arc<Mutex<ControllerConfig>>,
    protocol: Arc<Mutex<StimulationProtocol>>,
    capacitor_banks: Arc<Mutex<CapacitorBanks>>,
    machine_config: Arc<Mutex<MachineConfig>>,
}

// print some info every N_TRIGS received from the FPGA
const N_TRIGS: usize = 100;

impl Controller {
    pub fn new() -> Self {
        Controller {
            config: Arc::new(Mutex::new(ControllerConfig::default())),
            protocol: Arc::new(Mutex::new(StimulationProtocol::default())),
            capacitor_banks: Arc::new(Mutex::new(CapacitorBanks::default())),
            machine_config: Arc::new(Mutex::new(MachineConfig::default())),
        }
    }

    pub fn start(&mut self) -> Receiver<ControllerStatus> {
        let (status_sender, status_receiver) = channel();

        let controller_config = self.config.clone();
        let protocol = self.protocol.clone();
        let capacitor_banks = self.capacitor_banks.clone();
        let mconf = self.machine_config.clone();

        thread::spawn(move || {
            let mc = match machine_config::from_environment() {
                Ok(mc) => mc,
                Err(e) => {
                    log::error!(
                        "Error loading machine configuration from environment variables: {e}"
                    );
                    Controller::send_error(&status_sender, e);
                    return;
                }
            };
            *mconf.lock().unwrap() = mc.clone();
            log::info!("Loaded machine configuration: {mc:#?}");

            let gpio = match Gpio::new() {
                Ok(gpio) => gpio,
                Err(e) => {
                    log::error!("Error initializing GPIO: {e}");
                    Controller::send_error(&status_sender, TIMSError::GPIOError);
                    return;
                }
            };
            log::info!("GPIO initialized successfully");

            let trig_pin = match gpio.get(config::GPIO_TRIG_PIN as u8) {
                Ok(pin) => pin,
                Err(e) => {
                    log::error!("Error accessing trigger GPIO pin: {e}");
                    Controller::send_error(&status_sender, TIMSError::GPIOError);
                    return;
                }
            }
            .into_input();
            log::info!("Using pin {} as SPI trigger pin", config::GPIO_TRIG_PIN);

            let spi = match Spi::new(
                Bus::Spi0,
                SlaveSelect::Ss0,
                config::INTERFACE_SPI_FREQ as u32,
                Mode::Mode1,
            ) {
                Ok(spi) => spi,
                Err(e) => {
                    log::error!("Error initializing SPI bus: {e}");
                    Controller::send_error(&status_sender, TIMSError::SPIError);
                    return;
                }
            };
            log::info!(
                "SPI bus initialized with a clock frequency of {} MHz",
                config::INTERFACE_SPI_FREQ / 1000000
            );

            *capacitor_banks.lock().unwrap() =
                match CapacitorBanks::new(mc.num_coils, mc.capacitors.len()) {
                    Ok(cb) => {
                        log::info!("CapacitorBanks initialized successfully");
                        cb
                    }
                    Err(e) => {
                        log::error!("Error capacitor banks I2c buss: {e}");
                        Controller::send_error(&status_sender, TIMSError::I2cError);
                        return;
                    }
                };

            let mut temp_sensors = if mc.num_temperature_sensors > 0 {
                Some(match TemperatureSensors::new(mc.num_temperature_sensors) {
                    Ok(ts) => {
                        log::info!("Temperature sensors initialized successfully");
                        ts
                    }
                    Err(e) => {
                        log::error!("Error initializing temperature sensors SPI buses: {e}");
                        Controller::send_error(&status_sender, TIMSError::SPIError);
                        return;
                    }
                })
            } else {
                log::info!("No temperature sensors available");
                None
            };

            let mut psu = if mc.smbus_psu_connected {
                Some(match PowerSupply::new() {
                    Ok(psu) => {
                        log::info!("Power supply SMBUS initialized successfully");
                        psu
                    }
                    Err(e) => {
                        log::error!("Error initializing power supply I2c bus: {e}");
                        Controller::send_error(&status_sender, TIMSError::I2cError);
                        return;
                    }
                })
            } else {
                log::info!("Power supply SMBUS not available");
                None
            };

            let mut rx_buffer: [u8; PACKET_NBYTES] = [0; PACKET_NBYTES];
            let mut tx_buffer: [u8; PACKET_NBYTES] = [0; PACKET_NBYTES];

            let mut session_progress = 0.0;
            let mut status_idx: u64 = 0;
            let mut avg_ttr: f64 = 0.0;
            let mut trig_prev = false;

            log::info!("Listening for SPI triggers");
            loop {
                let trig = trig_pin.is_high();

                if trig && !trig_prev {
                    let now = std::time::Instant::now();
                    let mut state = ControllerState::Idle;

                    // Grab the configurations
                    let cconf = &controller_config.lock().unwrap().clone();
                    let mc = mconf.lock().unwrap().clone();

                    // FPGA ready for data transfer
                    // prepare data packet for sending the the FPGA
                    if cconf.play_protocol {
                        session_progress = protocol.lock().unwrap().to_buffer(&mut tx_buffer);
                        if session_progress < 1.0 {
                            state = ControllerState::Active;
                        }
                    } else {
                        for i in 0..tx_buffer.len() {
                            tx_buffer[i] = 0;
                        }
                    }

                    // write configuration words into tx buffer
                    cconf.to_buffer(&mut tx_buffer);

                    // Exchange data with FPGA
                    if let Err(e) = spi.transfer(&mut rx_buffer, &tx_buffer) {
                        log::error!("Error during SPI data transfer: {e}");
                        Controller::send_error(&status_sender, TIMSError::SPIError);
                        return;
                    }

                    let mut status = ControllerStatus::default_and_from_buffer(&rx_buffer, &mc);

                    if !status.packet_valid {
                        status.state = ControllerState::Error(TIMSError::SPIError);
                        status_sender.send(status).unwrap();
                        return;
                    }

                    status.session_progress = session_progress;

                    status_idx += 1;
                    status.idx = status_idx;

                    // Read temperatures
                    if let Some(temp_sensors) = temp_sensors.as_mut() {
                        status.temperature = match temp_sensors.read() {
                            Ok(v) => Some(v.clone()),
                            Err(e) => {
                                log::error!("Error while reading temperature sensors: {e}");
                                status.state = ControllerState::Error(TIMSError::SPIError);
                                status_sender.send(status).unwrap();
                                return;
                            }
                        };
                    }

                    if let Some(psu) = psu.as_mut() {
                        let (current, power) = match psu.read_current_and_power() {
                            Ok(v) => v,
                            Err(e) => {
                                log::error!("Error while reading supply current and power: {e}");
                                status.state = ControllerState::Error(TIMSError::I2cError);
                                status_sender.send(status).unwrap();
                                return;
                            }
                        };
                        status.supply_current = Some(current);
                        status.supply_power = Some(power);
                    }

                    if let Err(e) = Controller::safety_checks(&status, &mc) {
                        status.state = ControllerState::Error(e);
                        status_sender.send(status).unwrap();
                        return;
                    }

                    status.state = state;
                    status_sender.send(status).unwrap();

                    let elapsed = now.elapsed();
                    avg_ttr += elapsed.as_millis() as f64 / N_TRIGS as f64;
                    if status_idx % N_TRIGS as u64 == 0 {
                        log::info!(
                            "Received {status_idx} triggers. Average TTR = {avg_ttr:0.2} ms"
                        );
                        avg_ttr = 0.0;
                    }
                }
                trig_prev = trig;
            }
        });

        status_receiver
    }

    pub fn set_config(&mut self, new_cconf: ControllerConfig) -> Result<(), TIMSError> {
        let mconf = self.machine_config.lock().unwrap().clone();
        let current_cconf = self.config.lock().unwrap().clone();

        if new_cconf.intensity_a1 > mconf.max_intensity_setpoint
            || new_cconf.intensity_a2 > mconf.max_intensity_setpoint
            || new_cconf.intensity_b1 > mconf.max_intensity_setpoint
            || new_cconf.intensity_b2 > mconf.max_intensity_setpoint
        {
            log::error!(
                "Request intensity exceeds maximum allowed stimulation intensity ({})",
                mconf.max_intensity_setpoint
            );
            return Err(TIMSError::ConfigError);
        }

        if new_cconf.lc_setting_a != current_cconf.lc_setting_a
            || new_cconf.lc_setting_b != current_cconf.lc_setting_b
        {
            self.capacitor_banks
                .lock()
                .unwrap()
                .set(new_cconf.lc_setting_a, new_cconf.lc_setting_b)
                .map_err(|e| {
                    log::error!("Error while communicating with capacitor banks {e}");
                    TIMSError::I2cError
                })?;
        }

        *self.config.lock().unwrap() = new_cconf;

        Ok(())
    }

    pub fn set_protocol(&mut self, protocol: StimulationProtocol) -> Result<(), TIMSError> {
        let mut protocol = protocol.clone();
        protocol.compute();
        *self.protocol.lock().unwrap() = protocol;
        Ok(())
    }

    pub fn get_machine_configuration(&mut self) -> MachineConfig {
        self.machine_config.lock().unwrap().clone()
    }

    fn safety_checks(status: &ControllerStatus, mconf: &MachineConfig) -> Result<(), TIMSError> {
        if mconf.safety_checks_enabled {
            if let Some(t) = status.temperature.clone() {
                Controller::check_temperature(&t, mconf)?;
            }

            if let Some(f) = status.flow_rate.clone() {
                Controller::check_flow_rate(&f, mconf)?;
            }

            if let Some(p) = status.supply_power {
                Controller::check_supply_power(p, mconf)?;
            }

            Controller::check_coil_currents(&status.monitor_data, &mconf)?;
        }
        Ok(())
    }

    fn check_temperature(temperature: &Vec<f64>, mconf: &MachineConfig) -> Result<(), TIMSError> {
        for i in 0..mconf.num_coils {
            if temperature[i] > mconf.max_temperature {
                log::error!(
                    "Coil {} temperature ({}) exceeds maximum",
                    i,
                    temperature[i]
                );
                return Err(TIMSError::OverTemperature);
            }
        }
        Ok(())
    }

    fn check_flow_rate(flow_rate: &Vec<f64>, mconf: &MachineConfig) -> Result<(), TIMSError> {
        for i in 0..mconf.num_coils {
            if flow_rate[i] < mconf.min_flowrate {
                log::error!("Coil {} flow rate ({}) is below minimum", i, flow_rate[i]);
                return Err(TIMSError::Underflow);
            }
        }
        Ok(())
    }

    fn check_supply_power(power: f64, mconf: &MachineConfig) -> Result<(), TIMSError> {
        if power > mconf.max_power {
            log::error!("Supply power ({}) exceeds maximum", power);
            return Err(TIMSError::OverSupplyPower);
        }
        Ok(())
    }

    fn check_coil_currents(
        monitor_data: &MonitorData,
        mconf: &MachineConfig,
    ) -> Result<(), TIMSError> {
        let mut coil_idx = 0;
        for i in 0..monitor_data.channels.len() {
            let name = config::MONITOR_TRACE_NAMES[i];
            if name.starts_with("Ia") || name.starts_with("Ib") {
                coil_idx += 1;
                let imax = *monitor_data.channels[i].samples.iter().max().unwrap_or(&0) as f64
                    / config::FP_MAX as f64;
                if imax > mconf.max_current {
                    log::error!("Coil {} current ({}) exceeded maximum", coil_idx, imax);
                    return Err(TIMSError::OverCoilCurrent);
                }
            }
            if coil_idx == mconf.num_coils {
                break;
            }
        }
        Ok(())
    }

    fn send_error(sender: &Sender<ControllerStatus>, e: TIMSError) {
        sender
            .send(ControllerStatus {
                state: ControllerState::Error(e),
                ..Default::default()
            })
            .unwrap();
    }
}
