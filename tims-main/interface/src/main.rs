mod capacitor_banks;
mod channel_controls;
mod config;
mod control_panel;
mod driver;
mod panels;
mod power_supply;
mod protocol;
mod status_panel;
mod temperature_sensors;

use driver::Driver;
use panels::Panels;

struct MainApp {
    driver: Driver,
    capacitor_banks: capacitor_banks::CapacitorBanks,
    panels: Panels,
    keyboard: egui_keyboard::Keyboard,
    toasts: egui_toast::Toasts,
    sound_stream: Option<rodio::stream::OutputStream>,
    last_settings_save_time: std::time::Instant
}

impl MainApp {
    pub fn new(cc: &eframe::CreationContext<'_>) -> Self {
        cc.egui_ctx.set_pixels_per_point(0.80);

        std::fs::create_dir_all(config::SETTINGS_DIR).unwrap();
        std::fs::create_dir_all(config::PROTOCOLS_DIR).unwrap();

        let panels = Panels::from_file(config::SETTINGS_FILEPATH).unwrap_or(
            Panels::from_file(config::SETTINGS_DEFAULT_FILEPATH).unwrap_or(
                Panels::default())
        );

        let sound_stream = if 
            config::SOUND_DEVICE_AVAILABLE == 1 &&
             let Ok(ss) = rodio::OutputStreamBuilder::open_default_stream() {
            Some(ss)
        }
        else { None };

        let app = MainApp {
            driver: Driver::new(),
            capacitor_banks: capacitor_banks::CapacitorBanks::new(),
            panels: panels,
            keyboard: egui_keyboard::Keyboard::default(),
            toasts: egui_toast::Toasts::new().anchor(egui::Align2::CENTER_BOTTOM, (10.0, 10.0)),
            sound_stream: sound_stream,
            last_settings_save_time: std::time::Instant::now()
        };

        return app;
    }
}

impl eframe::App for MainApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.keyboard.pump_events(ctx);
        self.panels.show(
            ctx,
            &mut self.driver,
            &mut self.capacitor_banks,
            &mut self.toasts,
            self.sound_stream.as_mut(),
        );
        self.keyboard.show(ctx);
        self.toasts.show(ctx);

        if self.last_settings_save_time.elapsed() > std::time::Duration::from_secs(2) {
            self.panels.to_file(config::SETTINGS_FILEPATH);
            self.last_settings_save_time = std::time::Instant::now();
        }
    }
}

#[cfg(not(target_arch = "wasm32"))]
fn main() {
    if config::PROGRAM_DRIVER_ON_STARTUP == 1 {
        std::process::Command::new("openFPGALoader")
            .arg("-b")
            .arg("cmoda7_35t")
            .arg(config::BITSTREAM_FILEPATH)
            .status()
            .expect("Failed to load FPGA bitstream");
    }

    eframe::run_native(
        "TIMS",
        eframe::NativeOptions {
            viewport: egui::ViewportBuilder::default().with_fullscreen(true),
            ..Default::default()
        },
        Box::new(|cc| Ok(Box::new(MainApp::new(cc)))),
    )
    .unwrap();
}

#[cfg(target_arch = "wasm32")]
fn main() {
    use eframe::wasm_bindgen::JsCast as _;

    // Redirect `log` message to `console.log` and friends:
    eframe::WebLogger::init(log::LevelFilter::Debug).ok();

    let web_options = eframe::WebOptions::default();

    wasm_bindgen_futures::spawn_local(async {
        let document = web_sys::window()
            .expect("No window")
            .document()
            .expect("No document");

        let canvas = document
            .get_element_by_id("the_canvas_id")
            .expect("Failed to find the_canvas_id")
            .dyn_into::<web_sys::HtmlCanvasElement>()
            .expect("the_canvas_id was not a HtmlCanvasElement");

        let start_result = eframe::WebRunner::new()
            .start(
                canvas,
                web_options,
                Box::new(|cc| Ok(Box::new(MainApp::new(cc)))),
            )
            .await;

        // Remove the loading text and spinner:
        if let Some(loading_text) = document.get_element_by_id("loading_text") {
            match start_result {
                Ok(_) => {
                    loading_text.remove();
                }
                Err(e) => {
                    loading_text.set_inner_html(
                        "<p> The app has crashed. See the developer console for details. </p>",
                    );
                    panic!("Failed to start eframe: {e:?}");
                }
            }
        }
    });
}
