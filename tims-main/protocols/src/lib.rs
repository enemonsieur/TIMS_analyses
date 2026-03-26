pub mod config;

mod controller_config;
pub use controller_config::*;

mod controller_status;
pub use controller_status::*;

mod signals;
pub use signals::*;

mod stimulation_protocol;
pub use stimulation_protocol::*;

mod machine_config;
pub use machine_config::*;

mod lcsettings;
pub use lcsettings::*;

mod messages;
pub use messages::*;

mod error;
pub use error::*;

// Number of bytes in a word
pub const W: usize = config::INTERFACE_WORD_NBITS / 8;

// Number of setpoint/monitor samples per packet
pub const N: usize = config::INTERFACE_DATA_NUM_SAMPLES;

// Number of setpoint/monitor channels
pub const M: usize = config::INTERFACE_DATA_NUM_CHANNELS;

// Number of configuration words
pub const C: usize = config::INTERFACE_CONFIG_NUM_WORDS;

// Number of bytes in each configuration parameters
pub const V: usize = config::INTERFACE_CONFIG_BIT_ALIGNMENT / 8;

// Total number of bytes in a packet
pub const PACKET_NBYTES: usize = config::INTERFACE_PACKET_NBYTES;
