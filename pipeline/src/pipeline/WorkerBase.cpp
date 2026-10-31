#include "WorkerBase.hpp"
#include "core/Logger.hpp"

namespace aether::vision {

WorkerBase::WorkerBase(std::string name)
    : name_(std::move(name)),
      last_fps_time_(std::chrono::steady_clock::now()) {}

WorkerBase::~WorkerBase() {
    stop();
}

bool WorkerBase::start() {
    if (is_running_.exchange(true)) {
        return true;
    }

    is_paused_ = false;
    {
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        last_fps_time_ = std::chrono::steady_clock::now();
        window_count_ = 0;
    }

    onStart();
    thread_ = std::make_unique<std::thread>(&WorkerBase::threadEntry, this);
    LOG_INFO(name_ << " started");
    return true;
}

void WorkerBase::stop() {
    if (!is_running_.exchange(false)) {
        return;
    }

    onStop();
    if (thread_ && thread_->joinable()) {
        thread_->join();
    }
    LOG_INFO(name_ << " stopped");
}

void WorkerBase::pause() {
    is_paused_ = true;
    onPause();
    LOG_INFO(name_ << " paused");
}

void WorkerBase::resume() {
    is_paused_ = false;
    onResume();
    LOG_INFO(name_ << " resumed");
}

void WorkerBase::threadEntry() {
    LOG_INFO(name_ << " thread loop entered");
    workLoop();
    LOG_INFO(name_ << " thread loop finished");
}

void WorkerBase::trackProgress(uint64_t count) {
    total_count_.fetch_add(count, std::memory_order_relaxed);

    std::lock_guard<std::mutex> lock(metrics_mutex_);
    window_count_ += count;

    auto now = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(now - last_fps_time_).count();
    if (elapsed >= 1.0) {
        current_fps_ = static_cast<double>(window_count_) / elapsed;
        window_count_ = 0;
        last_fps_time_ = now;
    }
}

} // namespace aether::vision
