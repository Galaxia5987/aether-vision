#include "CaptureWorker.hpp"
#include "core/Logger.hpp"
#include <chrono>

namespace aether::vision {

CaptureWorker::CaptureWorker(
    std::shared_ptr<ICamera> camera,
    ThreadSafeQueue<std::shared_ptr<FrameBundle>>& frame_queue,
    std::shared_ptr<IPublisher> publisher,
    const CameraConfig& initial_config
) : WorkerBase("CaptureWorker"),
    camera_(std::move(camera)),
    frame_queue_(frame_queue),
    publisher_(std::move(publisher)),
    config_(initial_config) {}

void CaptureWorker::onStop() {
    if (camera_) {
        camera_->stop();
    }
}

void CaptureWorker::applySettings(const CameraConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_.MergeFrom(config);
    if (camera_ && camera_->isStreaming()) {
        camera_->applySettings(config_);
    }
}

bool CaptureWorker::resetCamera() {
    if (!camera_) return false;
    camera_->stop();
    CameraConfig cfg = getConfig();
    return camera_->initialize(cfg) && camera_->start();
}

CameraConfig CaptureWorker::getConfig() const {
    std::lock_guard<std::mutex> lock(config_mutex_);
    return config_;
}

CameraState CaptureWorker::getCameraState() const {
    return camera_ ? camera_->getState() : proto::CAM_DISCONNECTED;
}

std::string CaptureWorker::getDeviceName() const {
    return camera_ ? camera_->getDeviceName() : "";
}

std::string CaptureWorker::getSerialNumber() const {
    return camera_ ? camera_->getSerialNumber() : "";
}

void CaptureWorker::workLoop() {
    while (is_running_.load()) {
        if (is_paused_.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            continue;
        }

        // Camera connection & automatic reconnection
        if (!camera_ || !camera_->isStreaming()) {
            LOG_INFO("Attempting camera connection...");
            CameraConfig cfg = getConfig();

            if (camera_ && camera_->initialize(cfg) && camera_->start()) {
                LOG_INFO("Camera connected: " << camera_->getDeviceName());
                if (publisher_) {
                    publisher_->publishStatus(
                        proto::PIPE_RUNNING,
                        camera_->getState(),
                        camera_->getDeviceName(),
                        camera_->getSerialNumber()
                    );
                }
            } else {
                LOG_WARN("Camera unavailable. Retrying in 1000ms...");
                for (int i = 0; i < 20 && is_running_.load(); ++i) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(50));
                }
                continue;
            }
        }

        // Frame acquisition
        auto bundle = std::make_shared<FrameBundle>();
        bool captured = camera_->capture(*bundle, std::chrono::milliseconds(200));

        if (captured) {
            trackProgress(); // Automatically updates total frames and rolling FPS
            frame_queue_.push(std::move(bundle));
        } else {
            if (camera_ && camera_->getState() == proto::CAM_ERROR) {
                LOG_WARN("Camera error encountered. Triggering reconnect...");
                camera_->stop();
                if (publisher_) {
                    publisher_->publishError("Camera capture error, attempting restart...");
                }
            }
        }
    }
}

} // namespace aether::vision
