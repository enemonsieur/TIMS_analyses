use std::time::{Duration, Instant};

use egui::{Button, Color32, Grid, ProgressBar, RichText, ScrollArea, Slider, Ui, Vec2};
use egui_toast::ToastKind;
use protocols::MachineConfig;

use crate::{ChannelControls, ChannelID, Client, Resources, Settings, SignalControls};

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum ControlPanelState {
    Disconnected,
    Connected,
    Armed,
    Stim,
    StimPaused,
    Preview,
    PreviewPaused,
    Error,
}

pub struct ControlPanel {
    state: ControlPanelState,
    state_previous: ControlPanelState,
    last_connection_attempt_time: Instant,
    session_progress: f64,
    channel_a_controls: ChannelControls,
    channel_b_controls: ChannelControls,
    signal_controls: SignalControls,
}

impl Default for ControlPanel {
    fn default() -> Self {
        Self {
            state: ControlPanelState::Disconnected,
            state_previous: ControlPanelState::Disconnected,
            last_connection_attempt_time: Instant::now(),
            session_progress: 0.0,
            channel_a_controls: ChannelControls { id: ChannelID::A },
            channel_b_controls: ChannelControls { id: ChannelID::B },
            signal_controls: SignalControls {},
        }
    }
}

impl ControlPanel {
    pub fn show(&mut self, settings: &mut Settings, resources: &mut Resources, ui: &mut Ui) {
        let connected = self.state != ControlPanelState::Disconnected;

        let controls_enabled = match self.state {
            ControlPanelState::Connected | ControlPanelState::Error => true,
            _ => false,
        };

        ui.vertical_centered(|ui| {
            ui.separator();
            self.server_controls(settings, resources, ui);
            ui.heading("Control Panel");
            ui.add_enabled_ui(connected, |ui| {
                self.enable_and_start_controls(settings, resources, ui);
                self.session_controls(settings, resources, ui);
                ui.add_enabled_ui(controls_enabled, |ui| {
                    self.intensity_and_duration_controls(settings, resources, ui);
                    ui.separator();

                    self.channel_a_controls.show(
                        &mut settings.channel_a_settings,
                        resources,
                        &settings.signals,
                        ui,
                    );
                    self.channel_b_controls.show(
                        &mut settings.channel_b_settings,
                        resources,
                        &settings.signals,
                        ui,
                    );
                    ScrollArea::vertical().show(ui, |ui| {
                        self.signal_controls.show(settings, resources, ui);
                    });
                });
            });
        });

        if self.session_progress < 1.0 && resources.session_progress >= 1.0 {
            self.state = ControlPanelState::Connected;
        }
        self.session_progress = resources.session_progress;

        if self.state != self.state_previous {
            if self.state == ControlPanelState::Error {
            }
            self.send_config_to_server(settings, resources);
        }
        self.state_previous = self.state;
    }

    fn send_config_to_server(&mut self, settings: &Settings, resources: &mut Resources) {
        let play = match self.state {
            ControlPanelState::Stim | ControlPanelState::Preview => true,
            _ => false,
        };

        let stim = self.state == ControlPanelState::Stim;

        if let Ok(cconf) = settings.to_controller_config(&resources.machine_config, play, stim) {
            resources.client.set_controller_config(&cconf).unwrap();
        }
    }

    fn send_protocol_to_server(&mut self, settings: &Settings, resources: &mut Resources) {
        if let Ok(protocol) = settings.to_stimulation_protocol() {
            resources.client.set_protocol(&protocol).unwrap();
        }
    }


    fn server_controls(&mut self, settings: &mut Settings, resources: &mut Resources, ui: &mut Ui) {
        if !settings.running_on_target_machine {
            ui.horizontal_top(|ui| {
                ui.label("Machine IP:");
                ui.spacing_mut().text_edit_width = 0.65 * settings.control_panel_width;
                ui.text_edit_singleline(&mut settings.server_ip);
                if ui.button("Connect").clicked() {
                    resources.client.disconnect();
                    resources.client = Client::new(settings.server_ip.clone());
                    self.last_connection_attempt_time = Instant::now();
                    resources.show_toast(
                        &format!("Connecting to {}", settings.server_ip),
                        ToastKind::Info,
                    );
                }
            });
            ui.separator();
        }

        if self.state == ControlPanelState::Disconnected && resources.client.connected() {
            self.state = ControlPanelState::Connected;
            resources.machine_config = match resources.client.get_machine_config() {
                Ok(mconf) => mconf,
                Err(e) => {
                    log::warn!("Unable to update machine configuration from server: {e}");
                    log::warn!("Using default configuration instead");
                    MachineConfig::default()
                }
            };

            if !settings.running_on_target_machine {
                resources.show_toast(
                    &format!("Connected to {}", resources.client.get_server_ip()),
                    ToastKind::Info,
                );
            }
        }

        if self.state == ControlPanelState::Connected && !resources.client.connected() {
            self.state = ControlPanelState::Disconnected;
            resources.show_toast(
                &format!("Lost connection to {}", resources.client.get_server_ip()),
                ToastKind::Error,
            );
        }

        if self.last_connection_attempt_time.elapsed() > Duration::from_secs(4) {
            if !resources.client.connected() {
                resources.show_toast(
                    &format!("Unable to connect to {}", resources.client.get_server_ip()),
                    ToastKind::Error,
                );
                self.last_connection_attempt_time = Instant::now();
            }
        }
    }

