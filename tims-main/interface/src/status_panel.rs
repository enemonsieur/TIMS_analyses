use circular_buffer::CircularBuffer;

use crate::{
    config,
    driver::{self, Driver},
    temperature_sensors,
};

// Number of setpoint/monitor samples per packet
const N: usize = config::INTERFACE_DATA_NUM_SAMPLES as usize;
// Number of setpoint/monitor channels
const M: usize = config::INTERFACE_DATA_NUM_CHANNELS as usize;
// Monitor circular buffer length in samples
const L: usize = 20 * config::INTERFACE_SAMPLING_RATE as usize;
// Number of points per trace in monitor plot
const P: usize = 5000;

const TRACE_NAMES: [&str; 16] = [
    "Ma", "MSa", "Ia₁", "ISa₁", "Ia₂", "ISa₂", "Mb", "MSb", "Ib₁", "ISb₁", "Ib₂", "ISb₂", "F1",
    "F2", "F3", "F4",
];

const MAX_CURRENT_WINDOW_DURATION: f64 = 1.0;

const TRACE_DESCRIPTIONS: [&str; 16] = [
    "Actual modulation in channel A",
    "Setpoint signal for channel A modulation",
    "Actual amplitude of coil A1 current",
    "Setpoint signal for amplitude of coil A1 current",
    "Actual amplitude of coil A2 current",
    "Setpoint signal for amplitude of coil A2 current",
    "Actual modulation in channel B",
    "Setpoint signal for channel B modulation",
    "Actual amplitude of coil B1 current",
    "Setpoint signal for amplitude of coil B1 current",
    "Actual amplitude of coil B2 current",
    "Setpoint signal for amplitude of coil B2 current",
    "F1",
    "F2",
    "F3",
    "F4",
];

#[derive(serde::Deserialize, serde::Serialize)]
#[serde(default)]
pub struct StatusPanel {
    #[serde(skip)]
    monitor_channels: [Box<CircularBuffer<L, f32>>; M],

    #[serde(skip)]
    pub session_progress: f64,

    #[serde(skip)]
    pub temperature: [f64; temperature_sensors::NUM_SENSORS],

    #[serde(skip)]
    pub flow_rate: [f64; driver::NUM_FLOW_RATE_SENSORS],

    #[serde(skip)]
    pub supply_power: f64,
    #[serde(skip)]
    pub supply_current: f64,

    #[serde(skip)]
    pub max_currents: [f64; 4],

    #[serde(skip)]
    traces: [Vec<egui_plot::PlotPoint>; M],

    #[serde(skip)]
    show_monitor_channel_selection_dialog: bool,

    #[serde(skip)]
    hold_plot: bool,

    subsampling_factor: usize,

    trace_visible: [bool; TRACE_NAMES.len()],
}

impl Default for StatusPanel {
    fn default() -> Self {
        StatusPanel {
            monitor_channels: core::array::from_fn(|_| {
                let mut cb = CircularBuffer::<L, f32>::boxed();
                for _ in 0..L {
                    cb.push_back(0.0);
                }
                cb
            }),
            session_progress: 0.0,
            temperature: [0.0; temperature_sensors::NUM_SENSORS],
            flow_rate: [f64::NAN; driver::NUM_FLOW_RATE_SENSORS],
            supply_current: 0.0,
            supply_power: 0.0,
            max_currents: [0.0; 4],
            traces: core::array::from_fn(|_| {
                let mut v = Vec::<egui_plot::PlotPoint>::new();
                for i in 0..P {
                    v.push(egui_plot::PlotPoint {
                        x: i as f64,
                        y: 0.0,
                    });
                }
                v
            }),
            hold_plot: false,
            subsampling_factor: 1,
            show_monitor_channel_selection_dialog: false,
            trace_visible: [true; TRACE_NAMES.len()],
        }
    }
}

