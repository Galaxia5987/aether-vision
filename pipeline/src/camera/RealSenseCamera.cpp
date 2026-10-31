#include "RealSenseCamera.hpp"
#include "core/Logger.hpp"
#include <chrono>

namespace aether::vision {

RealSenseCamera::RealSenseCamera()
    : state_(CameraState::DISCONNECTED),
      is_streaming_(false) {}

RealSenseCamera::~RealSenseCamera() {
    RealSenseCamera::stop();
}

bool RealSenseCamera::isDeviceAvailable() const {
    try {
        auto dev_list = ctx_.query_devices();
        if (dev_list.size() == 0) {
            return false;
        }

        if (config_.serial_number.empty()) {
            return true;
        }

        for (const auto& dev : dev_list) {
            if (dev.supports(RS2_CAMERA_INFO_SERIAL_NUMBER)) {
                if (config_.serial_number == dev.get_info(RS2_CAMERA_INFO_SERIAL_NUMBER)) {
                    return true;
                }
            }
        }
        return false;
    } catch (const std::exception& e) {
        LOG_WARN("RealSense device check exception: " << e.what());
        return false;
    }
}

bool RealSenseCamera::initialize(const CameraConfig& config) {
    std::lock_guard<std::mutex> lock(mutex_);
    config_ = config;
    state_ = CameraState::CONNECTING;

    try {
        auto dev_list = ctx_.query_devices();
        if (dev_list.size() == 0) {
            LOG_WARN("No RealSense devices detected during initialization");
            state_ = CameraState::DISCONNECTED;
            return false;
        }

        bool found = false;
        if (!config_.serial_number.empty()) {
            for (const auto& dev : dev_list) {
                if (dev.supports(RS2_CAMERA_INFO_SERIAL_NUMBER) &&
                    config_.serial_number == dev.get_info(RS2_CAMERA_INFO_SERIAL_NUMBER)) {
                    device_ = dev;
                    found = true;
                    break;
                }
            }
        } else {
            device_ = dev_list[0];
            found = true;
        }

        if (!found) {
            LOG_ERROR("Specified RealSense device serial " << config_.serial_number << " not found");
            state_ = CameraState::DISCONNECTED;
            return false;
        }

        if (device_.supports(RS2_CAMERA_INFO_NAME)) {
            device_name_ = device_.get_info(RS2_CAMERA_INFO_NAME);
        } else {
            device_name_ = "Intel RealSense";
        }

        if (device_.supports(RS2_CAMERA_INFO_SERIAL_NUMBER)) {
            serial_number_ = device_.get_info(RS2_CAMERA_INFO_SERIAL_NUMBER);
        }

        LOG_INFO("Configured RealSense device: " << device_name_ << " (S/N: " << serial_number_ << ")");

        // Reset config
        cfg_ = rs2::config();
        if (!serial_number_.empty()) {
            cfg_.enable_device(serial_number_);
        }

        if (config_.enable_color) {
            cfg_.enable_stream(RS2_STREAM_COLOR, config_.width, config_.height, RS2_FORMAT_BGR8, config_.fps);
        }
        if (config_.enable_depth) {
            cfg_.enable_stream(RS2_STREAM_DEPTH, config_.width, config_.height, RS2_FORMAT_Z16, config_.fps);
        }

        if (config_.align_depth_to_color) {
            align_to_color_ = std::make_unique<rs2::align>(RS2_STREAM_COLOR);
        } else {
            align_to_color_.reset();
        }

        return true;
    } catch (const rs2::error& e) {
        LOG_ERROR("RealSense error initializing: " << e.what());
        state_ = CameraState::ERROR_STATE;
        return false;
    } catch (const std::exception& e) {
        LOG_ERROR("Exception initializing RealSense: " << e.what());
        state_ = CameraState::ERROR_STATE;
        return false;
    }
}

bool RealSenseCamera::start() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (is_streaming_) {
        return true;
    }

