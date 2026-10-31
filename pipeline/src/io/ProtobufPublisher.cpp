#include "ProtobufPublisher.hpp"
#include <chrono>

namespace aether::vision {

ProtobufPublisher::ProtobufPublisher(std::ostream& output_stream)
    : os_(output_stream) {}

void ProtobufPublisher::publishRawMessage(const PipelineMessage& message) {
    std::lock_guard<std::mutex> lock(stdout_mutex_);
    ProtobufFraming::writeDelimited(os_, message);
}

void ProtobufPublisher::publishResult(const ProcessingResult& result) {
    PipelineMessage msg;
    *msg.mutable_result() = result; // Direct Protobuf copy, zero conversion boilerplate
    publishRawMessage(msg);
}

void ProtobufPublisher::publishTelemetry(const SystemTelemetry& telemetry) {
    PipelineMessage msg;
    *msg.mutable_telemetry() = telemetry;
    publishRawMessage(msg);
}

void ProtobufPublisher::publishStatus(PipelineState state, CameraState cam_state, const std::string& device, const std::string& serial) {
    PipelineMessage msg;
    auto* status = msg.mutable_status();
    status->set_pipeline_state(state);
    status->set_camera_status(cam_state);
    status->set_camera_device(device);
    status->set_camera_serial(serial);
    publishRawMessage(msg);
}

void ProtobufPublisher::publishAck(const std::string& command_id, bool success, const std::string& message) {
    PipelineMessage msg;
    auto* ack = msg.mutable_ack();
    ack->set_command_id(command_id);
    ack->set_success(success);
    ack->set_message(message);
    publishRawMessage(msg);
}

void ProtobufPublisher::publishConfig(const CameraConfig& cam_cfg, const ProcessingConfig& proc_cfg, const std::string& command_id) {
    PipelineMessage msg;
    auto* ack = msg.mutable_ack();
    ack->set_command_id(command_id);
    ack->set_success(true);
    ack->set_message("Pipeline Configuration");

    auto* cfg_data = ack->mutable_config_data();
    *cfg_data->mutable_camera_config() = cam_cfg;
    *cfg_data->mutable_processing_config() = proc_cfg;

    publishRawMessage(msg);
}

void ProtobufPublisher::publishError(const std::string& error_msg) {
    PipelineMessage msg;
    auto* err = msg.mutable_error();
    err->set_error_message(error_msg);
    err->set_timestamp_ms(static_cast<double>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count()
    ));
    publishRawMessage(msg);
}

} // namespace aether::vision