impl StatusPanel {
    pub fn show(&mut self, ui: &mut egui::Ui, driver: &mut Driver) {
        for status in driver.status_receiver.try_iter() {
            self.session_progress = status.session_progress;
            self.temperature = status.temperature;
            self.flow_rate = status.flow_rate;
            self.supply_current = status.supply_current;
            self.supply_power = status.supply_power;
            for ch in 0..M {
                for i in 0..N {
                    self.monitor_channels[ch].push_back(status.monitor_channels[ch][i]);
                }
            }
        }

        if !self.hold_plot {
            for ch in 0..TRACE_NAMES.len() {
                for i in 0..P {
                    self.traces[ch][i].x = -((P - i - 1) as f64)
                        / (config::INTERFACE_SAMPLING_RATE as f64 / self.subsampling_factor as f64);

                    let y = self.monitor_channels[ch][L + (i - P) * self.subsampling_factor] as f64;

                    self.traces[ch][i].y = y;
                }
            }

            for i in 0..P {
                self.traces[0][i].y = self.traces[3][i].y
                    * f64::cos(self.traces[0][i].y * std::f64::consts::PI / 2.0);
                self.traces[6][i].y = self.traces[9][i].y
                    * f64::cos(self.traces[6][i].y * std::f64::consts::PI / 2.0);

                self.traces[1][i].y *= self.traces[3][i].y;
                self.traces[7][i].y *= self.traces[9][i].y;
            }

            self.max_currents = [0.0; 4];
            let max_current_window_start = P
                - (MAX_CURRENT_WINDOW_DURATION * config::INTERFACE_SAMPLING_RATE as f64
                    / self.subsampling_factor as f64) as usize;
            for i in max_current_window_start..P {
                self.max_currents[0] = f64::max(self.max_currents[0], self.traces[2][i].y);
                self.max_currents[1] = f64::max(self.max_currents[1], self.traces[4][i].y);
                self.max_currents[2] = f64::max(self.max_currents[2], self.traces[8][i].y);
                self.max_currents[3] = f64::max(self.max_currents[3], self.traces[10][i].y);
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
                    egui_plot::Legend::default()
                        .position(egui_plot::Corner::LeftTop)
                        .text_style(egui::TextStyle::Monospace)
                        .follow_insertion_order(true),
                )
                .show(ui, |plot_ui| {
                    plot_ui.set_plot_bounds(egui_plot::PlotBounds::from_min_max(
                        [0.0, -1.2],
                        [0.0, 1.2],
                    ));
                    plot_ui.set_auto_bounds(egui::Vec2b::new(true, false));
                    for ch in 0..TRACE_NAMES.len() {
                        if self.trace_visible[ch] {
                            plot_ui.line(
                                egui_plot::Line::new(
                                    TRACE_NAMES[ch],
                                    egui_plot::PlotPoints::Borrowed(&self.traces[ch]),
                                )
                                .name(TRACE_NAMES[ch])
                                .color(egui::epaint::Hsva::new(
                                    ch as f32 / TRACE_NAMES.len() as f32,
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

                // if ui.selectable_label(self.hold_plot, "Hold").clicked() {
                if ui
                    .add(egui::Button::new("Hold").selected(self.hold_plot))
                    .clicked()
                {
                    self.hold_plot = !self.hold_plot;
                }
            });

            egui::Grid::new("sensor_date_grid")
                .num_columns(4)
                .min_col_width(100.0)
                .show(ui, |ui| {
                    ui.label("Temperature X1:");
                    ui.label(format!("{:0.1} °C", self.temperature[0]));
                    ui.label("Temperature X2:");
                    ui.label(format!("{:0.1} °C", self.temperature[1]));
                    ui.end_row();

                    ui.label("Flow X1:");
                    ui.label(format!("{:0.1}", self.flow_rate[0]));
                    ui.label("Flow X2:");
                    ui.label(format!("{:0.1}", self.flow_rate[1]));
                    ui.end_row();

                    ui.label("Supply current:");
                    ui.label(format!("{:0.1} A", self.supply_current));
                    ui.label("Supply power:");
                    ui.label(format!("{:0.1} W", self.supply_power));
                    ui.end_row();
                });
        });

        if self.show_monitor_channel_selection_dialog {
            egui::Window::new("Monitor channel selection")
                .resizable(false)
                .collapsible(false)
                .show(ui.ctx(), |ui| {
                    ui.vertical_centered(|ui| {
                        egui::Grid::new("monitor_channel_selection_grid")
                            .num_columns(TRACE_NAMES.len() / 2)
                            .show(ui, |ui| {
                                for i in 0..TRACE_NAMES.len() {
                                    ui.checkbox(
                                        &mut self.trace_visible[i],
                                        format!("{} ({})", TRACE_DESCRIPTIONS[i], TRACE_NAMES[i]),
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

        ui.ctx().request_repaint();
    }
}
