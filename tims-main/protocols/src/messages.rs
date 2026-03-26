use std::{
    error,
    io::{Read, Write},
    net::TcpStream,
};

use crate::{ControllerConfig, ControllerStatus, MachineConfig, StimulationProtocol};
use serde::{Deserialize, Serialize};

type Result<T> = std::result::Result<T, Box<dyn error::Error>>;

#[derive(Clone, Copy, PartialEq, Deserialize, Serialize, Debug)]
pub enum RequestType {
    GetStatusAndLogs,
    GetMachineConfig,
    SetControllerConfig,
    SetStimulationProtocol,
    Disconnect,
}

impl Default for RequestType {
    fn default() -> Self {
        RequestType::GetStatusAndLogs
    }
}

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct RequestMessage {
    pub request_type: RequestType,
    pub controller_config: Option<ControllerConfig>,
    pub stimulation_protocol: Option<StimulationProtocol>,
    pub last_seen_status_idx: u64,
    pub last_seen_log_idx: u64,
}

#[derive(Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct LogRecord {
    pub msg: String,
    pub level: log::Level,
    pub idx: u64,
}

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct ResponseMessage {
    pub machine_config: Option<MachineConfig>,
    pub controller_status: Option<Vec<ControllerStatus>>,
    pub logs: Option<Vec<LogRecord>>,
    pub operation_successful: bool,
}

impl ResponseMessage {
    pub fn successful() -> Self {
        Self {
            operation_successful: true,
            ..Default::default()
        }
    }

    pub fn not_successful() -> Self {
        Self {
            operation_successful: false,
            ..Default::default()
        }
    }
}

pub fn send_request(stream: &TcpStream, message: &RequestMessage) -> Result<()> {
    let buffer = postcard::to_allocvec(message)?;
    write_buffer(stream, &buffer)?;
    Ok(())
}

pub fn receive_request(stream: &TcpStream) -> Result<RequestMessage> {
    let buffer = read_buffer(stream)?;
    let request: RequestMessage = postcard::from_bytes(&buffer)?;
    Ok(request)
}

pub fn send_response(stream: &TcpStream, message: &ResponseMessage) -> Result<()> {
    let buffer = postcard::to_allocvec(message)?;
    write_buffer(stream, &buffer)?;
    Ok(())
}

pub fn receive_response(stream: &TcpStream) -> Result<ResponseMessage> {
    let buffer = read_buffer(stream)?;
    let request: ResponseMessage = postcard::from_bytes(&buffer)?;
    Ok(request)
}

fn write_buffer(mut stream: &TcpStream, data: &[u8]) -> Result<()> {
    stream.write(&u32::to_be_bytes(data.len() as u32))?;
    stream.write(&data)?;
    Ok(())
}

fn read_buffer(mut stream: &TcpStream) -> Result<Vec<u8>> {
    let mut size_buffer = [0; size_of::<u32>()];
    stream.read_exact(&mut size_buffer)?;

    let size = u32::from_be_bytes(size_buffer) as usize;
    let mut buffer = vec![0; size];
    stream.read_exact(&mut buffer)?;

    Ok(buffer)
}
