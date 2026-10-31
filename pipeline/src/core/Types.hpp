#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <chrono>
#include <opencv2/core.hpp>

namespace aether::vision {

enum class CameraState {
    DISCONNECTED,
    CONNECTING,
    STREAMING,
    ERROR_STATE
};

inline const char* cameraStateToString(CameraState state) {
    switch (state) {
        case CameraState::DISCONNECTED: return "DISCONNECTED";
        case CameraState::CONNECTING:   return "CONNECTING";
        case CameraState::STREAMING:    return "STREAMING";
        case CameraState::ERROR_STATE:  return "ERROR";
        default:                        return "UNKNOWN";
    }
}

enum class PipelineState {
    STOPPED,
    STARTING,
    RUNNING,
    PAUSED,
    STOPPING
};

inline const char* pipelineStateToString(PipelineState state) {
    switch (state) {
        case PipelineState::STOPPED:  return "STOPPED";
        case PipelineState::STARTING: return "STARTING";
        case PipelineState::RUNNING:  return "RUNNING";
        case PipelineState::PAUSED:   return "PAUSED";
        case PipelineState::STOPPING: return "STOPPING";
        default:                      return "UNKNOWN";
    }
}

struct CameraConfig {
    std::string serial_number = "";
    int width = 640;
    int height = 480;
    int fps = 30;
    bool enable_color = true;
    bool enable_depth = true;
    bool align_depth_to_color = true;

    // Hardware camera settings
    bool auto_exposure = true;
    int exposure = 150;            // manual exposure (microseconds / device units)
    int gain = 16;                 // manual gain
    int laser_power = 150;         // RealSense IR projector laser power (0-360)
    bool emitter_enabled = true;   // RealSense projector laser enable
};

struct CameraIntrinsics {
    int width = 0;
    int height = 0;
    float ppx = 0.0f;              // Principal point X
    float ppy = 0.0f;              // Principal point Y
    float fx = 0.0f;               // Focal length X
    float fy = 0.0f;               // Focal length Y
    float coeffs[5] = {0.0f};      // Distortion coefficients
    bool valid = false;

    // Deproject 2D pixel (u, v) and depth (Z in meters) to 3D point (X, Y, Z in meters)
    void deproject(float pixel_x, float pixel_y, float depth_m, float& out_x, float& out_y, float& out_z) const {
        if (!valid || fx == 0.0f || fy == 0.0f) {
            out_x = 0.0f;
            out_y = 0.0f;
            out_z = depth_m;
            return;
        }
        out_x = (pixel_x - ppx) / fx * depth_m;
        out_y = (pixel_y - ppy) / fy * depth_m;
        out_z = depth_m;
    }
};

struct FrameBundle {
    uint64_t sequence_id = 0;
    double timestamp_ms = 0.0;
    cv::Mat color_frame;           // BGR 8-bit image
    cv::Mat depth_frame;           // 16-bit raw depth (or float depth in meters)
    CameraIntrinsics color_intrinsics;
    CameraIntrinsics depth_intrinsics;
    float depth_scale = 0.001f;    // meters per raw unit (typical RS is 0.001 = 1mm)
    bool has_color = false;
    bool has_depth = false;
};

struct Target3D {
    std::string label = "target";
    float confidence = 1.0f;
    float pixel_x = 0.0f;          // 2D center X
    float pixel_y = 0.0f;          // 2D center Y
    float bbox_x = 0.0f;           // Bounding box top-left X
    float bbox_y = 0.0f;           // Bounding box top-left Y
    float bbox_w = 0.0f;           // Bounding box width
    float bbox_h = 0.0f;           // Bounding box height
    float x = 0.0f;                // 3D position relative to camera (meters, Right)
    float y = 0.0f;                // 3D position relative to camera (meters, Down)
    float z = 0.0f;                // 3D position relative to camera (meters, Forward)
    float distance = 0.0f;         // Euclidean distance in meters
};

struct ProcessingConfig {
    float min_depth_m = 0.2f;      // RealSense min valid range
    float max_depth_m = 6.0f;      // RealSense max valid range

    // Optional color-based segmentation (HSV)
    bool enable_color_filter = false;
    int hsv_h_min = 0;
    int hsv_h_max = 180;
    int hsv_s_min = 100;
    int hsv_s_max = 255;
    int hsv_v_min = 100;
    int hsv_v_max = 255;
    int min_contour_area = 150;

    // Filters and post-processing flags
    bool enable_spatial_filter = true;
    bool enable_temporal_filter = true;
    bool enable_hole_filling = true;
};

struct ProcessingResult {
    uint64_t sequence_id = 0;
    double capture_timestamp_ms = 0.0;
    double process_timestamp_ms = 0.0;
    double processing_latency_ms = 0.0;
    std::vector<Target3D> targets;
    std::map<std::string, double> metrics;
};

struct SystemTelemetry {
    double capture_fps = 0.0;
    double processing_fps = 0.0;
    double publishing_fps = 0.0;
    uint64_t frames_captured = 0;
    uint64_t frames_processed = 0;
    uint64_t frames_dropped = 0;
    std::string camera_status = "DISCONNECTED";
    std::string pipeline_state = "STOPPED";
    double uptime_seconds = 0.0;
};

} // namespace aether::vision
