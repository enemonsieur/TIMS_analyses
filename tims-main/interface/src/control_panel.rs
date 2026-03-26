use strum::IntoEnumIterator;

use crate::config;
use crate::capacitor_banks::CapacitorBanks;
use crate::channel_controls::{ChannelControls, Coil};
use crate::driver::{Driver, DriverConfig, SignalSource, StimulationMode};
use crate::protocol::Protocol;
use crate::status_panel::StatusPanel;
use rodio::Source;
use std::collections::HashMap;
use std::path::PathBuf;
use std::str::FromStr;

#[derive(PartialEq, serde::Deserialize, serde::Serialize, strum::EnumIter, Clone)]
pub enum ModulationType {
    None,
    Sine,
    BurstTrains,
    CThetaBurst,
    IThetaBurst,
    FromFile,
}

impl ModulationType {
    fn to_string(&mut self) -> &str {
        match self {
            ModulationType::None => "None",
            ModulationType::Sine => "Sinusoidal Modulation",
            ModulationType::BurstTrains => "Burst trains Modulation",
            ModulationType::CThetaBurst => "cTBS Modulation",
            ModulationType::IThetaBurst => "iTBS Modulation",
            ModulationType::FromFile => "From file",
        }
    }
}

#[derive(PartialEq, Clone, Copy)]
pub enum ControlPanelState {
    Disabled,
    Armed,
    Stim,
    StimPaused,
    Preview,
    PreviewPaused,
    Error,
}

#[derive(serde::Deserialize, serde::Serialize)]
#[serde(default)]
pub struct ControlPanel {
    #[serde(skip)]
    driver_config: DriverConfig,
    #[serde(skip)]
    state: ControlPanelState,
    #[serde(skip)]
    state_previous: ControlPanelState,
    #[serde(skip)]
    session_progress: f64,
    #[serde(skip)]
    protocol_file_dialog: egui_file_dialog::FileDialog,

    power: f64,
    session_duration: f64,
    session_duration_input_enabled: bool,
    stimulation_mode: StimulationMode,
    amplitude_signal_source: SignalSource,
    external_ampitude_equal_currents: bool,
    modulation_signal_source: SignalSource,
    modulation_type: ModulationType,
    modulation_frequency: f64,
    modulation_depth: f64,
    burst_frequency: f64,
    burst_num_cycles: isize,
    burst_repetition_frequency: f64,
    bursts_per_train: isize,
    intertrain_interval: f64,
    channel_a: ChannelControls,
    channel_b: ChannelControls,
    available_coils: HashMap<String, Coil>,
    protocol_file: Option<PathBuf>,
}

impl Default for ControlPanel {
    fn default() -> Self {
        Self {
            driver_config: DriverConfig::default(),
            state: ControlPanelState::Disabled,
            state_previous: ControlPanelState::Disabled,
            session_progress: 0.0,
            session_duration_input_enabled: true,
            protocol_file_dialog: egui_file_dialog::FileDialog::new()
                .initial_directory(PathBuf::from_str(config::PROTOCOLS_DIR).unwrap()),
            power: 0.0,
            session_duration: 60.0,
            stimulation_mode: StimulationMode::TI,
            amplitude_signal_source: SignalSource::Internal,
            external_ampitude_equal_currents: true,
            modulation_signal_source: SignalSource::Internal,
            modulation_type: ModulationType::None,
            modulation_frequency: 10.0,
            modulation_depth: 1.0,
            burst_frequency: 50.0,
            burst_num_cycles: 3,
            burst_repetition_frequency: 5.0,
            bursts_per_train: 10,
            intertrain_interval: 8.0,
            channel_a: ChannelControls {
                channel_id: "A".to_string(),
                ..Default::default()
            },
            channel_b: ChannelControls {
                channel_id: "B".to_string(),
                ..Default::default()
            },
            available_coils: HashMap::new(),
            protocol_file: None,
        }
    }
}

