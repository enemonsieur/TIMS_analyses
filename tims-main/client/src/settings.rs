use protocols::{ControllerConfig, M, MachineConfig, Signal, SignalSource, StimulationProtocol};
use serde::{Deserialize, Serialize};
use std::{
    env, error,
    fs::{self, File},
    io::{BufReader, BufWriter, Write},
    path::PathBuf,
    time::Instant,
};

use app_dirs2::{AppDataType, AppInfo, get_app_root};

const APP_INFO: AppInfo = AppInfo {
    name: "TIMSClient",
    author: "Khaled Nasr",
};

type Result<T> = std::result::Result<T, Box<dyn error::Error>>;

#[derive(Default, Copy, Clone, Deserialize, Serialize, Debug)]
#[serde(default)]
pub struct SignalSourceSelection {
    pub internal: usize,
    pub external: usize,
    pub external_selected: bool,
}

#[derive(Default, Copy, Clone, Deserialize, Serialize, Debug)]
#[serde(default)]
pub struct ChannelSettings {
    pub enabled: bool,
    pub amplitude1_source: SignalSourceSelection,
    pub amplitude2_source: SignalSourceSelection,
    pub modulation_source: SignalSourceSelection,
    pub coil_idx: usize,
    pub coil_setting_idx: usize,
}

#[derive(Clone, Deserialize, Serialize, Debug)]
#[serde(default)]
pub struct Settings {
    pub server_ip: String,
    pub running_on_target_machine: bool,

    pub settings_filepath: Option<PathBuf>,
    pub settings_save_interval: u64,

    #[serde(skip)]
    pub last_save_time: Instant,

    pub large_button_size: [f32; 2],
    pub large_button_font_size: f32,
    pub large_button_corner_radius: f32,
    pub large_label_font_size: f32,
    pub panel_width_margin: f32,
    pub control_panel_width: f32,

    pub intensity: f64,
    pub session_duration: f64,
    pub signals: Vec<Signal>,
    pub channel_a_settings: ChannelSettings,
    pub channel_b_settings: ChannelSettings,
    pub monitor_trace_visible: [bool; M],
}

impl Default for Settings {
    fn default() -> Self {
        let running_on_target_machine = env::var("TIMS_TARGET_MACHINE").is_ok();
        let data_dir = Settings::get_data_dir();

        Self {
            server_ip: match running_on_target_machine {
                true => "127.0.0.1:8080".to_string(),
                false => "192.168.14.5:8080".to_string(),
            },
            running_on_target_machine,

            settings_filepath: Settings::get_settings_path(&data_dir),
            settings_save_interval: 3,
            last_save_time: Instant::now(),

            large_button_size: [100.0, 40.0],
            large_button_font_size: 15.0,
            large_button_corner_radius: 10.0,
            large_label_font_size: 15.0,
            panel_width_margin: 36.0,
            control_panel_width: 380.0,

            intensity: 0.0,
            session_duration: 60.0,
            signals: vec![Signal::default()],
            channel_a_settings: ChannelSettings {
                enabled: true,
                ..Default::default()
            },
            channel_b_settings: ChannelSettings::default(),
            monitor_trace_visible: [false; M],
        }
    }
}

impl SignalSourceSelection {
    pub fn selected(&self) -> SignalSource {
        match self.external_selected {
            false => SignalSource::Internal(self.internal),
            true => SignalSource::External(self.external),
        }
    }
}

impl Settings {
    pub fn to_stimulation_protocol(&self) -> Result<StimulationProtocol> {
        Ok(StimulationProtocol::new(
            self.session_duration,
            self.signals.clone(),
            self.channel_a_settings.amplitude1_source.internal,
            self.channel_a_settings.amplitude2_source.internal,
            self.channel_b_settings.amplitude1_source.internal,
            self.channel_b_settings.amplitude2_source.internal,
            self.channel_a_settings.modulation_source.internal,
            self.channel_b_settings.modulation_source.internal,
        )?)
    }

    pub fn to_controller_config(
        &self,
        mconf: &MachineConfig,
        play_protocol: bool,
        stim: bool,
    ) -> Result<ControllerConfig> {
        Ok(ControllerConfig {
            system_enabled: true,
            controller_enabled_a: stim && self.channel_a_settings.enabled,
            controller_enabled_b: stim && self.channel_b_settings.enabled,
            play_protocol,
            lc_setting_a: mconf.coils[self.channel_a_settings.coil_idx].settings
                [self.channel_a_settings.coil_setting_idx],
            lc_setting_b: mconf.coils[self.channel_a_settings.coil_idx].settings
                [self.channel_a_settings.coil_setting_idx],
            p_factor: 4.0,
            i_factor: 0.05,
            intensity_a1: mconf.max_intensity_setpoint * self.intensity,
            intensity_a2: mconf.max_intensity_setpoint * self.intensity,
            intensity_b1: mconf.max_intensity_setpoint * self.intensity,
            intensity_b2: mconf.max_intensity_setpoint * self.intensity,
            amplitude_a1_source: self.channel_a_settings.amplitude1_source.selected(),
            amplitude_a2_source: self.channel_a_settings.amplitude2_source.selected(),
            amplitude_b1_source: self.channel_b_settings.amplitude1_source.selected(),
            amplitude_b2_source: self.channel_b_settings.amplitude2_source.selected(),
            modulation_a_source: self.channel_a_settings.modulation_source.selected(),
            modulation_b_source: self.channel_b_settings.modulation_source.selected(),
        })
    }

    pub fn load(&mut self) -> Result<Settings> {
        if let Some(path) = self.settings_filepath.clone() {
            Ok(serde_json::from_reader(BufReader::new(File::open(path)?))?)
        } else {
            Ok(self.clone())
        }
    }

    pub fn save(&mut self) -> Result<()> {
        if self.last_save_time.elapsed().as_secs() < self.settings_save_interval {
            return Ok(());
        }

        if let Some(path) = self.settings_filepath.clone() {
            let file = File::create(path)?;
            let mut writer = BufWriter::new(file);
            serde_json::to_writer_pretty(&mut writer, &self)?;
            writer.flush()?;
            self.last_save_time = Instant::now();
            Ok(())
        } else {
            Ok(())
        }
    }

    fn get_data_dir() -> Option<PathBuf> {
        match get_app_root(AppDataType::UserConfig, &APP_INFO) {
            Ok(dir) => match fs::create_dir_all(dir.clone()) {
                Ok(()) => Some(dir),
                Err(e) => {
                    log::warn!("Unable to access application data directory {dir:?}: {e}");
                    None
                }
            },
            Err(e) => {
                log::warn!("Unable to find application data directory: {e}");
                None
            }
        }
    }

    fn get_settings_path(data_dir: &Option<PathBuf>) -> Option<PathBuf> {
        match data_dir {
            Some(dir) => {
                let path = dir.join("settings.json");
                log::info!("Loading and saving data from: {path:?}");
                Some(path)
            }
            None => {
                log::warn!("No settings file path could be found");
                log::warn!("Saving and loading application settings will be disabled");
                None
            }
        }
    }
}
