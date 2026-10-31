#include "PublishingWorker.hpp"
#include <chrono>

namespace aether::vision {

PublishingWorker::PublishingWorker(
    ThreadSafeQueue<ProcessingResult>& result_queue,
    std::shared_ptr<IPublisher> publisher,
    TelemetryProvider telemetry_provider
) : WorkerBase("PublishingWorker"),
    result_queue_(result_queue),
    publisher_(std::move(publisher)),
    telemetry_provider_(std::move(telemetry_provider)) {}

void PublishingWorker::workLoop() {
    auto last_telemetry_time = std::chrono::steady_clock::now();

    while (is_running_.load()) {
        ProcessingResult result;
        bool has_result = result_queue_.pop_for(result, std::chrono::milliseconds(50));

        if (has_result && publisher_) {
            publisher_->publishResult(result);
            trackProgress(); // Automatically updates total count and rolling FPS
        }

        // Periodic 1Hz system telemetry broadcast
        auto now = std::chrono::steady_clock::now();
        double telemetry_elapsed = std::chrono::duration<double>(now - last_telemetry_time).count();
        if (telemetry_elapsed >= 1.0) {
            if (telemetry_provider_ && publisher_) {
                SystemTelemetry telemetry = telemetry_provider_();
                publisher_->publishTelemetry(telemetry);
            }
            last_telemetry_time = now;
        }
    }
}

} // namespace aether::vision