impl ControlPanel {
    pub fn show(
        &mut self,
        ui: &mut egui::Ui,
        driver: &mut Driver,
        capacitor_banks: &mut CapacitorBanks,
        status_panel: &StatusPanel,
        toasts: &mut egui_toast::Toasts,
        sound_stream: Option<&mut rodio::stream::OutputStream>,
    ) {
        if self.session_progress < 1.0 && status_panel.session_progress >= 1.0 {
            self.state = ControlPanelState::Disabled;
            // self.update_driver_config_from_ui(driver, toasts);
        }
        self.session_progress = status_panel.session_progress;

        if config::SAFETY_CHECKS_ENABLED == 1 {
            for i in 0..4 {
                if i < config::NUM_COILS as usize {
                    if status_panel.max_currents[i] > config::MAX_CURRENT
                    || status_panel.temperature[i] > config::MAX_TEMPERATURE
                    || status_panel.flow_rate[i] < config::MIN_FLOW_RATE {
                        self.state = ControlPanelState::Error;
                    }
                }
            }

            if status_panel.supply_power > config::MAX_POWER {
                self.state = ControlPanelState::Error;
            }

            if status_panel.supply_current > config::MAX_SUPPLY_CURRENT {
                self.state = ControlPanelState::Error;
            }
        }

        ui.vertical_centered(|ui| {
            ui.heading("Control Panel");
            // ui.label(format!("Device IP: {:?}", local_ip_address::local_ip().unwrap()));

            egui::Grid::new("enable_and_start_grid")
                .num_columns(3)
                .min_col_width(100.0)
                .show(ui, |ui| {
                    let button_size = egui::Vec2::new(100.0, 40.0);
                    let button_font_size = 15.0;
                    let button_corner_radius = 10.0;

                    let enable_button_text = match self.state {
                        ControlPanelState::Disabled => "Enable",
                        ControlPanelState::Error => "Clear Error",
                        _ => "Disable",
                    };

                    let enable_button_enabled = match self.state {
                        ControlPanelState::Disabled
                        | ControlPanelState::Armed
                        | ControlPanelState::Error => true,
                        _ => false,
                    };

                    let enable_button = egui::Button::new(
                        egui::RichText::new(enable_button_text).size(button_font_size),
                    )
                    .min_size(button_size)
                    .corner_radius(button_corner_radius);

                    if ui
                        .add_enabled(enable_button_enabled, enable_button)
                        .clicked()
                    {
                        if self.state == ControlPanelState::Disabled {
                            if self.available_coils.len() > 0 {
                                let mut ca = self
                                    .channel_a
                                    .get_capacitor_bank_setting(&self.available_coils)
                                    as usize;

                                let mut cb = self
                                    .channel_b
                                    .get_capacitor_bank_setting(&self.available_coils)
                                    as usize;

                                if !self.channel_a.enabled {
                                    ca = 0;
                                }

                                if !self.channel_b.enabled {
                                    cb = 0;
                                }

                                capacitor_banks.set(&[ca, ca, cb, cb]);

                                self.state = ControlPanelState::Armed;
                            } else {
                                toasts.add(egui_toast::Toast {
                                    text: "Please add at least one coil definition before starting"
                                        .into(),
                                    kind: egui_toast::ToastKind::Error,
                                    options: egui_toast::ToastOptions::default()
                                        .duration_in_seconds(2.0)
                                        .show_progress(false),
                                    ..Default::default()
                                });
                            }
                        } else {
                            self.state = ControlPanelState::Disabled;
                        }
                    };

                    let status = match self.state {
                        ControlPanelState::Disabled => "Stim Disabled",
                        ControlPanelState::Armed => "Stim Ready",
                        ControlPanelState::Stim => "Stim ON",
                        ControlPanelState::StimPaused => "Stim Paused",
                        ControlPanelState::Preview => "Stim Preview",
                        ControlPanelState::PreviewPaused => "Preview Paused",
                        ControlPanelState::Error => "Error",
                    };

                    let status_color = match self.state {
                        ControlPanelState::Disabled => egui::Color32::WHITE,
                        ControlPanelState::Armed => egui::Color32::YELLOW,
                        ControlPanelState::Stim => egui::Color32::RED,
                        ControlPanelState::StimPaused => egui::Color32::YELLOW,
                        ControlPanelState::Preview => egui::Color32::WHITE,
                        ControlPanelState::PreviewPaused => egui::Color32::WHITE,
                        ControlPanelState::Error => egui::Color32::RED,
                    };

                    ui.centered_and_justified(|ui| {
                        ui.label(egui::RichText::new(status).size(14.0).color(status_color));
                    });

                    let start_button_text = match self.state {
                        ControlPanelState::Disabled | ControlPanelState::Error => "Preview",
                        ControlPanelState::Armed => "Start",
                        _ => "Stop",
                    };

                    let start_button = egui::Button::new(
                        egui::RichText::new(start_button_text).size(button_font_size),
                    )
                    .min_size(button_size)
                    .corner_radius(button_corner_radius);
                    if ui
                        .add_enabled(self.state != ControlPanelState::Error, start_button)
                        .clicked()
                    {
                        self.state = match self.state {
                            ControlPanelState::Disabled => ControlPanelState::Preview,
                            ControlPanelState::Armed => ControlPanelState::Stim,
                            _ => ControlPanelState::Disabled,
                        };

                        self.update_protocol_from_ui(driver);
                        // self.update_driver_config_from_ui(driver, toasts);
                    };
                });

            let progress_text = format!(
                "Session progress: {:.1}/{:.1} s",
                self.session_progress * self.session_duration,
                self.session_duration
            );
            ui.label(progress_text);
            ui.horizontal(|ui| {
                ui.add(
                    egui::ProgressBar::new(self.session_progress as f32)
                        .desired_width(ui.available_width() * 0.80),
                );
                ui.centered_and_justified(|ui| {
                    let pause_button_enabled = match self.state {
                        ControlPanelState::Disabled | ControlPanelState::Armed => false,
                        _ => true,
                    };

                    let pause_button_highlighted = match self.state {
                        ControlPanelState::StimPaused | ControlPanelState::PreviewPaused => true,
                        _ => false,
                    };

                    let pause_button = ui.add_enabled(
                        pause_button_enabled,
                        egui::Button::new("Pause").selected(pause_button_highlighted),
                    );

                    if pause_button.clicked() {
                        self.state = match self.state {
                            ControlPanelState::Stim => ControlPanelState::StimPaused,
                            ControlPanelState::Preview => ControlPanelState::PreviewPaused,
                            ControlPanelState::StimPaused => ControlPanelState::Stim,
                            ControlPanelState::PreviewPaused => ControlPanelState::Preview,
                            ControlPanelState::Error => ControlPanelState::Error,
                            _ => ControlPanelState::Disabled,
                        };

                        // self.update_driver_config_from_ui(driver, toasts);
                    }
                });
            });

            let param_ui_enabled = self.state == ControlPanelState::Disabled;

            ui.add_enabled_ui(param_ui_enabled, |ui| {
                egui::Grid::new("power_and_duration_grid").show(ui, |ui| {
                    ui.label("Power:");
                    let w = ui.style().spacing.slider_width;
                    ui.style_mut().spacing.slider_width = 170.0;
                    ui.add(egui::Slider::new(&mut self.power, 0.0..=1.0).show_value(false));
                    ui.style_mut().spacing.slider_width = w;
                    ui.label(format!("{0:.0}%", 100.0 * self.power));
                    ui.end_row();

                    ui.label("Session duration:");
                    ui.centered_and_justified(|ui| {
                        ui.add_enabled(
                            self.session_duration_input_enabled,
                            egui::DragValue::new(&mut self.session_duration)
                                .range(0.1..=1800.0)
                                .fixed_decimals(1)
                                .speed(1),
                        );
                    });
                    ui.label("sec");
                    ui.end_row();
                });

                ui.separator();
                egui::Grid::new("modes_grid").show(ui, |ui| {
                    ui.label("Stimulation mode:");
                    ui.selectable_value(&mut self.stimulation_mode, StimulationMode::TI, "TI");
                    ui.selectable_value(&mut self.stimulation_mode, StimulationMode::AM, "AM");
                    ui.end_row();

                    ui.label("Amplitude signal source:");
                    ui.selectable_value(
                        &mut self.amplitude_signal_source,
                        SignalSource::Internal,
                        "Internal",
                    );
                    ui.selectable_value(
                        &mut self.amplitude_signal_source,
                        SignalSource::External,
                        "External",
                    );
                    ui.end_row();

                    ui.label("Modulation signal source:");
                    ui.selectable_value(
                        &mut self.modulation_signal_source,
                        SignalSource::Internal,
                        "Internal",
                    );
                    ui.selectable_value(
                        &mut self.modulation_signal_source,
                        SignalSource::External,
                        "External",
                    );
                    ui.end_row();

                    if self.amplitude_signal_source == SignalSource::External {
                        ui.label("Equal currents");
                        ui.checkbox(&mut self.external_ampitude_equal_currents, "");
                        ui.end_row();
                    }
                });

                if self.modulation_signal_source == SignalSource::Internal 
                    || self.amplitude_signal_source == SignalSource::Internal {
                    ui.separator();
                    egui::Grid::new("modulation_type_grid").show(ui, |ui| {
                        ui.label("Internal signal type:");
                        egui::ComboBox::from_id_salt("modulation_type_combobox")
                            .selected_text(self.modulation_type.to_string())
                            .show_ui(ui, |ui| {
                                for t in ModulationType::iter() {
                                    ui.selectable_value(
                                        &mut self.modulation_type,
                                        t.clone(),
                                        t.clone().to_string(),
                                    );
                                }
                            });
                        ui.end_row();

                        if self.modulation_type == ModulationType::Sine {
                            ui.label("Modulation frequency");
                            ui.add(
                                egui::DragValue::new(&mut self.modulation_frequency)
                                    .suffix(" Hz")
                                    .range(0.01..=300.0)
                                    .fixed_decimals(1)
                                    .speed(0.1),
                            );
                            ui.end_row();

                            ui.label("Modulation depth");
                            ui.add(
                                egui::DragValue::new(&mut self.modulation_depth)
                                    .range(0.0..=1.0)
                                    .fixed_decimals(3)
                                    .speed(0.001),
                            );
                            ui.end_row();
                        }

                        if self.modulation_type == ModulationType::BurstTrains {
                            let min_burst_frequency =
                                self.burst_repetition_frequency * self.burst_num_cycles as f64;
                            let max_burst_num_cycles =
                                (self.burst_frequency / self.burst_repetition_frequency) as isize;
                            let max_burst_repetitiion_frequency =
                                self.burst_frequency / self.burst_num_cycles as f64;
                            ui.label("Burst frequency");
                            ui.add(
                                egui::DragValue::new(&mut self.burst_frequency)
                                    .suffix(" Hz")
                                    .range(min_burst_frequency..=300.0)
                                    .fixed_decimals(3)
                                    .speed(0.1),
                            );
                            ui.end_row();

                            ui.label("Number of cycles per burst");
                            ui.add(
                                egui::DragValue::new(&mut self.burst_num_cycles)
                                    .range(1..=max_burst_num_cycles),
                            );
                            ui.end_row();

                            ui.label("Burst repetition frequency");
                            ui.add(
                                egui::DragValue::new(&mut self.burst_repetition_frequency)
                                    .suffix(" Hz")
                                    .range(0.0..=max_burst_repetitiion_frequency)
                                    .fixed_decimals(3)
                                    .speed(0.1),
                            );
                            ui.end_row();

                            ui.label("Number of bursts per train");
                            ui.add(
                                egui::DragValue::new(&mut self.bursts_per_train).range(1..=1000),
                            );
                            ui.end_row();

                            ui.label("Inter-train interval");
                            ui.add(
                                egui::DragValue::new(&mut self.intertrain_interval)
                                    .suffix(" s")
                                    .range(0.0..=120.0)
                                    .fixed_decimals(3)
                                    .speed(0.1),
                            );
                            ui.end_row();
                        }

                        if self.modulation_type == ModulationType::CThetaBurst {
                            self.burst_frequency = 50.0;
                            self.burst_num_cycles = 3;
                            self.burst_repetition_frequency = 5.0;
                            self.bursts_per_train = 1;
                            self.intertrain_interval = 0.0;
                        }

                        if self.modulation_type == ModulationType::IThetaBurst {
                            self.burst_frequency = 50.0;
                            self.burst_num_cycles = 3;
                            self.burst_repetition_frequency = 5.0;
                            self.bursts_per_train = 10;
                            self.intertrain_interval = 8.0;
                        }

                        if self.modulation_type == ModulationType::FromFile {
                            ui.label("Protocol file:");
                            if self.protocol_file != None {
                                ui.label(self.protocol_file.clone().unwrap().file_stem().unwrap().to_str().unwrap());
                            }
                            else {
                                ui.label("None");
                            }
                            if ui.button("Pick").clicked() {
                                self.protocol_file_dialog.pick_file();
                            }
                            ui.end_row();
                        }
                    });
                }

                ui.separator();
                self.channel_a.show(ui, &mut self.available_coils, toasts);
                ui.separator();
                self.channel_b.show(ui, &mut self.available_coils, toasts);
                ui.separator();
            });
        });

        if self.state != self.state_previous {
            if self.state == ControlPanelState::Error {
                if config::SOUND_DEVICE_AVAILABLE == 1 {
                    let wave = rodio::source::SineWave::new(440.0)
                        .take_duration(std::time::Duration::from_secs(1));
                    sound_stream.unwrap().mixer().add(wave);
                }
            }
            self.update_driver_config_from_ui(driver, toasts);
        }
        self.state_previous = self.state;

        self.protocol_file_dialog.update(ui.ctx());
        if let Some(path) = self.protocol_file_dialog.take_picked() {
            self.protocol_file = Some(path.to_path_buf());
            self.session_duration = Protocol::from_file(self.protocol_file.clone().unwrap()).duration;
            println!("{:?}", path);
        }

        self.session_duration_input_enabled = 
            (self.modulation_signal_source == SignalSource::Internal 
                || self.amplitude_signal_source == SignalSource::Internal) 
            && (self.modulation_type != ModulationType::FromFile);
    }

