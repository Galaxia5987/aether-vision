#include "ProtobufStdinHandler.hpp"
#include "core/ProtobufFraming.hpp"
#include "core/Logger.hpp"

namespace aether::vision {

ProtobufStdinHandler::ProtobufStdinHandler(ICommandDispatcher& dispatcher, std::istream& input_stream)
    : dispatcher_(dispatcher),
      is_(input_stream),
      is_running_(false) {
    read_buffer_.reserve(64 * 1024);
}

ProtobufStdinHandler::~ProtobufStdinHandler() {
    stop();
}

void ProtobufStdinHandler::start() {
    if (is_running_.exchange(true)) {
        return;
    }

    worker_thread_ = std::make_unique<std::thread>(&ProtobufStdinHandler::readLoop, this);
    LOG_INFO("Protobuf STDIN reader thread started");
}

void ProtobufStdinHandler::stop() {
    if (!is_running_.exchange(false)) {
        return;
    }

    if (worker_thread_ && worker_thread_->joinable()) {
        worker_thread_->detach();
    }
    LOG_INFO("Protobuf STDIN reader stopped");
}

void ProtobufStdinHandler::processCommand(const PipelineCommand& command) {
    dispatcher_.dispatchCommand(command);
}

void ProtobufStdinHandler::readLoop() {
    while (is_running_.load()) {
        PipelineCommand command;
        bool ok = ProtobufFraming::readDelimited(is_, command, read_buffer_);

        if (!ok) {
            if (is_running_.load()) {
                LOG_INFO("STDIN closed or reached EOF. Requesting pipeline shutdown...");
                PipelineCommand shutdown_cmd;
                shutdown_cmd.set_type(proto::CMD_SHUTDOWN);
                shutdown_cmd.set_command_id("system-eof");
                dispatcher_.dispatchCommand(shutdown_cmd);
            }
            break;
        }

        processCommand(command);
    }
}

} // namespace aether::vision
