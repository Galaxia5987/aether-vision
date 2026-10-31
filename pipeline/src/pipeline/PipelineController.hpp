#pragma once

#include "core/Types.hpp"
#include "io/ProtobufStdinHandler.hpp"
#include "io/ProtobufPublisher.hpp"
#include "CaptureWorker.hpp"
#include "ProcessingWorker.hpp"
#include "PublishingWorker.hpp"

#include <memory>
#include <string>

namespace aether::vision {

class PipelineManager;

class PipelineController : public ICommandDispatcher {
public:
    PipelineController(
        PipelineManager& manager,
        CaptureWorker& capture_worker,
        ProcessingWorker& processing_worker,
        PublishingWorker& publishing_worker,
        std::shared_ptr<IPublisher> publisher
    );
    ~PipelineController() override = default;

    void dispatchCommand(const PipelineCommand& command) override;

private:
    void handleSetCamera(const PipelineCommand& command);
    void handleSetProcessing(const PipelineCommand& command);
    void handleGetStatus(const std::string& command_id);
    void handleGetConfig(const std::string& command_id);
    void handleResetCamera(const std::string& command_id);

    PipelineManager& manager_;
    CaptureWorker& capture_worker_;
    ProcessingWorker& processing_worker_;
    PublishingWorker& publishing_worker_;
    std::shared_ptr<IPublisher> publisher_;
};

} // namespace aether::vision