    pub fn update_driver_config_from_ui(
        &mut self,
        driver: &mut Driver,
        toasts: &mut egui_toast::Toasts,
    ) {
        let mut dconf = DriverConfig::default();

        if self.available_coils.len() == 0 {
            toasts.add(egui_toast::Toast {
                text: "Please add at least one coil definition before starting".into(),
                kind: egui_toast::ToastKind::Error,
                options: egui_toast::ToastOptions::default()
                    .duration_in_seconds(2.0)
                    .show_progress(false),
                ..Default::default()
            });
        } else {
            dconf.system_enabled = true;

            dconf.controller_enabled_a =
                self.channel_a.enabled && self.state == ControlPanelState::Stim;

            dconf.controller_enabled_b =
                self.channel_b.enabled && self.state == ControlPanelState::Stim;

            dconf.play_protocol = match self.state {
                ControlPanelState::Stim | ControlPanelState::Preview => true,
                _ => false,
            };

            dconf.p_factor = 4.0;
            dconf.i_factor = 0.05;

            // dconf.p_factor = 6.0;
            // dconf.i_factor = 0.1;

            dconf.clk_ticks_per_sample_a = self.available_coils[&self.channel_a.selected_coil_name]
                .possible_settings[self.channel_a.lc_setting_index]
                .clk_ticks_per_sample;

            dconf.clk_ticks_per_sample_b = self.available_coils[&self.channel_b.selected_coil_name]
                .possible_settings[self.channel_b.lc_setting_index]
                .clk_ticks_per_sample;

            dconf.stimulation_mode = self.stimulation_mode;
            dconf.amplitude_signal_source = self.amplitude_signal_source;
            dconf.modulation_signal_source = self.modulation_signal_source;

            dconf.power_a1 = self.power * self.channel_a.current1;
            dconf.power_a2 = self.power * self.channel_a.current2;
            dconf.power_b1 = self.power * self.channel_b.current1;
            dconf.power_b2 = self.power * self.channel_b.current2;

            driver.set_config(dconf);
        }
    }

