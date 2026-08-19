//
// Created by adarw on 8/15/26.
//

#ifndef AETHER_VISION_USBCAMERA_HPP
#define AETHER_VISION_USBCAMERA_HPP

#include <vector>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <opencv2/core/mat.hpp>

namespace aethervision
{
    class UsbCamera {
    public:
        explicit UsbCamera(int deviceId = 0);
        ~UsbCamera();

        UsbCamera(const UsbCamera&) = delete;
        UsbCamera& operator=(const UsbCamera&) = delete;

        UsbCamera(UsbCamera&&) noexcept;
        UsbCamera& operator=(UsbCamera&&) noexcept;

        bool open(int deviceId);
        void close();
        bool isOpened() const;

        cv::Mat readFrame();

        int getWidth() const;
        int getHeight() const;
        int getChannels() const;

        static std::vector<uint8_t> encodeToJpeg(const cv::Mat& rawData, int quality = 95);

    private:
        struct Impl;
        std::unique_ptr<Impl> pImpl;

        int currentWidth{0};
        int currentHeight{0};
        int currentChannels{0};
    };
} // aethervision

#endif //AETHER_VISION_USBCAMERA_HPP