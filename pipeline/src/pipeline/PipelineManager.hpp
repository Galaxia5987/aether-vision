#pragma once

#include "core/Types.hpp"
#include "core/ThreadSafeQueue.hpp"
#include "camera/ICamera.hpp"
#include "processing/IProcessor.hpp"
#include "io/ProtobufPublisher.hpp"
#include "io/ProtobufStdinHandler.hpp"

#include <memory>
#include <vector>
#include <atomic>
#include <chrono>

namespace aether::vision {

class WorkerBase;
class CaptureWorker;
class ProcessingWorker;
class PublishingWorker;
class PipelineController;

class PipelineManager : public ICommandDispatcher {
public:
    PipelineManager(
        std::shared_ptr<ICamera> camera,
        std::shared_ptr<IProcessor> processor,
        std::shared_ptr<IPublisher> publisher,
        const CameraConfig& initial_cam_config = {},
        const ProcessingConfig& initial_proc_config = {}
    );
    ~PipelineManager() override;

    bool start();
    void stop();
    void pause();
    void resume();
    void wait();

    // ICommandDispatcher: delegates to PipelineController
    void dispatchCommand(const PipelineCommand& command) override;

    PipelineState getState() const { return state_.load(); }
    bool isRunning() const { return is_running_.load(); }

    size_t getFrameQueueSize() const;
    size_t getResultQueueSize() const;
    uint64_t getDroppedFrames() const;
    double getUptimeSeconds() const;

private:
    SystemTelemetry collectTelemetry();

    std::shared_ptr<IPublisher> publisher_;
    std::atomic<PipelineState> state_{proto::PIPE_STOPPED};
    std::atomic<bool> is_running_{false};
    std::chrono::steady_clock::time_point start_time_;

    ThreadSafeQueue<std::shared_ptr<FrameBundle>> frame_queue_;
    ThreadSafeQueue<ProcessingResult> result_queue_;

    std::unique_ptr<CaptureWorker> capture_worker_;
    std::unique_ptr<ProcessingWorker> processing_worker_;
    std::unique_ptr<PublishingWorker> publishing_worker_;
    std::unique_ptr<PipelineController> controller_;

    std::vector<WorkerBase*> workers_;
};

} // namespace aether::vision
