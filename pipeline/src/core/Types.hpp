#pragma once

#include "vision_pipeline.pb.h"
#include <cstdint>
#include <string>
#include <memory>
#include <opencv2/core.hpp>

namespace aether::vision {

// Directly alias the Protobuf generated classes as our primary domain types
using proto::CommandType;
using proto::CameraState;
using proto::PipelineState;
using proto::Vector3;
using proto::BoundingBox2D;
using proto::Target3D;
using proto::CameraConfig;
using proto::ProcessingConfig;
using proto::PipelineCommand;
using proto::ProcessingResult;
using proto::SystemTelemetry;
using proto::PipelineStatus;
using proto::PipelineConfig;
using proto::CommandAck;
using proto::ErrorMessage;
using proto::PipelineMessage;

inline const char* cameraStateToString(CameraState state) {
    switch (state) {
        case proto::CAM_DISCONNECTED: return "DISCONNECTED";
        case proto::CAM_CONNECTING:   return "CONNECTING";
        case proto::CAM_STREAMING:    return "STREAMING";
        case proto::CAM_ERROR:        return "ERROR";
        default:                      return "UNKNOWN";
    }
}

inline const char* pipelineStateToString(PipelineState state) {
    switch (state) {
        case proto::PIPE_STOPPED:  return "STOPPED";
        case proto::PIPE_STARTING: return "STARTING";
        case proto::PIPE_RUNNING:  return "RUNNING";
        case proto::PIPE_PAUSED:   return "PAUSED";
        case proto::PIPE_STOPPING: return "STOPPING";
        default:                   return "UNKNOWN";
    }
}

// In-memory intrinsic calibration matrix
struct CameraIntrinsics {
    int width = 0;
    int height = 0;
    float ppx = 0.0f;              // Principal point X
    float ppy = 0.0f;              // Principal point Y
    float fx = 0.0f;               // Focal length X
    float fy = 0.0f;               // Focal length Y
    float coeffs[5] = {0.0f};      // Distortion coefficients
    bool valid = false;

    // Deprojects 2D pixel (u, v) and depth (Z in meters) into 3D metric coordinates (X, Y, Z in meters)
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

// In-memory frame container transferred between capture and processing threads
struct FrameBundle {
    uint64_t sequence_id = 0;
    double timestamp_ms = 0.0;
    cv::Mat color_frame;           // BGR 8-bit image
    cv::Mat depth_frame;           // 16-bit raw depth (or float depth in meters)
    CameraIntrinsics color_intrinsics;
    CameraIntrinsics depth_intrinsics;
    float depth_scale = 0.001f;    // meters per raw unit
    bool has_color = false;
    bool has_depth = false;
};

} // namespace aether::vision
