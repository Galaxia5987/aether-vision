#include "ProcessingWorker.hpp"
#include <chrono>

namespace aether::vision {

ProcessingWorker::ProcessingWorker(
    std::shared_ptr<IProcessor> processor,
    ThreadSafeQueue<std::shared_ptr<FrameBundle>>& frame_queue,
    ThreadSafeQueue<ProcessingResult>& result_queue,
    const ProcessingConfig& initial_config
) : WorkerBase("ProcessingWorker"),
    processor_(std::move(processor)),
    frame_queue_(frame_queue),
    result_queue_(result_queue) {
    configure(initial_config);
}

void ProcessingWorker::configure(const ProcessingConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_.MergeFrom(config);
    if (processor_) {
        processor_->configure(config_);
    }
}

ProcessingConfig ProcessingWorker::getConfig() const {
    std::lock_guard<std::mutex> lock(config_mutex_);
    return config_;
}

void ProcessingWorker::workLoop() {
    while (is_running_.load()) {
        std::shared_ptr<FrameBundle> bundle;
        bool has_frame = frame_queue_.pop_for(bundle, std::chrono::milliseconds(100));

        if (!has_frame || !bundle) {
            continue;
        }

        if (is_paused_.load()) {
            continue;
        }

        ProcessingResult result;
        if (processor_) {
            bool success = processor_->process(bundle, result);
            if (success) {
                trackProgress(); // Automatically updates total count and rolling FPS
                result_queue_.push(std::move(result));
            }
        }
    }
}

} // namespace aether::vision
