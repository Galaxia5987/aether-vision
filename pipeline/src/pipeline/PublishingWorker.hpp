#pragma once

#include "WorkerBase.hpp"
#include "core/Types.hpp"
#include "core/ThreadSafeQueue.hpp"
#include "io/ProtobufPublisher.hpp"

#include <memory>
#include <functional>

namespace aether::vision {

class PublishingWorker : public WorkerBase {
public:
    using TelemetryProvider = std::function<SystemTelemetry()>;

    PublishingWorker(
        ThreadSafeQueue<ProcessingResult>& result_queue,
        std::shared_ptr<IPublisher> publisher,
        TelemetryProvider telemetry_provider
    );
    ~PublishingWorker() override = default;

protected:
    void workLoop() override;

private:
    ThreadSafeQueue<ProcessingResult>& result_queue_;
    std::shared_ptr<IPublisher> publisher_;
    TelemetryProvider telemetry_provider_;
};

} // namespace aether::vision