    try {
        LOG_INFO("Starting RealSense pipeline stream...");
        profile_ = pipe_.start(cfg_);
        is_streaming_ = true;
        state_ = CameraState::STREAMING;

        querySensorsAndIntrinsics();
        applySettings(config_);

        LOG_INFO("RealSense streaming successfully started.");
        return true;
    } catch (const rs2::error& e) {
        LOG_ERROR("RealSense error starting stream: " << e.what());
        state_ = CameraState::ERROR_STATE;
        is_streaming_ = false;
        return false;
    } catch (const std::exception& e) {
        LOG_ERROR("Exception starting RealSense: " << e.what());
        state_ = CameraState::ERROR_STATE;
        is_streaming_ = false;
        return false;
    }
}

void RealSenseCamera::stop() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!is_streaming_) {
        return;
    }

    try {
        LOG_INFO("Stopping RealSense pipeline stream...");
        pipe_.stop();
    } catch (const std::exception& e) {
        LOG_WARN("Exception while stopping pipeline: " << e.what());
    }

    is_streaming_ = false;
    state_ = CameraState::DISCONNECTED;
}

bool RealSenseCamera::isStreaming() const {
    return is_streaming_.load();
}

CameraState RealSenseCamera::getState() const {
    return state_.load();
}

void RealSenseCamera::querySensorsAndIntrinsics() {
    try {
        // Query depth scale
        auto dev = profile_.get_device();
        for (auto&& sensor : dev.query_sensors()) {
            if (sensor.is<rs2::depth_sensor>()) {
                depth_scale_ = sensor.as<rs2::depth_sensor>().get_depth_scale();
                LOG_INFO("Depth sensor scale: " << depth_scale_ << " m/unit");
                break;
            }
        }

        updateIntrinsicsFromProfile();
    } catch (const std::exception& e) {
        LOG_WARN("Could not read all sensor intrinsics: " << e.what());
    }
}

void RealSenseCamera::updateIntrinsicsFromProfile() {
    try {
        if (config_.enable_color) {
            auto color_stream = profile_.get_stream(RS2_STREAM_COLOR).as<rs2::video_stream_profile>();
            rs2_intrinsics intr = color_stream.get_intrinsics();
            color_intrinsics_.width = intr.width;
            color_intrinsics_.height = intr.height;
            color_intrinsics_.ppx = intr.ppx;
            color_intrinsics_.ppy = intr.ppy;
            color_intrinsics_.fx = intr.fx;
            color_intrinsics_.fy = intr.fy;
            for (int i = 0; i < 5; ++i) {
                color_intrinsics_.coeffs[i] = intr.coeffs[i];
            }
            color_intrinsics_.valid = true;
        }

        if (config_.enable_depth) {
            auto depth_stream = profile_.get_stream(RS2_STREAM_DEPTH).as<rs2::video_stream_profile>();
            rs2_intrinsics intr = depth_stream.get_intrinsics();
            depth_intrinsics_.width = intr.width;
            depth_intrinsics_.height = intr.height;
            depth_intrinsics_.ppx = intr.ppx;
            depth_intrinsics_.ppy = intr.ppy;
            depth_intrinsics_.fx = intr.fx;
            depth_intrinsics_.fy = intr.fy;
            for (int i = 0; i < 5; ++i) {
                depth_intrinsics_.coeffs[i] = intr.coeffs[i];
            }
            depth_intrinsics_.valid = true;
        }
    } catch (const std::exception& e) {
        LOG_WARN("Failed to extract stream intrinsics: " << e.what());
    }
}

bool RealSenseCamera::capture(FrameBundle& out_bundle, std::chrono::milliseconds timeout) {
    if (!is_streaming_.load()) {
        return false;
    }

    try {
        rs2::frameset frames = pipe_.wait_for_frames(static_cast<unsigned int>(timeout.count()));
        if (!frames) {
            return false;
        }

        if (align_to_color_) {
            frames = align_to_color_->process(frames);
        }

        double frame_ts = frames.get_timestamp();

        rs2::video_frame color_f = frames.get_color_frame();
        rs2::depth_frame depth_f = frames.get_depth_frame();

        out_bundle.sequence_id = ++sequence_counter_;
        out_bundle.timestamp_ms = frame_ts;
        out_bundle.depth_scale = depth_scale_;

        if (color_f) {
            int cw = color_f.get_width();
            int ch = color_f.get_height();
            out_bundle.color_frame = cv::Mat(cv::Size(cw, ch), CV_8UC3, const_cast<void*>(color_f.get_data()), cv::Mat::AUTO_STEP).clone();
            out_bundle.has_color = true;
            out_bundle.color_intrinsics = color_intrinsics_;
        } else {
            out_bundle.has_color = false;
        }

        if (depth_f) {
            int dw = depth_f.get_width();
            int dh = depth_f.get_height();
            out_bundle.depth_frame = cv::Mat(cv::Size(dw, dh), CV_16UC1, const_cast<void*>(depth_f.get_data()), cv::Mat::AUTO_STEP).clone();
            out_bundle.has_depth = true;
            // If aligned to color, depth intrinsics match color intrinsics
            out_bundle.depth_intrinsics = align_to_color_ ? color_intrinsics_ : depth_intrinsics_;
        } else {
            out_bundle.has_depth = false;
        }

        return true;
    } catch (const rs2::error& e) {
        LOG_ERROR("RealSense error during frame capture: " << e.what());
        state_ = CameraState::ERROR_STATE;
        return false;
    } catch (const std::exception& e) {
        LOG_ERROR("Exception during frame capture: " << e.what());
        state_ = CameraState::ERROR_STATE;
        return false;
    }
}

