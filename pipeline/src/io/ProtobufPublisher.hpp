#pragma once

#include "core/Types.hpp"
#include "core/ProtobufFraming.hpp"

#include <mutex>
#include <string>
#include <memory>
#include <iostream>

namespace aether::vision {

class IPublisher {
public:
    virtual ~IPublisher() = default;
    virtual void publishResult(const ProcessingResult& result) = 0;
    virtual void publishTelemetry(const SystemTelemetry& telemetry) = 0;
    virtual void publishStatus(PipelineState state, CameraState cam_state, const std::string& device, const std::string& serial) = 0;
    virtual void publishAck(const std::string& command_id, bool success, const std::string& message) = 0;
    virtual void publishConfig(const CameraConfig& cam_cfg, const ProcessingConfig& proc_cfg, const std::string& command_id) = 0;
    virtual void publishError(const std::string& error_msg) = 0;
    virtual void publishRawMessage(const PipelineMessage& message) = 0;
};

class ProtobufPublisher : public IPublisher {
public:
    explicit ProtobufPublisher(std::ostream& output_stream = std::cout);
    ~ProtobufPublisher() override = default;

    void publishResult(const ProcessingResult& result) override;
    void publishTelemetry(const SystemTelemetry& telemetry) override;
    void publishStatus(PipelineState state, CameraState cam_state, const std::string& device, const std::string& serial) override;
    void publishAck(const std::string& command_id, bool success, const std::string& message) override;
    void publishConfig(const CameraConfig& cam_cfg, const ProcessingConfig& proc_cfg, const std::string& command_id) override;
    void publishError(const std::string& error_msg) override;

    void publishRawMessage(const PipelineMessage& message) override;

private:
    std::ostream& os_;
    std::mutex stdout_mutex_;
};

} // namespace aether::vision