    pub fn update_protocol_from_ui(&mut self, driver: &mut Driver) {
        let protocol = match self.modulation_signal_source {
            SignalSource::Internal => match self.modulation_type {
                ModulationType::None => {
                    Protocol::constant_amp_constant_phase(self.session_duration, 0.0)
                }

                ModulationType::Sine => Protocol::sine_modulation(
                    self.session_duration,
                    self.modulation_frequency,
                    self.modulation_depth,
                ),

                ModulationType::BurstTrains
                | ModulationType::CThetaBurst
                | ModulationType::IThetaBurst => Protocol::burst_train_modulation(
                    self.session_duration,
                    self.burst_frequency,
                    self.burst_num_cycles,
                    self.burst_repetition_frequency,
                    self.bursts_per_train,
                    self.intertrain_interval,
                ),

                ModulationType::FromFile => {
                    let protocol = Protocol::from_file(self.protocol_file.clone().unwrap());
                    self.session_duration = protocol.duration;
                    protocol
                }
            },

            SignalSource::External => match self.amplitude_signal_source {
                SignalSource::Internal => {
                    if self.modulation_type == ModulationType::FromFile {
                        let protocol = Protocol::from_file(self.protocol_file.clone().unwrap());
                        self.session_duration = protocol.duration;
                        protocol
                    }
                    else {
                        Protocol::constant_amp_external_phase_control(self.session_duration)
                    }
                }

                SignalSource::External => {
                    Protocol::external_amp_and_phase_control(self.session_duration)
                }
            },
        };

        driver.set_protocol(protocol);
    }
}
