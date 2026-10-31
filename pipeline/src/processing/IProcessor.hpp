#pragma once

#include "core/Types.hpp"
#include <memory>
#include <vector>
#include <string>

namespace aether::vision {

struct ProcessingContext {
    const FrameBundle& frame;
    const ProcessingConfig& config;
    ProcessingResult& result;

    // Optional intermediate artifacts shared across stages
    cv::Mat processed_color;
    cv::Mat processed_depth;
    cv::Mat mask;
};

class IProcessingStage {
public:
    virtual ~IProcessingStage() = default;
    virtual std::string name() const = 0;
    virtual bool process(ProcessingContext& ctx) = 0;
    virtual void configure(const ProcessingConfig& /*config*/) {}
};

class IProcessor {
public:
    virtual ~IProcessor() = default;
    virtual bool process(const std::shared_ptr<const FrameBundle>& frame, ProcessingResult& out_result) = 0;
    virtual void configure(const ProcessingConfig& config) = 0;
    virtual ProcessingConfig getConfig() const = 0;
};

} // namespace aether::vision
