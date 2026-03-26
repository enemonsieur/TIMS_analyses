use crate::config;
use std::collections::HashMap;
use std::f64::consts::PI;

#[derive(Default, std::fmt::Debug, serde::Deserialize, serde::Serialize)]
#[serde(default)]
#[derive(Clone)]
pub struct LCSetting {
    pub inductance: f64,
    pub capacitance: f64,
    pub carrier_frequency: f64,
    pub clk_ticks_per_sample: usize,
    pub capacitor_bank_setting: isize,
}

#[derive(Default, serde::Deserialize, serde::Serialize)]
#[serde(default)]
#[derive(Clone)]
pub struct Coil {
    pub name: String,
    pub inductance: f64,
    pub possible_settings: Vec<LCSetting>,
}

impl Coil {
    fn calculate_possible_settings(&mut self) {
        self.possible_settings = Vec::new();

        for i in 1..(1 << config::AVAILABLE_CAPACITANCES.len()) {
            let mut capacitance: f64 = 0.0;
            for j in 0..config::AVAILABLE_CAPACITANCES.len() {
                capacitance += config::AVAILABLE_CAPACITANCES[j] * ((i >> j & 1) as f64);
            }

            let carrier_frequency_ideal =
                1.0 / (2.0 * PI * f64::sqrt(self.inductance * 1E-6 * capacitance * 1E-9));
            let clk_ticks_per_sample = f64::round(
                config::FPGA_FCLK as f64
                    / (carrier_frequency_ideal * config::SAMPLES_PER_CARRIER_PERIOD as f64),
            ) as usize;
            let carrier_frequency = config::FPGA_FCLK as f64
                / (clk_ticks_per_sample * config::SAMPLES_PER_CARRIER_PERIOD) as f64;

            if carrier_frequency < config::MAX_CARRIER_FREQUENCY {
                self.possible_settings.push(LCSetting {
                    inductance: self.inductance,
                    capacitance,
                    carrier_frequency,
                    clk_ticks_per_sample,
                    capacitor_bank_setting: i,
                });
            }
        }

        self.possible_settings
            .sort_by_key(|setting| setting.clk_ticks_per_sample);
        self.possible_settings.reverse();
    }
}

#[derive(serde::Deserialize, serde::Serialize)]
#[serde(default)]
pub struct ChannelControls {
    pub channel_id: String,
    pub enabled: bool,
    pub equal_currents: bool,
    pub current1: f64,
    pub current2: f64,
    pub selected_coil_name: String,
    pub lc_setting_index: usize,
    pub add_coil_dialog_open: bool,
    pub coil_being_made: Coil,
}

impl Default for ChannelControls {
    fn default() -> Self {
        Self {
            channel_id: "".to_string(),
            enabled: true,
            equal_currents: true,
            current1: 0.0,
            current2: 0.0,
            selected_coil_name: "".to_string(),
            lc_setting_index: 0,
            add_coil_dialog_open: false,
            coil_being_made: Coil::default(),
        }
    }
}

impl ChannelControls {
    fn add_coil_dialog(
        &mut self,
        ui: &mut egui::Ui,
        toasts: &mut egui_toast::Toasts,
        available_coils: &mut HashMap<String, Coil>,
    ) {
        egui::Window::new("Add Coil")
            .anchor(egui::Align2::CENTER_CENTER, (0.0, 0.0))
            .collapsible(false)
            .resizable(false)
            .title_bar(false)
            .show(ui.ctx(), |ui| {
                ui.set_width(250.0);
                ui.heading("Add new coil type");
                egui::Grid::new("add_coil_dialog_grid")
                    .num_columns(2)
                    .show(ui, |ui| {
                        ui.label("Name:");
                        ui.add_sized(
                            ui.available_size(),
                            egui::TextEdit::singleline(&mut self.coil_being_made.name)
                                .horizontal_align(egui::Align::Center),
                        );
                        ui.end_row();

                        ui.label("Inductance:");
                        ui.add_sized(
                            ui.available_size(),
                            egui::DragValue::new(&mut self.coil_being_made.inductance)
                                .suffix("uH")
                                .range(1.0..=1E6)
                                .fixed_decimals(3)
                                .speed(0.1),
                        );
                        ui.end_row();
                    });
                egui::Sides::new().show(
                    ui,
                    |_| {},
                    |ui| {
                        if ui.button("Save").clicked() {
                            if self.coil_being_made.name.is_empty() {
                                toasts.add(egui_toast::Toast {
                                    text: "Coil name cannot be empty".into(),
                                    kind: egui_toast::ToastKind::Error,
                                    options: egui_toast::ToastOptions::default()
                                        .duration_in_seconds(2.0)
                                        .show_progress(false),
                                    ..Default::default()
                                });
                            } else if available_coils.contains_key(&self.coil_being_made.name) {
                                toasts.add(egui_toast::Toast {
                                    text: "Coil name already exists".into(),
                                    kind: egui_toast::ToastKind::Error,
                                    options: egui_toast::ToastOptions::default()
                                        .duration_in_seconds(2.0)
                                        .show_progress(false),
                                    ..Default::default()
                                });
                            } else {
                                self.coil_being_made.calculate_possible_settings();
                                available_coils.insert(
                                    self.coil_being_made.name.clone(),
                                    self.coil_being_made.clone(),
                                );
                                self.selected_coil_name = self.coil_being_made.name.clone();
                                self.add_coil_dialog_open = false;
                            }
                        } else if ui.button("Cancel").clicked() {
                            self.add_coil_dialog_open = false;
                        }
                    },
                );
            });
    }

