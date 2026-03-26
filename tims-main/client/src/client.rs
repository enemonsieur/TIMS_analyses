use std::error;
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::{net::TcpStream, thread, time::Duration};

use protocols::{
    ControllerConfig, ControllerStatus, LogRecord, MachineConfig, RequestMessage, RequestType,
    ResponseMessage, StimulationProtocol, TIMSError,
};

type Result<T> = std::result::Result<T, Box<dyn error::Error>>;

#[derive(Debug)]
pub struct ServerStatus {
    pub controller_status: Vec<ControllerStatus>,
    pub logs: Vec<LogRecord>,
}

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum ClientState {
    Connected,
    Disconnected,
}

pub struct Client {
    server_ip: String,
    state: Arc<Mutex<ClientState>>,
    status_receiver: Receiver<ServerStatus>,
    request_sender: Sender<RequestMessage>,
    response_receiver: Receiver<ResponseMessage>,
}

impl Client {
    pub fn new(server_ip: String) -> Self {
        let (status_sender, status_receiver) = channel();
        let (request_sender, request_receiver) = channel();
        let (response_sender, response_receiver) = channel();
        let state = Arc::new(Mutex::new(ClientState::Disconnected));

        let client = Client {
            server_ip: server_ip.clone(),
            state: state.clone(),
            status_receiver,
            request_sender,
            response_receiver,
        };

        thread::spawn(move || {
            loop {
                match TcpStream::connect(&server_ip) {
                    Ok(stream) => {
                        *state.lock().unwrap() = ClientState::Connected;
                        match Client::handle_stream(
                            stream,
                            &status_sender,
                            &request_receiver,
                            &response_sender,
                        ) {
                            Ok(()) => {
                                *state.lock().unwrap() = ClientState::Disconnected;
                                log::info!("Disconnected from {} upon request", &server_ip);
                                return;
                            }
                            Err(e) => {
                                *state.lock().unwrap() = ClientState::Disconnected;
                                log::warn!("Connection with {} interrupted: {}", &server_ip, e);
                            }
                        }
                    }
                    Err(e) => {
                        *state.lock().unwrap() = ClientState::Disconnected;
                        log::warn!("Could not connect to {}: {}", &server_ip, e);
                    }
                };

                // check if a disconnect request has been received while still trying to connect
                for request in request_receiver.try_iter() {
                    match request.request_type {
                        RequestType::Disconnect => {
                            // stop trying to reconnect
                            response_sender.send(ResponseMessage::successful()).unwrap();
                            return;
                        }
                        _ => {
                            response_sender
                                .send(ResponseMessage::not_successful())
                                .unwrap();
                        }
                    }
                }

                thread::sleep(Duration::from_millis(2000));
            }
        });

        client
    }

    pub fn get_server_ip(&self) -> &String {
        return &self.server_ip;
    }

    pub fn disconnect(&mut self) {
        self.request_sender
            .send(RequestMessage {
                request_type: RequestType::Disconnect,
                ..Default::default()
            })
            .unwrap();

        self.response_receiver.recv().unwrap();
    }

    pub fn get_state(&mut self) -> ClientState {
        *self.state.lock().unwrap()
    }

    pub fn connected(&mut self) -> bool {
        self.get_state() == ClientState::Connected
    }

    pub fn get_status(&mut self) -> Vec<ServerStatus> {
        self.status_receiver.try_iter().collect()
    }

    pub fn get_machine_config(&mut self) -> Result<MachineConfig> {
        self.request_sender
            .send(RequestMessage {
                request_type: RequestType::GetMachineConfig,
                ..Default::default()
            })
            .unwrap();

        Ok(self
            .response_receiver
            .recv()
            .unwrap()
            .machine_config
            .ok_or(TIMSError::ConfigError)?)
    }

    pub fn set_controller_config(&mut self, cconf: &ControllerConfig) -> Result<()> {
        self.request_sender
            .send(RequestMessage {
                request_type: RequestType::SetControllerConfig,
                controller_config: Some(cconf.clone()),
                ..Default::default()
            })
            .unwrap();

        if self.response_receiver.recv().unwrap().operation_successful {
            Ok(())
        } else {
            Err(Box::new(TIMSError::ConfigError))
        }
    }

    pub fn set_protocol(&mut self, protocol: &StimulationProtocol) -> Result<()> {
        self.request_sender
            .send(RequestMessage {
                request_type: RequestType::SetStimulationProtocol,
                stimulation_protocol: Some(protocol.clone()),
                ..Default::default()
            })
            .unwrap();

        if self.response_receiver.recv().unwrap().operation_successful {
            Ok(())
        } else {
            Err(Box::new(TIMSError::ProtocolError))
        }
    }

    fn handle_stream(
        stream: TcpStream,
        status_sender: &Sender<ServerStatus>,
        request_receiver: &Receiver<RequestMessage>,
        response_sender: &Sender<ResponseMessage>,
    ) -> Result<()> {
        let mut status_idx = 0;
        let mut log_idx = 0;
        loop {
            let status = Client::get_server_status(&stream, &mut status_idx, &mut log_idx)?;
            if !status.controller_status.is_empty() || !status.logs.is_empty() {
                status_sender.send(status).unwrap();
            }

            for request in request_receiver.try_iter() {
                if request.request_type == RequestType::Disconnect {
                    return Ok(());
                }
                protocols::send_request(&stream, &request)?;
                let response = protocols::receive_response(&stream)?;
                response_sender.send(response).unwrap();
            }
            thread::sleep(Duration::from_millis(10));
        }
    }

    fn get_server_status(
        stream: &TcpStream,
        status_idx: &mut u64,
        log_idx: &mut u64,
    ) -> Result<ServerStatus> {
        let request = RequestMessage {
            request_type: RequestType::GetStatusAndLogs,
            last_seen_status_idx: *status_idx,
            last_seen_log_idx: *log_idx,
            ..Default::default()
        };

        protocols::send_request(&stream, &request)?;

        let response = protocols::receive_response(&stream)?;
        let controller_status = response.controller_status.ok_or(TIMSError::TCPError)?;
        let logs = response.logs.ok_or(TIMSError::TCPError)?;

        if let Some(s) = controller_status.last() {
            *status_idx = s.idx;
        }

        if let Some(r) = logs.last() {
            *log_idx = r.idx;
        }

        for rec in logs.iter() {
            log::log!(rec.level, "SERVER LOG: {}", rec.msg);
        }

        Ok(ServerStatus {
            controller_status,
            logs,
        })
    }
}
