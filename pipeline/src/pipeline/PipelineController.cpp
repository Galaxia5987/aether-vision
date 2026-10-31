#include "PipelineController.hpp"
#include "PipelineManager.hpp"
#include "core/Logger.hpp"

namespace aether::vision {

PipelineController::PipelineController(
    PipelineManager& manager,
    CaptureWorker& capture_worker,
    ProcessingWorker& processing_worker,
    PublishingWorker& publishing_worker,
    std::shared_ptr<IPublisher> publisher
) : manager_(manager),
    capture_worker_(capture_worker),
    processing_worker_(processing_worker),
    publishing_worker_(publishing_worker),
    publisher_(std::move(publisher)) {}

void PipelineController::dispatchCommand(const PipelineCommand& command) {
    LOG_INFO("PipelineController received command: " << static_cast<int>(command.type()) << " (id: " << command.command_id() << ")");

    switch (command.type()) {
        case proto::CMD_START: {
            bool ok = manager_.start();
            if (publisher_) publisher_->publishAck(command.command_id(), ok, ok ? "Started" : "Already running");
            break;
        }
        case proto::CMD_STOP: {
            manager_.stop();
            if (publisher_) publisher_->publishAck(command.command_id(), true, "Stopped");
            break;
        }
        case proto::CMD_PAUSE: {
            manager_.pause();
            if (publisher_) publisher_->publishAck(command.command_id(), true, "Paused");
            break;
        }
        case proto::CMD_RESUME: {
            manager_.resume();
            if (publisher_) publisher_->publishAck(command.command_id(), true, "Resumed");
            break;
        }
        case proto::CMD_CONFIGURE_CAMERA: {
            handleSetCamera(command);
            break;
        }
        case proto::CMD_CONFIGURE_PROCESSING: {
            handleSetProcessing(command);
            break;
        }
        case proto::CMD_GET_STATUS: {
            handleGetStatus(command.command_id());
            break;
        }
        case proto::CMD_GET_CONFIG: {
            handleGetConfig(command.command_id());
            break;
        }
        case proto::CMD_RESET_CAMERA: {
            handleResetCamera(command.command_id());
            break;
        }
        case proto::CMD_SHUTDOWN: {
            if (publisher_) publisher_->publishAck(command.command_id(), true, "Shutting down pipeline");
            manager_.stop();
            break;
        }
        default: {
            LOG_WARN("Unknown Protobuf command type received: " << static_cast<int>(command.type()));
            if (publisher_) publisher_->publishAck(command.command_id(), false, "Unknown command type");
            break;
        }
    }
}

void PipelineController::handleSetCamera(const PipelineCommand& command) {
    if (command.has_camera_config()) {
        capture_worker_.applySettings(command.camera_config());
    }

    if (publisher_) {
        publisher_->publishAck(command.command_id(), true, "Camera settings applied");
    }
}

void PipelineController::handleSetProcessing(const PipelineCommand& command) {
    if (command.has_processing_config()) {
        processing_worker_.configure(command.processing_config());
    }

    if (publisher_) {
        publisher_->publishAck(command.command_id(), true, "Processing settings applied");
    }
}

void PipelineController::handleGetStatus(const std::string& command_id) {
    if (!publisher_) return;

    PipelineMessage msg;
    auto* ack = msg.mutable_ack();
    ack->set_command_id(command_id);
    ack->set_success(true);
    ack->set_message("Pipeline status");

    auto* status = ack->mutable_status_data();
    status->set_pipeline_state(manager_.getState());
    status->set_camera_status(capture_worker_.getCameraState());
    status->set_camera_device(capture_worker_.getDeviceName());
    status->set_camera_serial(capture_worker_.getSerialNumber());
    status->set_frame_queue_size(static_cast<uint32_t>(manager_.getFrameQueueSize()));
    status->set_result_queue_size(static_cast<uint32_t>(manager_.getResultQueueSize()));
    status->set_dropped_frames(manager_.getDroppedFrames());
    status->set_capture_fps(capture_worker_.getFps());
    status->set_processing_fps(processing_worker_.getFps());
    status->set_publishing_fps(publishing_worker_.getFps());

    publisher_->publishRawMessage(msg);
}

void PipelineController::handleGetConfig(const std::string& command_id) {
    if (publisher_) {
        publisher_->publishConfig(capture_worker_.getConfig(), processing_worker_.getConfig(), command_id);
    }
}

void PipelineController::handleResetCamera(const std::string& command_id) {
    bool ok = capture_worker_.resetCamera();
    if (publisher_) {
        publisher_->publishAck(command_id, ok, ok ? "Camera reset successful" : "Camera reset failed");
    }
}

} // namespace aether::vision
