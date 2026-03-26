use circular_buffer::CircularBuffer;
use protocols::{ControllerState, ControllerStatus, LogRecord, RequestType, ResponseMessage};

use crate::Controller;
use std::{
    net::{TcpListener, TcpStream},
    sync::{Arc, Mutex},
    thread,
    time::{Duration, SystemTime},
};

type LogBuffer = CircularBuffer<256, LogRecord>;
type ControllerStatusBuffer = CircularBuffer<32, ControllerStatus>;

#[derive(Clone)]
pub struct Server {
    controller: Arc<Mutex<Controller>>,
    controller_status: Arc<Mutex<ControllerStatusBuffer>>,
    logs: Arc<Mutex<LogBuffer>>,
}

impl Server {
    pub fn new() -> Self {
        let logs = Arc::new(Mutex::new(LogBuffer::new()));
        Server::setup_logs(logs.clone());

        let controller = Controller::new();

        let server = Server {
            controller: Arc::new(Mutex::new(controller)),
            controller_status: Arc::new(Mutex::new(CircularBuffer::new())),
            logs: logs,
        };

        Server::handle_controller(server.clone());
        server
    }

    pub fn start(&mut self) {
        let listener = TcpListener::bind("0.0.0.0:8080").expect("Failed to bind to port 8080");

        for stream in listener.incoming() {
            match stream {
                Ok(stream) => {
                    Server::handle_client(self.clone(), stream);
                }
                Err(e) => log::error!("Failed to establish connection with client: {}", e),
            }
        }
    }

    fn handle_controller(server: Server) {
        thread::spawn(move || {
            loop {
                log::info!("Starting controller thread");

                let status_receiver = server.controller.lock().unwrap().start();

                for status in status_receiver.iter() {
                    if let ControllerState::Error(e) = status.state {
                        log::error!("Controller crashed with error: {e}");
                        break;
                    }
                    server.controller_status.lock().unwrap().push_back(status);
                }

                log::info!("Restarting controller in 5 seconds");
                thread::sleep(Duration::from_secs(5));
            }
        });
    }

    fn handle_client(server: Server, stream: TcpStream) {
        thread::spawn(move || {
            let peer = stream.peer_addr().unwrap();
            log::info!("New connection with: {peer}");

            loop {
                if let Ok(request) = protocols::receive_request(&stream) {
                    let response = match request.request_type {
                        RequestType::GetMachineConfig => ResponseMessage {
                            machine_config: Some(
                                server
                                    .controller
                                    .lock()
                                    .unwrap()
                                    .get_machine_configuration(),
                            ),
                            operation_successful: true,
                            ..Default::default()
                        },

                        RequestType::GetStatusAndLogs => ResponseMessage {
                            controller_status: Some(
                                server.controller_status_since(request.last_seen_status_idx),
                            ),
                            logs: Some(server.logs_since(request.last_seen_log_idx)),
                            operation_successful: true,
                            ..Default::default()
                        },

                        RequestType::SetControllerConfig => {
                            if let Some(cconf) = request.controller_config {
                                match server.controller.lock().unwrap().set_config(cconf) {
                                    Ok(()) => ResponseMessage::successful(),
                                    Err(e) => {
                                        log::error!(
                                            "Error while applying controller configuration: {e}"
                                        );
                                        ResponseMessage::not_successful()
                                    }
                                }
                            } else {
                                ResponseMessage::not_successful()
                            }
                        }

                        RequestType::SetStimulationProtocol => {
                            if let Some(protocol) = request.stimulation_protocol {
                                match server.controller.lock().unwrap().set_protocol(protocol) {
                                    Ok(()) => ResponseMessage::successful(),
                                    Err(e) => {
                                        log::error!(
                                            "Error while loading stimulation protocol: {e}"
                                        );
                                        ResponseMessage::not_successful()
                                    }
                                }
                            } else {
                                ResponseMessage::not_successful()
                            }
                        }

                        _ => ResponseMessage::default(),
                    };

                    if protocols::send_response(&stream, &response).is_err() {
                        log::info!("Connection with {peer} interrupted while sending response");
                        break;
                    };
                } else {
                    log::info!("Connection with {peer} interrupted while receiving request");
                    break;
                }
            }

            log::info!("Connection with {peer} terminated");
        });
    }

    fn setup_logs(logs: Arc<Mutex<LogBuffer>>) {
        fern::Dispatch::new()
            .format(|out, message, record| {
                out.finish(format_args!(
                    "[{} {}] {}",
                    humantime::format_rfc3339_seconds(SystemTime::now()),
                    record.level(),
                    message
                ))
            })
            .level(log::LevelFilter::Info)
            .chain(std::io::stdout())
            .chain(fern::Output::call(move |record| {
                let mut logs = logs.lock().unwrap();
                let idx = if let Some(r) = logs.back() {
                    r.idx + 1
                } else {
                    1
                };

                logs.push_back(LogRecord {
                    msg: record.args().to_string(),
                    level: record.level(),
                    idx,
                });
            }))
            .apply()
            .unwrap();
    }

    fn controller_status_since(&self, idx: u64) -> Vec<ControllerStatus> {
        self.controller_status
            .lock()
            .unwrap()
            .iter()
            .filter_map(|s| if s.idx > idx { Some(s.clone()) } else { None })
            .collect()
    }

    fn logs_since(&self, idx: u64) -> Vec<LogRecord> {
        self.logs
            .lock()
            .unwrap()
            .iter()
            .filter_map(|s| if s.idx > idx { Some(s.clone()) } else { None })
            .collect()
    }
}