bool RealSenseCamera::applySettings(const CameraConfig& config) {
    std::lock_guard<std::mutex> lock(mutex_);
    config_ = config;

    if (!is_streaming_) {
        return true;
    }

    try {
        auto dev = profile_.get_device();
        for (auto&& sensor : dev.query_sensors()) {
            if (sensor.is<rs2::depth_sensor>()) {
                auto depth_sens = sensor.as<rs2::depth_sensor>();

                if (depth_sens.supports(RS2_OPTION_EMITTER_ENABLED)) {
                    depth_sens.set_option(RS2_OPTION_EMITTER_ENABLED, config_.emitter_enabled ? 1.0f : 0.0f);
                }
                if (depth_sens.supports(RS2_OPTION_LASER_POWER)) {
                    depth_sens.set_option(RS2_OPTION_LASER_POWER, static_cast<float>(config_.laser_power));
                }
                if (depth_sens.supports(RS2_OPTION_ENABLE_AUTO_EXPOSURE)) {
                    depth_sens.set_option(RS2_OPTION_ENABLE_AUTO_EXPOSURE, config_.auto_exposure ? 1.0f : 0.0f);
                }
                if (!config_.auto_exposure && depth_sens.supports(RS2_OPTION_EXPOSURE)) {
                    depth_sens.set_option(RS2_OPTION_EXPOSURE, static_cast<float>(config_.exposure));
                }
                if (!config_.auto_exposure && depth_sens.supports(RS2_OPTION_GAIN)) {
                    depth_sens.set_option(RS2_OPTION_GAIN, static_cast<float>(config_.gain));
                }
            } else if (sensor.is<rs2::color_sensor>()) {
                auto color_sens = sensor.as<rs2::color_sensor>();
                if (color_sens.supports(RS2_OPTION_ENABLE_AUTO_EXPOSURE)) {
                    color_sens.set_option(RS2_OPTION_ENABLE_AUTO_EXPOSURE, config_.auto_exposure ? 1.0f : 0.0f);
                }
                if (!config_.auto_exposure && color_sens.supports(RS2_OPTION_EXPOSURE)) {
                    color_sens.set_option(RS2_OPTION_EXPOSURE, static_cast<float>(config_.exposure));
                }
                if (!config_.auto_exposure && color_sens.supports(RS2_OPTION_GAIN)) {
                    color_sens.set_option(RS2_OPTION_GAIN, static_cast<float>(config_.gain));
                }
            }
        }
        LOG_INFO("Applied camera hardware settings successfully");
        return true;
    } catch (const rs2::error& e) {
        LOG_WARN("RealSense error applying settings: " << e.what());
        return false;
    } catch (const std::exception& e) {
        LOG_WARN("Exception applying settings: " << e.what());
        return false;
    }
}

std::string RealSenseCamera::getDeviceName() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return device_name_;
}

std::string RealSenseCamera::getSerialNumber() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return serial_number_;
}

CameraIntrinsics RealSenseCamera::getColorIntrinsics() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return color_intrinsics_;
}

CameraIntrinsics RealSenseCamera::getDepthIntrinsics() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return depth_intrinsics_;
}

float RealSenseCamera::getDepthScale() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return depth_scale_;
}

} // namespace aether::vision
