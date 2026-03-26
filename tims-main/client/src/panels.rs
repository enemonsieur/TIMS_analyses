use egui::{CentralPanel, Context, SidePanel};

use crate::{ControlPanel, Resources, Settings, StatusPanel};

#[derive(Default)]
pub struct Panels {
    pub control_panel: ControlPanel,
    pub status_panel: StatusPanel,
}

impl Panels {
    pub fn show(&mut self, settings: &mut Settings, resources: &mut Resources, ctx: &Context) {
        SidePanel::left("left_panel")
            .resizable(false)
            .exact_width(settings.control_panel_width + settings.panel_width_margin)
            .show(&ctx, |ui| {
                self.control_panel.show(settings, resources, ui);
            });

        CentralPanel::default().show(ctx, |ui| {
            self.status_panel.show(settings, resources, ui);
        });
    }
}
