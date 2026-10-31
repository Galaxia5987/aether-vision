#pragma once

#include "WorkerBase.hpp"
#include "core/Types.hpp"
#include "core/ThreadSafeQueue.hpp"
#include "processing/IProcessor.hpp"

#include <mutex>
#include <memory>

namespace aether::vision {

class ProcessingWorker : public WorkerBase {
public:
    ProcessingWorker(
        std::shared_ptr<IProcessor> processor,
        ThreadSafeQueue<std::shared_ptr<FrameBundle>>& frame_queue,
        ThreadSafeQueue<ProcessingResult>& result_queue,
        const ProcessingConfig& initial_config = {}
    );
    ~ProcessingWorker() override = default;

    void configure(const ProcessingConfig& config);
    ProcessingConfig getConfig() const;

protected:
    void workLoop() override;

private:
    std::shared_ptr<IProcessor> processor_;
    ThreadSafeQueue<std::shared_ptr<FrameBundle>>& frame_queue_;
    ThreadSafeQueue<ProcessingResult>& result_queue_;

    mutable std::mutex config_mutex_;
    ProcessingConfig config_;
};

} // namespace aether::vision
