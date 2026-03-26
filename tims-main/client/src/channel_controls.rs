use std::fmt::Display;

use egui::{ComboBox, Grid, Slider, Ui};
use protocols::{Coil, LCSetting, Signal, SignalSource};

use crate::{ChannelSettings, Resources, SignalSourceSelection};

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum ChannelID {
    A,
    B,
}

impl Display for ChannelID {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ChannelID::A => write!(f, "A"),
            ChannelID::B => write!(f, "B"),
        }
    }
}

pub struct ChannelControls {
    pub id: ChannelID,
}

impl ChannelControls {
    pub fn show(
        &mut self,
        settings: &mut ChannelSettings,
        resources: &mut Resources,
        signals: &Vec<Signal>,
        ui: &mut Ui,
    ) {
        let num_coils = match self.id {
            ChannelID::A => match resources.machine_config.num_coils {
                0 => 0,
                1 => 1,
                2 => 2,
                _ => 2,
            },
            ChannelID::B => match resources.machine_config.num_coils {
                0..=2 => 0,
                3 => 1,
                4 => 2,
                _ => 2,
            },
        };

        if num_coils == 0 {
            return;
        }

        Grid::new(format!("channel{}_controls", self.id))
            .num_columns(2)
            .min_col_width(ui.available_width() * 0.35)
            .show(ui, |ui| {
                ui.label(format!("Channel {}", self.id));
                ui.checkbox(&mut settings.enabled, "");
                ui.end_row();

                self.coil_controls(
                    settings.enabled,
                    &resources.machine_config.coils,
                    &mut settings.coil_idx,
                    ui,
                );
                ui.end_row();

                self.carrier_frequency_controls(
                    settings.enabled,
                    &resources.machine_config.coils[settings.coil_idx].settings,
                    &mut settings.coil_setting_idx,
                    ui,
                );
                ui.end_row();

                if num_coils >= 1 {
                    self.signal_source_controls(
                        settings.enabled,
                        signals.len(),
                        resources.machine_config.num_external_signal_sources,
                        &mut settings.amplitude1_source,
                        &format!("Coil {}1 amplitude", self.id),
                        ui,
                    );
                    ui.end_row();
                }

                if num_coils >= 2 {
                    self.signal_source_controls(
                        settings.enabled,
                        signals.len(),
                        resources.machine_config.num_external_signal_sources,
                        &mut settings.amplitude2_source,
                        &format!("Coil {}2 amplitude", self.id),
                        ui,
                    );
                    ui.end_row();

                    self.signal_source_controls(
                        settings.enabled,
                        signals.len(),
                        resources.machine_config.num_external_signal_sources,
                        &mut settings.modulation_source,
                        &format!("Channel {} modulation   ", self.id),
                        ui,
                    );
                    ui.end_row();
                }
            });
        ui.separator();
    }

    fn signal_source_controls(
        &mut self,
        enabled: bool,
        num_internal_signal_sources: usize,
        num_external_signal_sources: usize,
        source: &mut SignalSourceSelection,
        label: &str,
        ui: &mut Ui,
    ) {
        source.internal = usize::min(source.internal, num_internal_signal_sources - 1);
        source.external = usize::min(source.external, num_external_signal_sources - 1);

        if num_external_signal_sources == 0 {
            source.external_selected = false;
        }

        ui.label(label);
        ui.horizontal(|ui| {
            ui.add_enabled_ui(enabled, |ui| {
                ui.selectable_value(&mut source.external_selected, false, "Internal");
            });
            ui.add_enabled_ui(enabled && num_external_signal_sources > 0, |ui| {
                ui.selectable_value(&mut source.external_selected, true, "External");
            });
            ui.add_enabled_ui(enabled, |ui| {
                ComboBox::from_id_salt(label)
                    .width(ui.available_width())
                    .selected_text(source.selected().to_string())
                    .show_ui(ui, |ui| {
                        if source.external_selected {
                            for t in 0..num_external_signal_sources {
                                let v = SignalSource::External(t);
                                ui.selectable_value(&mut source.external, t, v.to_string());
                            }
                        } else {
                            for t in 0..num_internal_signal_sources {
                                let v = SignalSource::Internal(t);
                                ui.selectable_value(&mut source.internal, t, v.to_string());
                            }
                        }
                    });
            });
        });
    }

    fn coil_controls(
        &mut self,
        enabled: bool,
        coils: &Vec<Coil>,
        coil_idx: &mut usize,
        ui: &mut Ui,
    ) {
        if coils.is_empty() {
            log::error!("No valid coil definitions were found in machine configuration");
            log::error!("Panic exiting!");
        }
        *coil_idx = usize::min(*coil_idx, coils.len() - 1);

        ui.label("Coil");
        ui.add_enabled_ui(enabled, |ui| {
            ComboBox::new(format!("channel{0}_coil", self.id), "")
                .selected_text(&coils[*coil_idx].name)
                .show_ui(ui, |ui| {
                    for idx in 0..coils.len() {
                        ui.selectable_value(coil_idx, idx, coils[idx].name.clone());
                    }
                })
        });
    }
    fn carrier_frequency_controls(
        &mut self,
        enabled: bool,
        settings: &Vec<LCSetting>,
        setting_idx: &mut usize,
        ui: &mut Ui,
    ) {
        if settings.is_empty() {
            log::error!("No valid carrier frequencies were found in machine configuration");
            log::error!("Panic exiting!");
        }
        *setting_idx = usize::min(*setting_idx, settings.len() - 1);

        ui.label("Carrier frequency");
        ui.horizontal(|ui| {
            ui.spacing_mut().slider_width = ui.available_width() * 0.65;
            ui.add_enabled(
                enabled && settings.len() > 1,
                Slider::new(setting_idx, 0..=settings.len() - 1).show_value(false),
            );
            ui.label(format!(
                "{0:.3} kHz",
                settings[*setting_idx].carrier_frequency,
            ));
        });
    }
}
