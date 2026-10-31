#include "PipelineManager.hpp"
#include "WorkerBase.hpp"
#include "CaptureWorker.hpp"
#include "ProcessingWorker.hpp"
#include "PublishingWorker.hpp"
#include "PipelineController.hpp"
#include "core/Logger.hpp"

namespace aether::vision {

PipelineManager::PipelineManager(
    std::shared_ptr<ICamera> camera,
    std::shared_ptr<IProcessor> processor,
    std::shared_ptr<IPublisher> publisher,
    const CameraConfig& initial_cam_config,
    const ProcessingConfig& initial_proc_config
) : publisher_(std::move(publisher)),
    frame_queue_(2, QueueDropPolicy::DropOldest),
    result_queue_(5, QueueDropPolicy::DropOldest) {

    // 1. Instantiate workers deriving from WorkerBase
    capture_worker_ = std::make_unique<CaptureWorker>(
        std::move(camera),
        frame_queue_,
        publisher_,
        initial_cam_config
    );

    processing_worker_ = std::make_unique<ProcessingWorker>(
        std::move(processor),
        frame_queue_,
        result_queue_,
        initial_proc_config
    );

    publishing_worker_ = std::make_unique<PublishingWorker>(
        result_queue_,
        publisher_,
        [this]() { return collectTelemetry(); }
    );

    // Collect base pointers for uniform lifecycle iteration
    workers_ = { capture_worker_.get(), processing_worker_.get(), publishing_worker_.get() };

    // 2. Instantiate STDIN command controller
    controller_ = std::make_unique<PipelineController>(
        *this,
        *capture_worker_,
        *processing_worker_,
        *publishing_worker_,
        publisher_
    );
}

PipelineManager::~PipelineManager() {
    stop();
}

bool PipelineManager::start() {
    if (is_running_.exchange(true)) {
        LOG_WARN("Pipeline already running");
        return true;
    }

    state_ = proto::PIPE_STARTING;
    start_time_ = std::chrono::steady_clock::now();

    frame_queue_.resume();
    result_queue_.resume();

    LOG_INFO("Starting pipeline worker modules...");
    for (auto* worker : workers_) {
        worker->start();
    }

    state_ = proto::PIPE_RUNNING;
    if (publisher_) {
        publisher_->publishStatus(
            state_.load(),
            capture_worker_->getCameraState(),
            capture_worker_->getDeviceName(),
            capture_worker_->getSerialNumber()
        );
    }

    LOG_INFO("Pipeline successfully started.");
    return true;
}

void PipelineManager::stop() {
    if (!is_running_.exchange(false)) {
        return;
    }

    state_ = proto::PIPE_STOPPING;
    LOG_INFO("Stopping pipeline worker modules...");

    frame_queue_.stop();
    result_queue_.stop();

    for (auto* worker : workers_) {
        worker->stop();
    }

    state_ = proto::PIPE_STOPPED;
    if (publisher_) {
        publisher_->publishStatus(
            state_.load(),
            capture_worker_->getCameraState(),
            capture_worker_->getDeviceName(),
            capture_worker_->getSerialNumber()
        );
    }
    LOG_INFO("Pipeline stopped cleanly.");
}

void PipelineManager::pause() {
    state_ = proto::PIPE_PAUSED;
    for (auto* worker : workers_) {
        worker->pause();
    }
    if (publisher_) {
        publisher_->publishStatus(
            state_.load(),
            capture_worker_->getCameraState(),
            capture_worker_->getDeviceName(),
            capture_worker_->getSerialNumber()
        );
    }
    LOG_INFO("Pipeline paused.");
}

void PipelineManager::resume() {
    state_ = proto::PIPE_RUNNING;
    for (auto* worker : workers_) {
        worker->resume();
    }
    if (publisher_) {
        publisher_->publishStatus(
            state_.load(),
            capture_worker_->getCameraState(),
            capture_worker_->getDeviceName(),
            capture_worker_->getSerialNumber()
        );
    }
    LOG_INFO("Pipeline resumed.");
}

void PipelineManager::wait() {
    while (is_running_.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

void PipelineManager::dispatchCommand(const PipelineCommand& command) {
    if (controller_) {
        controller_->dispatchCommand(command);
    }
}

size_t PipelineManager::getFrameQueueSize() const {
    return frame_queue_.size();
}

size_t PipelineManager::getResultQueueSize() const {
    return result_queue_.size();
}

uint64_t PipelineManager::getDroppedFrames() const {
    return frame_queue_.get_dropped_count();
}

double PipelineManager::getUptimeSeconds() const {
    if (!is_running_.load()) return 0.0;
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration<double>(now - start_time_).count();
}

SystemTelemetry PipelineManager::collectTelemetry() {
    SystemTelemetry telemetry;
    telemetry.set_capture_fps(capture_worker_ ? capture_worker_->getFps() : 0.0);
    telemetry.set_processing_fps(processing_worker_ ? processing_worker_->getFps() : 0.0);
    telemetry.set_publishing_fps(publishing_worker_ ? publishing_worker_->getFps() : 0.0);
    telemetry.set_frames_captured(capture_worker_ ? capture_worker_->getTotalFrames() : 0);
    telemetry.set_frames_processed(processing_worker_ ? processing_worker_->getTotalFrames() : 0);
    telemetry.set_frames_dropped(frame_queue_.get_dropped_count());
    telemetry.set_camera_status(capture_worker_ ? capture_worker_->getCameraState() : proto::CAM_DISCONNECTED);
    telemetry.set_pipeline_state(state_.load());
    telemetry.set_uptime_seconds(getUptimeSeconds());
    return telemetry;
}

} // namespace aether::vision
