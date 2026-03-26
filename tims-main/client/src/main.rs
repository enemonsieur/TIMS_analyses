mod client;
pub use crate::client::*;

mod app;
pub use crate::app::*;

mod settings;
pub use crate::settings::*;

mod panels;
pub use crate::panels::*;

mod control_panel;
pub use crate::control_panel::*;

mod status_panel;
pub use crate::status_panel::*;

mod channel_controls;
pub use crate::channel_controls::*;

mod signal_controls;
pub use crate::signal_controls::*;

fn main()  {
    env_logger::init();
    MainApp::run();
}
