//
// Created by adarw on 8/16/26.
//

#include "YoloDetector.hpp"
#include <onnxruntime_cxx_api.h>
#include <opencv2/opencv.hpp>
#include <cstring>
#include <algorithm>

namespace aethervision{

    class YoloDetector::Impl {
    public:
        Impl(const std::string& modelPath, bool useCUDA) {
            printf("Hello World!\n");
            env_ = Ort::Env(ORT_LOGGING_LEVEL_INFO, "YOLO_Inference");
            sessionOptions_ = Ort::SessionOptions();

            if (useCUDA) {
                OrtCUDAProviderOptions cudaOptions;
                sessionOptions_.AppendExecutionProvider_CUDA(cudaOptions);
            }

            session_ = std::make_unique<Ort::Session>(env_, modelPath.c_str(), sessionOptions_);

            Ort::TypeInfo inputTypeInfo = session_->GetInputTypeInfo(0);
            auto inputTensorInfo = inputTypeInfo.GetTensorTypeAndShapeInfo();
            inputDims_ = inputTensorInfo.GetShape();

            if (inputDims_[0] == -1) inputDims_[0] = 1;

            Ort::TypeInfo outputTypeInfo = session_->GetOutputTypeInfo(0);
            auto outputTensorInfo = outputTypeInfo.GetTensorTypeAndShapeInfo();
            outputDims_ = outputTensorInfo.GetShape();

            Ort::AllocatorWithDefaultOptions allocator;

            // Extract string directly into a std::string and store the C-string pointer
            auto allocatedInputName = session_->GetInputNameAllocated(0, allocator);
            inputNamesStr_.push_back(allocatedInputName.get());
            inputNamesCStr_.push_back(inputNamesStr_.back().c_str());

            auto allocatedOutputName = session_->GetOutputNameAllocated(0, allocator);
            outputNamesStr_.push_back(allocatedOutputName.get());
            outputNamesCStr_.push_back(outputNamesStr_.back().c_str());
        }

        std::vector<Detection> detect(const cv::Mat& image, float confThreshold, float iouThreshold) {
            float scale;
            int padW, padH;
            cv::Mat preprocessedImage = preprocess(image, scale, padW, padH);

            size_t inputTensorSize = 1;
            for (auto dim : inputDims_) inputTensorSize *= dim;

            std::vector<float> inputTensorValues(inputTensorSize);

            cv::Mat channels[3];
            cv::split(preprocessedImage, channels);
            int channelSize = inputDims_[2] * inputDims_[3];
            for (int i = 0; i < 3; ++i) {
                std::memcpy(inputTensorValues.data() + i * channelSize, channels[i].data, channelSize * sizeof(float));
            }

            auto memoryInfo = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
            Ort::Value inputTensor = Ort::Value::CreateTensor<float>(
                memoryInfo, inputTensorValues.data(), inputTensorSize, inputDims_.data(), inputDims_.size());

            auto outputTensors = session_->Run(
                Ort::RunOptions{nullptr}, inputNamesCStr_.data(), &inputTensor, 1, outputNamesCStr_.data(), 1);

            float* outputData = outputTensors[0].GetTensorMutableData<float>();

            int numChannels = outputDims_[1];
            int numAnchors = outputDims_[2];

            cv::Mat outputMat(numChannels, numAnchors, CV_32F, outputData);
            outputMat = outputMat.t();

            std::vector<cv::Rect> boxes;
            std::vector<float> confidences;
            std::vector<int> classIds;

            for (int i = 0; i < numAnchors; ++i) {
                float* rowPtr = outputMat.ptr<float>(i);
                float maxClassScore = 0.0f;
                int classId = -1;

                for (int c = 4; c < numChannels; ++c) {
                    if (rowPtr[c] > maxClassScore) {
                        maxClassScore = rowPtr[c];
                        classId = c - 4;
                    }
                }

                if (maxClassScore > confThreshold) {
                    float cx = rowPtr[0];
                    float cy = rowPtr[1];
                    float w = rowPtr[2];
                    float h = rowPtr[3];

                    int left = static_cast<int>((cx - w / 2.0f - padW) / scale);
                    int top = static_cast<int>((cy - h / 2.0f - padH) / scale);
                    int width = static_cast<int>(w / scale);
                    int height = static_cast<int>(h / scale);

                    boxes.push_back(cv::Rect(left, top, width, height));
                    confidences.push_back(maxClassScore);
                    classIds.push_back(classId);
                }
            }

            std::vector<int> indices;
            cv::dnn::NMSBoxes(boxes, confidences, confThreshold, iouThreshold, indices);

            std::vector<Detection> results;
            for (int idx : indices) {
                BoundingBox bbox{boxes[idx].x, boxes[idx].y, boxes[idx].width, boxes[idx].height};
                results.push_back({bbox, confidences[idx], classIds[idx]});
            }

            return results;
        }

    private:
        Ort::Env env_{nullptr};
        Ort::SessionOptions sessionOptions_{nullptr};
        std::unique_ptr<Ort::Session> session_;

        // REPLACE AllocatedStringPtr with standard strings
        std::vector<std::string> inputNamesStr_;
        std::vector<std::string> outputNamesStr_;

        std::vector<const char*> inputNamesCStr_;
        std::vector<const char*> outputNamesCStr_;

        std::vector<int64_t> inputDims_;
        std::vector<int64_t> outputDims_;

        cv::Mat preprocess(const cv::Mat& image, float& scale, int& padW, int& padH) {
            int inputW = inputDims_[3];
            int inputH = inputDims_[2];

            scale = std::min(static_cast<float>(inputW) / image.cols, static_cast<float>(inputH) / image.rows);
            int newW = static_cast<int>(image.cols * scale);
            int newH = static_cast<int>(image.rows * scale);

            padW = (inputW - newW) / 2;
            padH = (inputH - newH) / 2;

            cv::Mat resizedImage;
            cv::resize(image, resizedImage, cv::Size(newW, newH));

            cv::Mat paddedImage(inputH, inputW, CV_8UC3, cv::Scalar(114, 114, 114));
            resizedImage.copyTo(paddedImage(cv::Rect(padW, padH, newW, newH)));

            cv::Mat floatImage;
            paddedImage.convertTo(floatImage, CV_32FC3, 1.0 / 255.0);
            cv::cvtColor(floatImage, floatImage, cv::COLOR_BGR2RGB);

            return floatImage;
        }
    };

    YoloDetector::YoloDetector(const std::string& modelPath, bool useCUDA)
        : pImpl(std::make_unique<Impl>(modelPath, useCUDA)) {}

    YoloDetector::~YoloDetector() = default;

    YoloDetector::YoloDetector(YoloDetector&&) noexcept = default;
    YoloDetector& YoloDetector::operator=(YoloDetector&&) noexcept = default;

    std::vector<Detection> YoloDetector::detect(const cv::Mat& image, float confThreshold, float iouThreshold) {

        return pImpl->detect(image, confThreshold, iouThreshold);
    }
} // aethervision