    fn enable_and_start_controls(
        &mut self,
        settings: &mut Settings,
        resources: &mut Resources,
        ui: &mut Ui,
    ) {
        let button_size = Vec2::new(
            settings.control_panel_width / 3.0,
            settings.large_button_size[1],
        );
        Grid::new("enable_and_start_grid")
            .num_columns(3)
            .max_col_width(settings.control_panel_width / 3.0)
            .show(ui, |ui| {
                let enable_button_text = match self.state {
                    ControlPanelState::Connected => "Enable",
                    ControlPanelState::Error => "Clear Error",
                    _ => "Disable",
                };

                let enable_button_enabled = match self.state {
                    ControlPanelState::Connected
                    | ControlPanelState::Armed
                    | ControlPanelState::Error => true,
                    _ => false,
                };

                let enable_button = Button::new(
                    RichText::new(enable_button_text).size(settings.large_button_font_size),
                )
                .min_size(button_size)
                .corner_radius(settings.large_button_corner_radius);

                if ui
                    .add_enabled(enable_button_enabled, enable_button)
                    .clicked()
                {
                    self.state = match self.state {
                        ControlPanelState::Connected => ControlPanelState::Armed,
                        _ => ControlPanelState::Connected,
                    }
                };

                let status = match self.state {
                    ControlPanelState::Disconnected => "Disconnected",
                    ControlPanelState::Connected => "Connected",
                    ControlPanelState::Armed => "Stim Ready",
                    ControlPanelState::Stim => "Stim ON",
                    ControlPanelState::StimPaused => "Stim Paused",
                    ControlPanelState::Preview => "Stim Preview",
                    ControlPanelState::PreviewPaused => "Preview Paused",
                    ControlPanelState::Error => "Error",
                };

                let status_color = match self.state {
                    ControlPanelState::Disconnected => Color32::WHITE,
                    ControlPanelState::Connected => Color32::GREEN,
                    ControlPanelState::Armed => Color32::YELLOW,
                    ControlPanelState::Stim => Color32::RED,
                    ControlPanelState::StimPaused => Color32::YELLOW,
                    ControlPanelState::Preview => Color32::WHITE,
                    ControlPanelState::PreviewPaused => Color32::WHITE,
                    ControlPanelState::Error => Color32::RED,
                };

                ui.centered_and_justified(|ui| {
                    ui.label(
                        RichText::new(status)
                            .size(settings.large_label_font_size)
                            .color(status_color),
                    );
                });

                let start_button_text = match self.state {
                    ControlPanelState::Connected | ControlPanelState::Error => "Preview",
                    ControlPanelState::Armed => "Start",
                    _ => "Stop",
                };

                let start_button = Button::new(
                    RichText::new(start_button_text).size(settings.large_button_font_size),
                )
                .min_size(button_size)
                .corner_radius(settings.large_button_corner_radius);
                if ui
                    .add_enabled(self.state != ControlPanelState::Error, start_button)
                    .clicked()
                {
                    self.state = match self.state {
                        ControlPanelState::Connected => ControlPanelState::Preview,
                        ControlPanelState::Armed => ControlPanelState::Stim,
                        _ => ControlPanelState::Connected,
                    };

                    self.send_protocol_to_server(settings, resources);
                };
            });
    }

    fn session_controls(
        &mut self,
        settings: &mut Settings,
        _resources: &mut Resources,
        ui: &mut Ui,
    ) {
        let progress_text = format!(
            "Session progress: {:.1}/{:.1} s",
            self.session_progress * settings.session_duration,
            settings.session_duration
        );
        ui.label(progress_text);
        ui.horizontal(|ui| {
            ui.add(
                ProgressBar::new(self.session_progress as f32)
                    .desired_width(settings.control_panel_width * 0.80),
            );
            ui.centered_and_justified(|ui| {
                let pause_button_enabled = match self.state {
                    ControlPanelState::Disconnected
                    | ControlPanelState::Connected
                    | ControlPanelState::Armed => false,
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
                        _ => ControlPanelState::Connected,
                    };
                }
            });
        });
    }

    fn intensity_and_duration_controls(
        &mut self,
        settings: &mut Settings,
        _resources: &mut Resources,
        ui: &mut Ui,
    ) {
        egui::Grid::new("power_and_duration_grid").show(ui, |ui| {
            ui.label("Stimulation intensity");
            ui.style_mut().spacing.slider_width = settings.control_panel_width * 0.575;
            ui.add(Slider::new(&mut settings.intensity, 0.0..=1.0).show_value(false));
            ui.label(format!("{0:.0}%", 100.0 * settings.intensity));
            ui.end_row();

            ui.label("Session duration");
            ui.centered_and_justified(|ui| {
                ui.add(
                    egui::DragValue::new(&mut settings.session_duration)
                        .range(0.1..=1800.0)
                        .fixed_decimals(1)
                        .speed(1),
                );
            });
            ui.label("sec");
            ui.end_row();
        });
    }
}
