#pragma once

#include "WorkerBase.hpp"
#include "core/Types.hpp"
#include "core/ThreadSafeQueue.hpp"
#include "camera/ICamera.hpp"
#include "io/ProtobufPublisher.hpp"

#include <mutex>
#include <string>
#include <memory>

namespace aether::vision {

class CaptureWorker : public WorkerBase {
public:
    CaptureWorker(
        std::shared_ptr<ICamera> camera,
        ThreadSafeQueue<std::shared_ptr<FrameBundle>>& frame_queue,
        std::shared_ptr<IPublisher> publisher,
        const CameraConfig& initial_config = {}
    );
    ~CaptureWorker() override = default;

    void applySettings(const CameraConfig& config);
    bool resetCamera();

    CameraConfig getConfig() const;
    CameraState getCameraState() const;
    std::string getDeviceName() const;
    std::string getSerialNumber() const;

protected:
    void workLoop() override;
    void onStop() override;

private:
    std::shared_ptr<ICamera> camera_;
    ThreadSafeQueue<std::shared_ptr<FrameBundle>>& frame_queue_;
    std::shared_ptr<IPublisher> publisher_;

    mutable std::mutex config_mutex_;
    CameraConfig config_;
};

} // namespace aether::vision