    fn coil_chooser(&mut self, ui: &mut ::egui::Ui, available_coils: &mut HashMap<String, Coil>) {
        ui.add_enabled(self.enabled, egui::Label::new("Coil type:"));
        if available_coils.len() > 0 {
            if !available_coils.contains_key(&self.selected_coil_name) {
                self.selected_coil_name = available_coils.keys().last().unwrap().clone();
            }
            ui.add_enabled_ui(self.enabled, |ui| {
                egui::ComboBox::new(format!("channel{0}_coil", self.channel_id), "")
                    .selected_text(&self.selected_coil_name)
                    .show_ui(ui, |ui| {
                        for key in available_coils.keys() {
                            ui.selectable_value(&mut self.selected_coil_name, key.clone(), key);
                        }
                    })
            });
        }
        ui.horizontal(|ui| {
            ui.add_enabled_ui(self.enabled, |ui| {
                if ui.button("+").clicked() {
                    self.coil_being_made = Coil::default();
                    self.add_coil_dialog_open = true;
                }
            });
            ui.add_enabled_ui(self.enabled, |ui| {
                if ui.button("🗑").clicked() {
                    available_coils.remove(&self.selected_coil_name);
                    if available_coils.len() > 0 {
                        self.selected_coil_name = available_coils.keys().last().unwrap().clone();
                    }
                }
            });
        });
    }

    fn carrier_frequency_chooser(
        &mut self,
        ui: &mut egui::Ui,
        available_coils: &mut HashMap<String, Coil>,
    ) {
        let selected_coil = &available_coils[&self.selected_coil_name];
        ui.add_enabled(self.enabled, egui::Label::new("Carrier frequency:"));
        ui.add_enabled(
            self.enabled,
            egui::Slider::new(
                &mut self.lc_setting_index,
                0..=selected_coil.possible_settings.len() - 1,
            )
            .show_value(false),
        );
        ui.add_enabled(
            self.enabled,
            egui::Label::new(format!(
                "{0:.3} kHz",
                selected_coil.possible_settings[self.lc_setting_index].carrier_frequency / 1000.0,
            )),
        );
    }

    fn current_chooser(&mut self, ui: &mut egui::Ui) {
        ui.add_enabled(self.enabled, egui::Label::new("Equal currents:"));
        ui.add_enabled(
            self.enabled,
            egui::Checkbox::new(&mut self.equal_currents, ""),
        );
        ui.end_row();

        ui.add_enabled(
            self.enabled,
            egui::Label::new(format!("Coil {id}1 current:", id = self.channel_id)),
        );
        ui.add_enabled(
            self.enabled,
            egui::Slider::new(&mut self.current1, 0.0..=config::MAX_CURRENT_SETPOINT).show_value(false),
        );
        ui.add_enabled(
            self.enabled,
            egui::Label::new(format!("{0:.2}", self.current1)),
        );
        ui.end_row();

        ui.add_enabled(
            self.enabled,
            egui::Label::new(format!("Coil {id}2 current:", id = self.channel_id)),
        );
        ui.add_enabled(
            self.enabled,
            egui::Slider::new(
                if self.equal_currents {
                    &mut self.current1
                } else {
                    &mut self.current2
                },
                0.0..=config::MAX_CURRENT_SETPOINT,
            )
            .show_value(false),
        );
        ui.add_enabled(
            self.enabled,
            egui::Label::new(format!(
                "{0:.2}",
                if self.equal_currents {
                    &mut self.current1
                } else {
                    &mut self.current2
                }
            )),
        );
        if self.enabled & self.equal_currents {
            self.current2 = self.current1;
        }
    }

    pub fn show(
        &mut self,
        ui: &mut egui::Ui,
        available_coils: &mut HashMap<String, Coil>,
        toasts: &mut egui_toast::Toasts,
    ) {
        egui::Grid::new(format!("channel{0}_controls", self.channel_id))
            .num_columns(3)
            .show(ui, |ui| {
                ui.label(format!("Channel {0}:", self.channel_id));
                ui.checkbox(&mut self.enabled, "");
                ui.end_row();

                let w = ui.style().spacing.slider_width;
                ui.style_mut().spacing.slider_width = 140.0;

                self.coil_chooser(ui, available_coils);
                ui.end_row();

                if available_coils.len() > 0 {
                    self.carrier_frequency_chooser(ui, available_coils);
                    ui.end_row();
                }

                self.current_chooser(ui);
                ui.end_row();

                ui.style_mut().spacing.slider_width = w;
            });
        if self.add_coil_dialog_open {
            self.add_coil_dialog(ui, toasts, available_coils);
        }
    }

    pub fn get_capacitor_bank_setting(
        &mut self,
        available_coils: &HashMap<String, Coil>,
    ) -> isize {
        available_coils[&self.selected_coil_name].possible_settings[self.lc_setting_index]
            .capacitor_bank_setting
    }
}
