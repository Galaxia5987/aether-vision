//
// Created by adarw on 8/15/26.
//

#include "UsbCamera.hpp"
#include <opencv2/opencv.hpp>

namespace aethervision {

    struct UsbCamera::Impl {
        cv::VideoCapture cap;
    };

    UsbCamera::UsbCamera(int deviceId) : pImpl(std::make_unique<Impl>()) {
        if (!open(deviceId)) {
            throw std::runtime_error("Failed to initialize camera on device index " + std::to_string(deviceId));
        }
    }

    UsbCamera::~UsbCamera() = default;

    UsbCamera::UsbCamera(UsbCamera&&) noexcept = default;
    UsbCamera& UsbCamera::operator=(UsbCamera&&) noexcept = default;

    bool UsbCamera::open(int deviceId) {
        return pImpl->cap.open(deviceId, cv::CAP_ANY);
    }

    void UsbCamera::close() {
        if (pImpl->cap.isOpened()) {
            pImpl->cap.release();
        }
    }

    bool UsbCamera::isOpened() const {
        return pImpl->cap.isOpened();
    }

    cv::Mat UsbCamera::readFrame() {
        cv::Mat frame;

        if (!pImpl->cap.isOpened() || !pImpl->cap.read(frame)) {
            return cv::Mat();
        }

        return frame;
    }

    int UsbCamera::getWidth() const {
        return currentWidth;
    }

    int UsbCamera::getHeight() const {
        return currentHeight;
    }

    int UsbCamera::getChannels() const {
        return currentChannels;
    }

    std::vector<uint8_t> UsbCamera::encodeToJpeg(const cv::Mat& rawData, int quality) {
        if (rawData.empty()) {
            return cv::Mat();
        }

        std::vector<uint8_t> jpegBuffer;
        std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, quality};

        cv::imencode(".jpg", rawData, jpegBuffer, params);
        return jpegBuffer;
    }
} // aethervision