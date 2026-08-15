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

    std::vector<uint8_t> UsbCamera::readFrame() {
        cv::Mat frame;

        if (!pImpl->cap.isOpened() || !pImpl->cap.read(frame)) {
            return std::vector<uint8_t>();
        }

        currentWidth = frame.cols;
        currentHeight = frame.rows;
        currentChannels = frame.channels();

        size_t sizeInBytes = frame.total() * frame.elemSize();
        return std::vector<uint8_t>(frame.data, frame.data + sizeInBytes);
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

    std::vector<uint8_t> UsbCamera::encodeToJpeg(const std::vector<uint8_t>& rawData, int width, int height, int channels, int quality) {
        if (rawData.empty() || width <= 0 || height <= 0 || channels <= 0) {
            return std::vector<uint8_t>();
        }

        int type = CV_MAKETYPE(CV_8U, channels);
        cv::Mat mat(height, width, type, const_cast<uint8_t*>(rawData.data()));

        std::vector<uint8_t> jpegBuffer;
        std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, quality};

        cv::imencode(".jpg", mat, jpegBuffer, params);
        return jpegBuffer;
    }
} // aethervision