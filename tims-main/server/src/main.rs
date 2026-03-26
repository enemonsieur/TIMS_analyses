mod capacitor_banks;
pub use capacitor_banks::*;

mod controller;
pub use controller::*;

mod machine_config;

mod power_supply;
pub use power_supply::*;

mod temperature_sensors;
pub use temperature_sensors::*;

mod server;
pub use server::*;

fn main() {
    let mut server = Server::new();
    server.start();
}
