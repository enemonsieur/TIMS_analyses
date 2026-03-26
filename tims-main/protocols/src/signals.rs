use std::f64::consts::PI;

use serde::{Deserialize, Serialize};
use strum::EnumIter;

use crate::config;

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug, EnumIter)]
pub enum Signal {
    Constant(ConstantSignalParams),
    Sine(SineSignalParams),
    Ramp(RampSignalParams),
    MixedSignal(MixedSignalParams),
    Arbitrary(ArbitrarySignalParams),
}

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct ConstantSignalParams {
    pub value: f64,
}

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct SineSignalParams {
    pub amplitude: f64,
    pub frequency: f64,
    pub phase: f64,
    pub depth: f64,
}

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct RampSignalParams {
    pub peak: f64,
    pub up_duration: f64,
    pub down_duration: f64,
}

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct MixedSignalParams {
    pub a_idx: usize,
    pub b_idx: usize,
}

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct ArbitrarySignalParams {
    pub samples: Vec<i16>,
}

impl Default for Signal {
    fn default() -> Self {
        Signal::Constant(ConstantSignalParams { value: 0.0 })
    }
}

impl Default for ConstantSignalParams {
    fn default() -> Self {
        Self { value: 1.0 }
    }
}

impl Default for SineSignalParams {
    fn default() -> Self {
        Self {
            amplitude: 1.0,
            frequency: 10.0,
            phase: 0.0,
            depth: 1.0,
        }
    }
}

impl Default for RampSignalParams {
    fn default() -> Self {
        Self {
            up_duration: 10.0,
            down_duration: 10.0,
            peak: 1.0,
        }
    }
}

impl Signal {
    pub fn compute(&self, duration: f64, other_signals: &Vec<Signal>) -> Vec<i16> {
        let num_samples = Signal::duration_to_num_samples(duration);
        match self {
            Signal::Constant(p) => vec![Signal::fp16(p.value); num_samples],

            Signal::Sine(p) => {
                let (a, f, mut p, d) = (p.amplitude, p.frequency, p.phase, p.depth);
                p = PI * p / 180.0;

                (0..num_samples)
                    .map(|i| {
                        let t = i as f64 / config::INTERFACE_SAMPLING_RATE as f64;
                        let m =
                            0.5 * d * (f64::sin(p + 2.0 * PI * f * t - PI / 2.0) + 1.0) + (1.0 - d);
                        Signal::fp16(a * m)
                    })
                    .collect()
            }

            Signal::Ramp(p) => (0..num_samples)
                .map(|i| {
                    let t = i as f64 / config::INTERFACE_SAMPLING_RATE as f64;

                    let t1 = p.up_duration;
                    let t2 = duration - p.down_duration;

                    if t < t1 {
                        Signal::fp16(p.peak * t / p.up_duration)
                    } else if t < t2 {
                        Signal::fp16(p.peak)
                    } else {
                        Signal::fp16(p.peak * (1.0 - (t - t2) / p.down_duration))
                    }
                })
                .collect(),

            Signal::MixedSignal(p) => {
                if usize::max(p.a_idx, p.b_idx) > other_signals.len() - 1 {
                    log::error!(
                        "Attempted to refer to a non-existing signal in compund signal definition"
                    );
                    log::warn!("Setting invalid signal to zero");
                    vec![0; num_samples]
                } else {
                    let a = other_signals[p.a_idx].compute(duration, other_signals);
                    let b = other_signals[p.b_idx].compute(duration, other_signals);
                    (0..num_samples)
                        .map(|i| Signal::fp16(Signal::f64(a[i]) * Signal::f64(b[i])))
                        .collect()
                }
            }

            Self::Arbitrary(p) => (0..num_samples)
                .map(|i| match i < p.samples.len() {
                    true => p.samples[i],
                    false => 0,
                })
                .collect(),
        }
    }

    pub fn to_string(&self) -> String {
        match self {
            Signal::Constant(_) => "Constant value".to_string(),
            Signal::Sine(_) => "Sinusoidal wave".to_string(),
            Signal::Ramp(_) => "Linear ramp".to_string(),
            Signal::MixedSignal(_) => "Mixed signal".to_string(),
            Signal::Arbitrary(_) => "Arbitrary wave".to_string(),
        }
    }

    pub fn duration_to_num_samples(duration: f64) -> usize {
        f64::ceil(duration * config::INTERFACE_SAMPLING_RATE as f64) as usize
    }

    pub fn fp16(val: f64) -> i16 {
        f64::round(val * config::FP_MAX as f64) as i16
    }

    pub fn f64(val: i16) -> f64 {
        val as f64 / config::FP_MAX as f64
    }
}
