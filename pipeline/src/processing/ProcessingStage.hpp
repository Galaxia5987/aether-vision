#pragma once

#include "IProcessor.hpp"
#include "core/Logger.hpp"
#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <cmath>

namespace aether::vision {

// Stage 1: Depth validation and range filtering
class DepthFilteringStage : public IProcessingStage {
public:
    std::string name() const override { return "DepthFiltering"; }

    bool process(ProcessingContext& ctx) override {
        if (!ctx.frame.has_depth || ctx.frame.depth_frame.empty()) {
            return true;
        }

        const cv::Mat& raw_depth = ctx.frame.depth_frame;
        const float depth_scale = ctx.frame.depth_scale;
        const float min_d = ctx.config.min_depth_m() > 0.0f ? ctx.config.min_depth_m() : 0.2f;
        const float max_d = ctx.config.max_depth_m() > 0.0f ? ctx.config.max_depth_m() : 6.0f;

        uint16_t min_raw = static_cast<uint16_t>(min_d / depth_scale);
        uint16_t max_raw = static_cast<uint16_t>(max_d / depth_scale);

        cv::Mat valid_mask;
        cv::inRange(raw_depth, cv::Scalar(min_raw), cv::Scalar(max_raw), valid_mask);

        int total_pixels = raw_depth.rows * raw_depth.cols;
        int valid_pixels = cv::countNonZero(valid_mask);
        double valid_pct = total_pixels > 0 ? (100.0 * valid_pixels / total_pixels) : 0.0;

        (*ctx.result.mutable_metrics())["valid_depth_pct"] = valid_pct;
        return true;
    }
};

// Stage 2: Color / Contour detection stage (HSV segmentation)
class ColorSegmentationStage : public IProcessingStage {
public:
    std::string name() const override { return "ColorSegmentation"; }

    bool process(ProcessingContext& ctx) override {
        if (!ctx.config.enable_color_filter() || !ctx.frame.has_color || ctx.frame.color_frame.empty()) {
            return true;
        }

        cv::Mat hsv;
        cv::cvtColor(ctx.frame.color_frame, hsv, cv::COLOR_BGR2HSV);

        cv::Scalar lower(ctx.config.hsv_h_min(), ctx.config.hsv_s_min(), ctx.config.hsv_v_min());
        cv::Scalar upper(ctx.config.hsv_h_max(), ctx.config.hsv_s_max(), ctx.config.hsv_v_max());

        cv::inRange(hsv, lower, upper, ctx.mask);

        cv::Mat kernel = cv::getStructuringElement(cv::MORPH_RECT, cv::Size(3, 3));
        cv::morphologyEx(ctx.mask, ctx.mask, cv::MORPH_OPEN, kernel);
        cv::morphologyEx(ctx.mask, ctx.mask, cv::MORPH_CLOSE, kernel);

        std::vector<std::vector<cv::Point>> contours;
        cv::findContours(ctx.mask, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

        int min_area = ctx.config.min_contour_area() > 0 ? ctx.config.min_contour_area() : 150;

        for (const auto& contour : contours) {
            double area = cv::contourArea(contour);
            if (area < min_area) {
                continue;
            }

            cv::Rect rect = cv::boundingRect(contour);
            cv::Moments m = cv::moments(contour);
            if (m.m00 == 0) continue;

            float cx = static_cast<float>(m.m10 / m.m00);
            float cy = static_cast<float>(m.m01 / m.m00);

            // Directly append to protobuf repeated Target3D field
            auto* target = ctx.result.add_targets();
            target->set_label("color_target");
            target->set_confidence(1.0f);
            target->set_pixel_x(cx);
            target->set_pixel_y(cy);

            auto* bbox = target->mutable_bbox();
            bbox->set_x(static_cast<float>(rect.x));
            bbox->set_y(static_cast<float>(rect.y));
            bbox->set_width(static_cast<float>(rect.width));
            bbox->set_height(static_cast<float>(rect.height));
        }

        (*ctx.result.mutable_metrics())["detected_targets"] = static_cast<double>(ctx.result.targets_size());
        return true;
    }
};

// Stage 3: Deproject 2D target detections to 3D camera coordinates using depth map
class Deprojection3DStage : public IProcessingStage {
public:
    std::string name() const override { return "Deprojection3D"; }

    bool process(ProcessingContext& ctx) override {
        if (ctx.result.targets_size() == 0 || !ctx.frame.has_depth || ctx.frame.depth_frame.empty()) {
            return true;
        }

        const cv::Mat& depth_mat = ctx.frame.depth_frame;
        const float depth_scale = ctx.frame.depth_scale;
        const auto& intrinsics = ctx.frame.depth_intrinsics;

        int rows = depth_mat.rows;
        int cols = depth_mat.cols;

        const float min_d = ctx.config.min_depth_m() > 0.0f ? ctx.config.min_depth_m() : 0.2f;
        const float max_d = ctx.config.max_depth_m() > 0.0f ? ctx.config.max_depth_m() : 6.0f;

        for (int i = 0; i < ctx.result.targets_size(); ++i) {
            auto* target = ctx.result.mutable_targets(i);
            int cx = static_cast<int>(std::round(target->pixel_x()));
            int cy = static_cast<int>(std::round(target->pixel_y()));

            // Sample a 5x5 window around centroid for robust depth (median filter against dropouts)
            std::vector<uint16_t> depth_samples;
            int half_win = 2;

            for (int dy = -half_win; dy <= half_win; ++dy) {
                int y = cy + dy;
                if (y < 0 || y >= rows) continue;

                const uint16_t* row_ptr = depth_mat.ptr<uint16_t>(y);
                for (int dx = -half_win; dx <= half_win; ++dx) {
                    int x = cx + dx;
                    if (x < 0 || x >= cols) continue;

                    uint16_t raw_val = row_ptr[x];
                    if (raw_val > 0) {
                        depth_samples.push_back(raw_val);
                    }
                }
            }

            float depth_m = 0.0f;
            if (!depth_samples.empty()) {
                std::sort(depth_samples.begin(), depth_samples.end());
                uint16_t median_raw = depth_samples[depth_samples.size() / 2];
                depth_m = median_raw * depth_scale;
            }

            auto* pos = target->mutable_position_3d();
            if (depth_m >= min_d && depth_m <= max_d) {
                float tx = 0.0f, ty = 0.0f, tz = 0.0f;
                intrinsics.deproject(target->pixel_x(), target->pixel_y(), depth_m, tx, ty, tz);
                pos->set_x(tx);
                pos->set_y(ty);
                pos->set_z(tz);
                target->set_distance_m(std::sqrt(tx * tx + ty * ty + tz * tz));
            } else {
                pos->set_x(0.0f);
                pos->set_y(0.0f);
                pos->set_z(0.0f);
                target->set_distance_m(0.0f);
            }
        }

        return true;
    }
};

} // namespace aether::vision
