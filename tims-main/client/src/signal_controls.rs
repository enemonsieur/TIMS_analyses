use crate::{Resources, Settings};
use egui::{ComboBox, Grid, Slider, Ui};
use protocols::Signal;
use strum::IntoEnumIterator;

pub struct SignalControls {}

impl SignalControls {
    pub fn show(&mut self, settings: &mut Settings, _resources: &mut Resources, ui: &mut Ui) {
        let mut idx_to_delete = None;

        for i in 0..settings.signals.len() {
            Grid::new(format!("signal_controls_{i}"))
                .num_columns(3)
                .min_col_width(settings.control_panel_width * 0.4)
                .show(ui, |ui| {
                    ui.spacing_mut().slider_width = settings.control_panel_width * 0.45;
                    if let Some(idx) = self.show_signal(&mut settings.signals, i, ui) {
                        idx_to_delete = Some(idx);
                    }
                });

            ui.separator();
        }

        ui.vertical_centered(|ui| {
            if ui.button("Add new internal signal").clicked() {
                settings.signals.push(Signal::default());
            }
        });

        if let Some(idx) = idx_to_delete {
            settings.signals.remove(idx);
        }
    }

    fn show_signal(&mut self, signals: &mut Vec<Signal>, idx: usize, ui: &mut Ui) -> Option<usize> {
        let mut idx_to_delete = None;
        let num_signals = signals.len();

        ui.label(format!("Internal signal S{idx}"));

        ui.horizontal(|ui| {
            ComboBox::from_id_salt(format!("internal_signal_{idx}"))
                .selected_text(signals[idx].to_string())
                .show_ui(ui, |ui| {
                    for v in Signal::iter() {
                        if !matches!(v, Signal::Arbitrary(_))
                            && !(idx == 0 && matches!(v, Signal::MixedSignal(_)))
                        {
                            ui.selectable_value(&mut signals[idx], v.clone(), v.to_string());
                        }
                    }
                });

            if idx > 0 && ui.button("Delete").clicked() {
                idx_to_delete = Some(idx);
            }
        });
        ui.end_row();

        match &mut signals[idx] {
            Signal::Constant(p) => {
                ui.label("Value");
                ui.add(Slider::new(&mut p.value, 0.0..=1.0));
                ui.end_row();
            }

            Signal::Sine(p) => {
                ui.label("Amplitude");
                ui.add(Slider::new(&mut p.amplitude, 0.0..=1.0));
                ui.end_row();

                ui.label("Frequency (Hz)");
                ui.add(Slider::new(&mut p.frequency, 0.01..=200.0));
                ui.end_row();

                ui.label("Phase (Degrees)");
                ui.add(Slider::new(&mut p.phase, 0.0..=360.0));
                ui.end_row();

                ui.label("Depth");
                ui.add(Slider::new(&mut p.depth, 0.0..=1.0));
                ui.end_row();
            }

            Signal::Ramp(p) => {
                ui.label("Peak value");
                ui.add(Slider::new(&mut p.peak, 0.0..=1.0));
                ui.end_row();

                ui.label("Ramp up duration (s)");
                ui.add(Slider::new(&mut p.up_duration, 0.01..=200.0));
                ui.end_row();

                ui.label("Ramp down duration");
                ui.add(Slider::new(&mut p.down_duration, 0.0..=200.0));
                ui.end_row();
            }

            Signal::MixedSignal(p) => {
                p.a_idx = usize::min(p.a_idx, num_signals - 1);
                p.b_idx = usize::min(p.b_idx, num_signals - 1);
                if p.a_idx == idx { p.a_idx = 0 }
                if p.b_idx == idx { p.b_idx = 0 }

                ui.label("First signal");
                ComboBox::from_id_salt(format!("mixed_signal_a_{idx}"))
                    .selected_text(format!("Internal Signal S{}", p.a_idx))
                    .show_ui(ui, |ui| {
                        for i in 0..num_signals {
                            if i != idx {
                                ui.selectable_value(
                                    &mut p.a_idx,
                                    i,
                                    format!("Internal Signal S{i}"),
                                );
                            }
                        }
                    });
                ui.end_row();

                ui.label("Second signal");
                ComboBox::from_id_salt(format!("mixed_signal_b_{idx}"))
                    .selected_text(format!("Internal Signal S{}", p.b_idx))
                    .show_ui(ui, |ui| {
                        for i in 0..num_signals {
                            if i != idx {
                                ui.selectable_value(
                                    &mut p.b_idx,
                                    i,
                                    format!("Internal Signal S{i}"),
                                );
                            }
                        }
                    });
                ui.end_row();
            }

            _ => {}
        }

        idx_to_delete
    }
}
