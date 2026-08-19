//
// Created by adarw on 8/16/26.
//

#ifndef AETHER_VISION_YOLODETECTOR_HPP
#define AETHER_VISION_YOLODETECTOR_HPP

#include <string>
#include <vector>
#include <memory>
#include <opencv2/core/mat.hpp>


namespace aethervision{
    struct BoundingBox {
        int x;
        int y;
        int width;
        int height;
    };

    struct Detection {
        BoundingBox box;
        float confidence;
        int class_id;
    };

    class YoloDetector {
    public:
        explicit YoloDetector(const std::string& modelPath, bool useCUDA = false);

        ~YoloDetector();

        YoloDetector(const YoloDetector&) = delete;
        YoloDetector& operator=(const YoloDetector&) = delete;
        YoloDetector(YoloDetector&&) noexcept;
        YoloDetector& operator=(YoloDetector&&) noexcept;

        std::vector<Detection> detect(const cv::Mat& imagePtr, float confThreshold = 0.25f, float iouThreshold = 0.45f);

    private:
        class Impl;
        std::unique_ptr<Impl> pImpl;
    };
} // aethervision

#endif //AETHER_VISION_YOLODETECTOR_HPP
