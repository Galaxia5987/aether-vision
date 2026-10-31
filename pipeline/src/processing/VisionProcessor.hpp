#pragma once

#include "IProcessor.hpp"
#include <vector>
#include <memory>
#include <mutex>

namespace aether::vision {

class VisionProcessor : public IProcessor {
public:
    VisionProcessor();
    explicit VisionProcessor(const ProcessingConfig& initial_config);
    ~VisionProcessor() override = default;

    bool process(const std::shared_ptr<const FrameBundle>& frame, ProcessingResult& out_result) override;
    void configure(const ProcessingConfig& config) override;
    ProcessingConfig getConfig() const override;

    void addStage(std::unique_ptr<IProcessingStage> stage);
    void clearStages();

private:
    void initDefaultStages();

    mutable std::mutex mutex_;
    ProcessingConfig config_;
    std::vector<std::unique_ptr<IProcessingStage>> stages_;
};

} // namespace aether::vision
