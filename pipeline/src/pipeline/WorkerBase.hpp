#pragma once

#include <string>
#include <thread>
#include <atomic>
#include <memory>
#include <chrono>
#include <mutex>

namespace aether::vision {

class WorkerBase {
public:
    explicit WorkerBase(std::string name);
    virtual ~WorkerBase();

    WorkerBase(const WorkerBase&) = delete;
    WorkerBase& operator=(const WorkerBase&) = delete;

    virtual bool start();
    virtual void stop();
    virtual void pause();
    virtual void resume();

    bool isRunning() const { return is_running_.load(); }
    bool isPaused() const { return is_paused_.load(); }
    double getFps() const { return current_fps_.load(); }
    uint64_t getTotalFrames() const { return total_count_.load(std::memory_order_relaxed); }
    const std::string& getName() const { return name_; }

protected:
    virtual void workLoop() = 0;

    virtual void onStart() {}
    virtual void onStop() {}
    virtual void onPause() {}
    virtual void onResume() {}

    void trackProgress(uint64_t count = 1);

    std::string name_;
    std::atomic<bool> is_running_{false};
    std::atomic<bool> is_paused_{false};
    std::unique_ptr<std::thread> thread_;

    std::atomic<uint64_t> total_count_{0};
    std::atomic<double> current_fps_{0.0};
    std::chrono::steady_clock::time_point last_fps_time_;
    uint64_t window_count_{0};
    std::mutex metrics_mutex_;

private:
    void threadEntry();
};

} // namespace aether::vision
