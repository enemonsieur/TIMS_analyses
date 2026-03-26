use eframe::{App, CreationContext, Frame};
use egui::{Align2, Context};
use egui_toast::{Toast, ToastKind, ToastOptions, Toasts};
use protocols::MachineConfig;

use crate::{Client, Panels, Settings};

pub struct Resources {
    pub client: Client,
    pub toasts: Toasts,
    pub machine_config: MachineConfig,
    pub session_progress: f64,
}

pub struct MainApp {
    settings: Settings,
    resources: Resources,
    panels: Panels,
}

impl MainApp {
    fn new(_cc: &CreationContext<'_>) -> Self {
        let mut settings = Settings::default();
        settings = match settings.load() {
            Ok(s) => s,
            Err(e) => {
                log::warn!("Error while loading settings from file: {e}");
                log::warn!("Using default settings instead");
                settings
            },
        };

        let resources = Resources {
            client: Client::new(settings.server_ip.clone()),
            toasts: Toasts::new().anchor(Align2::CENTER_BOTTOM, (10.0, 10.0)),
            machine_config: MachineConfig::default(),
            session_progress: 0.0,
        };

        return MainApp {
            settings,
            resources,
            panels: Panels::default(),
        };
    }

    pub fn run() {
        eframe::run_native(
            "TIMS Client",
            eframe::NativeOptions {
                viewport: egui::ViewportBuilder::default().with_maximized(true),
                ..Default::default()
            },
            Box::new(|cc| Ok(Box::new(MainApp::new(cc)))),
        )
        .unwrap();
    }
}

impl App for MainApp {
    fn update(&mut self, ctx: &Context, _frame: &mut Frame) {
        self.panels
            .show(&mut self.settings, &mut self.resources, ctx);
        self.resources.toasts.show(ctx);
        ctx.request_repaint();

        if let Err(e) = self.settings.save() {
            log::warn!("Error while saving settings to file: {e}");
        }
    }
}

impl Resources {
    pub fn show_toast(&mut self, text: &String, kind: ToastKind) {
        self.toasts.add(Toast {
            text: text.into(),
            kind,
            options: ToastOptions::default()
                .duration_in_seconds(3.0)
                .show_progress(false),
            ..Default::default()
        });
    }
}
