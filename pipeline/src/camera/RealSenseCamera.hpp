#pragma once

#include "ICamera.hpp"
#include <librealsense2/rs.hpp>
#include <mutex>
#include <atomic>
#include <memory>
#include <string>

namespace aether::vision {

class RealSenseCamera : public ICamera {
public:
    RealSenseCamera();
    ~RealSenseCamera() override;

    bool initialize(const CameraConfig& config) override;
    bool start() override;
    void stop() override;
    bool isStreaming() const override;
    CameraState getState() const override;

    bool capture(FrameBundle& out_bundle, std::chrono::milliseconds timeout) override;
    bool applySettings(const CameraConfig& config) override;

    std::string getDeviceName() const override;
    std::string getSerialNumber() const override;
    CameraIntrinsics getColorIntrinsics() const override;
    CameraIntrinsics getDepthIntrinsics() const override;
    float getDepthScale() const override;

    // Checks hardware connection without starting stream
    bool isDeviceAvailable() const;

private:
    void querySensorsAndIntrinsics();
    void updateIntrinsicsFromProfile();

    CameraConfig config_;
    mutable std::mutex mutex_;
    std::atomic<CameraState> state_;
    std::atomic<bool> is_streaming_;

    rs2::context ctx_;
    rs2::pipeline pipe_;
    rs2::config cfg_;
    rs2::pipeline_profile profile_;
    rs2::device device_;
    std::unique_ptr<rs2::align> align_to_color_;

    std::string device_name_;
    std::string serial_number_;
    float depth_scale_ = 0.001f;

    CameraIntrinsics color_intrinsics_;
    CameraIntrinsics depth_intrinsics_;
    uint64_t sequence_counter_ = 0;
};

} // namespace aether::vision
