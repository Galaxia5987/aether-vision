#include "VisionProcessor.hpp"
#include "ProcessingStage.hpp"
#include "core/Logger.hpp"
#include <chrono>

namespace aether::vision {

VisionProcessor::VisionProcessor() {
    initDefaultStages();
}

VisionProcessor::VisionProcessor(const ProcessingConfig& initial_config)
    : config_(initial_config) {
    initDefaultStages();
}

void VisionProcessor::initDefaultStages() {
    stages_.push_back(std::make_unique<DepthFilteringStage>());
    stages_.push_back(std::make_unique<ColorSegmentationStage>());
    stages_.push_back(std::make_unique<Deprojection3DStage>());
}

void VisionProcessor::addStage(std::unique_ptr<IProcessingStage> stage) {
    std::lock_guard<std::mutex> lock(mutex_);
    stages_.push_back(std::move(stage));
}

void VisionProcessor::clearStages() {
    std::lock_guard<std::mutex> lock(mutex_);
    stages_.clear();
}

void VisionProcessor::configure(const ProcessingConfig& config) {
    std::lock_guard<std::mutex> lock(mutex_);
    config_ = config;
    for (auto& stage : stages_) {
        stage->configure(config_);
    }
    LOG_INFO("VisionProcessor updated configuration");
}

ProcessingConfig VisionProcessor::getConfig() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return config_;
}

bool VisionProcessor::process(const std::shared_ptr<const FrameBundle>& frame, ProcessingResult& out_result) {
    if (!frame) {
        return false;
    }

    auto start_time = std::chrono::steady_clock::now();

    ProcessingConfig current_config;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        current_config = config_;
    }

    out_result.set_sequence_id(frame->sequence_id);
    out_result.set_capture_timestamp_ms(frame->timestamp_ms);
    out_result.set_process_timestamp_ms(static_cast<double>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count()
    ));
    out_result.clear_targets();
    out_result.clear_metrics();

    ProcessingContext ctx{*frame, current_config, out_result, {}, {}, {}};

    std::lock_guard<std::mutex> lock(mutex_);
    for (const auto& stage : stages_) {
        auto stage_start = std::chrono::steady_clock::now();
        bool success = stage->process(ctx);
        auto stage_end = std::chrono::steady_clock::now();

        double stage_ms = std::chrono::duration<double, std::milli>(stage_end - stage_start).count();
        (*out_result.mutable_metrics())[stage->name() + "_ms"] = stage_ms;

        if (!success) {
            LOG_WARN("Stage " << stage->name() << " failed processing frame " << frame->sequence_id);
            break;
        }
    }

    auto end_time = std::chrono::steady_clock::now();
    double latency = std::chrono::duration<double, std::milli>(end_time - start_time).count();
    out_result.set_processing_latency_ms(latency);
    (*out_result.mutable_metrics())["total_latency_ms"] = latency;

    return true;
}

} // namespace aether::vision
