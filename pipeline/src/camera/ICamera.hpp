#pragma once

#include "core/Types.hpp"
#include <chrono>
#include <memory>
#include <string>

namespace aether::vision {

class ICamera {
public:
    virtual ~ICamera() = default;

    virtual bool initialize(const CameraConfig& config) = 0;
    virtual bool start() = 0;
    virtual void stop() = 0;
    virtual bool isStreaming() const = 0;
    virtual CameraState getState() const = 0;

    // Capture the latest frame bundle (color, depth, intrinsics)
    virtual bool capture(FrameBundle& out_bundle, std::chrono::milliseconds timeout) = 0;

    // Dynamically apply hardware settings (exposure, gain, laser, etc.)
    virtual bool applySettings(const CameraConfig& config) = 0;

    // Device metadata
    virtual std::string getDeviceName() const = 0;
    virtual std::string getSerialNumber() const = 0;
    virtual CameraIntrinsics getColorIntrinsics() const = 0;
    virtual CameraIntrinsics getDepthIntrinsics() const = 0;
    virtual float getDepthScale() const = 0;
};

} // namespace aether::vision
