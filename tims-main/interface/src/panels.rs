use crate::{
    capacitor_banks::CapacitorBanks, control_panel::ControlPanel, driver::Driver,
    status_panel::StatusPanel,
};

use std::fs::File;
use std::io::BufReader;
use std::io::BufWriter;
use std::io::Write;

#[derive(Default, serde::Deserialize, serde::Serialize)]
#[serde(default)]
pub struct Panels {
    control_panel: ControlPanel,
    status_panel: StatusPanel,
}

impl Panels {
    pub fn show(
        &mut self,
        ctx: &egui::Context,
        driver: &mut Driver,
        capacitor_banks: &mut CapacitorBanks,
        toasts: &mut egui_toast::Toasts,
        sound_stream: Option<&mut rodio::stream::OutputStream>,
    ) {
        egui::SidePanel::left("left_panel")
            .resizable(false)
            .show(&ctx, |ui| {
                self.control_panel.show(
                    ui,
                    driver,
                    capacitor_banks,
                    &self.status_panel,
                    toasts,
                    sound_stream,
                )
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            self.status_panel.show(ui, driver);
        });
    }

    pub fn to_file(&mut self, path: &str) {
        let file = File::create(path).unwrap();
        let mut writer = BufWriter::new(file);
        serde_json::to_writer_pretty(&mut writer, &self).unwrap();
        writer.flush().unwrap();
    }

    pub fn from_file(path: &str) -> Option<Panels> {
        if let Ok(file) = File::open(path) {
            if let Ok(p) = serde_json::from_reader(BufReader::new(file)) {
                Some(p)
            } else {
                None
            }
        } else {
            None
        }
    }
}
