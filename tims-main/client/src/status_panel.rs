use circular_buffer::CircularBuffer;
use egui::{TextStyle, Ui, Window};
use egui_plot::{Corner, Legend, Line, PlotBounds, PlotPoint, PlotPoints};

use crate::{Resources, Settings};

use protocols::{M, N, Signal, config};

// Monitor circular buffer length in samples
const L: usize = 20 * config::INTERFACE_SAMPLING_RATE as usize;

// Number of points per trace in monitor plot
const P: usize = 5000;

pub struct StatusPanel {
    data: [Box<CircularBuffer<L, f32>>; M],
    traces: [Vec<PlotPoint>; M],
    hold_plot: bool,
    subsampling_factor: usize,
    show_monitor_channel_selection_dialog: bool,
}

impl Default for StatusPanel {
    fn default() -> Self {
        Self {
            data: core::array::from_fn(|_| {
                let mut cb = CircularBuffer::<L, f32>::boxed();
                for _ in 0..L {
                    cb.push_back(0.0);
                }
                cb
            }),
            traces: core::array::from_fn(|_| {
                (0..P).map(|i| PlotPoint::new(i as f64, 0.0)).collect()
            }),
            hold_plot: false,
            subsampling_factor: 1,
            show_monitor_channel_selection_dialog: false,
        }
    }
}

impl StatusPanel {
    pub fn show(&mut self, settings: &mut Settings, resources: &mut Resources, ui: &mut Ui) {
        let server_status = resources.client.get_status();

        for entry in server_status {
            for status in entry.controller_status {
                for ch in 0..M {
                    for i in 0..N {
                        let v = Signal::f64(status.monitor_data.channels[ch].samples[i]);
                        self.data[ch].push_back(v as f32);
                    }
                }

                resources.session_progress = status.session_progress;
            }
        }

        if !self.hold_plot {
            for ch in 0..M {
                for i in 0..P {
                    self.traces[ch][i].x = -((P - i - 1) as f64)
                        / (config::INTERFACE_SAMPLING_RATE as f64 / self.subsampling_factor as f64);

                    let y = self.data[ch][L + (i - P) * self.subsampling_factor] as f64;

                    self.traces[ch][i].y = y;
                }
            }
        }

        ui.vertical(|ui| {
            egui_plot::Plot::new("Monitor")
                .allow_zoom([true, false])
                .show_x(false)
                .show_y(false)
                .allow_drag([true, false])
                .height(ui.available_height() * 0.85)
                .x_axis_label("Time (seconds)")
                .legend(
                    Legend::default()
                        .position(Corner::LeftTop)
                        .text_style(TextStyle::Monospace)
                        .follow_insertion_order(true),
                )
                .show(ui, |plot_ui| {
                    plot_ui.set_plot_bounds(PlotBounds::from_min_max([0.0, -1.2], [0.0, 1.2]));
                    plot_ui.set_auto_bounds(egui::Vec2b::new(true, false));
                    for ch in 0..M {
                        if settings.monitor_trace_visible[ch] {
                            plot_ui.line(
                                Line::new(
                                    config::MONITOR_TRACE_NAMES[ch],
                                    PlotPoints::Borrowed(&self.traces[ch]),
                                )
                                .name(config::MONITOR_TRACE_NAMES[ch])
                                .color(egui::epaint::Hsva::new(
                                    ch as f32 / M as f32,
                                    1.0,
                                    1.0,
                                    1.0,
                                )),
                            );
                        }
                    }
                });

            ui.style_mut().spacing.button_padding = egui::Vec2::new(10.0, 10.0);
            ui.horizontal(|ui| {
                ui.label("Monitor time range:");
                ui.add_enabled(
                    !self.hold_plot,
                    egui::Slider::new(&mut self.subsampling_factor, 1usize..=(L / P))
                        .show_value(false),
                );
                ui.add_space(ui.available_width() * 0.60);
                if ui.button("Monitor channels").clicked() {
                    self.show_monitor_channel_selection_dialog = true;
                }

                if ui
                    .add(egui::Button::new("Hold").selected(self.hold_plot))
                    .clicked()
                {
                    self.hold_plot = !self.hold_plot;
                }
            });
        });

        if self.show_monitor_channel_selection_dialog {
            Window::new("Monitor channel selection")
                .resizable(false)
                .collapsible(false)
                .show(ui.ctx(), |ui| {
                    ui.vertical_centered(|ui| {
                        egui::Grid::new("monitor_channel_selection_grid")
                            .num_columns(config::MONITOR_TRACE_NAMES.len() / 2)
                            .show(ui, |ui| {
                                for i in 0..M {
                                    ui.checkbox(
                                        &mut settings.monitor_trace_visible[i],
                                        format!(
                                            "{} ({})",
                                            config::MONITOR_TRACE_DESCRIPTIONS[i],
                                            config::MONITOR_TRACE_NAMES[i]
                                        ),
                                    );

                                    if (i + 1) % 2 == 0 {
                                        ui.end_row();
                                    }
                                }
                            });
                        ui.style_mut().spacing.button_padding = egui::Vec2::new(10.0, 10.0);
                        if ui.button("Close").clicked() {
                            self.show_monitor_channel_selection_dialog = false;
                        }
                    });
                });
        }
    }
}
