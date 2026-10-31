#pragma once

#include <queue>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <optional>
#include <atomic>

namespace aether::vision {

enum class QueueDropPolicy {
    DropOldest,  // Evicts oldest item when queue is full (ideal for real-time vision)
    DropNewest,  // Discards incoming item if full
    Block        // Producer waits until space is available
};

template <typename T>
class ThreadSafeQueue {
public:
    explicit ThreadSafeQueue(size_t max_capacity = 2, QueueDropPolicy policy = QueueDropPolicy::DropOldest)
        : max_capacity_(max_capacity > 0 ? max_capacity : 1),
          drop_policy_(policy),
          dropped_count_(0),
          stopped_(false) {}

    ~ThreadSafeQueue() {
        stop();
    }

    // Push an item into the queue according to the configured drop policy
    bool push(T item) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (stopped_) {
            return false;
        }

        if (queue_.size() >= max_capacity_) {
            switch (drop_policy_) {
                case QueueDropPolicy::DropOldest:
                    queue_.pop();
                    dropped_count_.fetch_add(1, std::memory_order_relaxed);
                    break;
                case QueueDropPolicy::DropNewest:
                    dropped_count_.fetch_add(1, std::memory_order_relaxed);
                    return false;
                case QueueDropPolicy::Block:
                    cv_not_full_.wait(lock, [this] {
                        return queue_.size() < max_capacity_ || stopped_;
                    });
                    if (stopped_) {
                        return false;
                    }
                    break;
            }
        }

        queue_.push(std::move(item));
        lock.unlock();
        cv_not_empty_.notify_one();
        return true;
    }

    // Wait until an item is available or queue is stopped
    bool pop(T& out_item) {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_not_empty_.wait(lock, [this] {
            return !queue_.empty() || stopped_;
        });

        if (queue_.empty() || stopped_) {
            return false;
        }

        out_item = std::move(queue_.front());
        queue_.pop();
        lock.unlock();
        cv_not_full_.notify_one();
        return true;
    }

    // Wait with timeout
    template <typename Rep, typename Period>
    bool pop_for(T& out_item, const std::chrono::duration<Rep, Period>& timeout) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!cv_not_empty_.wait_for(lock, timeout, [this] {
            return !queue_.empty() || stopped_;
        })) {
            return false; // Timed out
        }

        if (queue_.empty() || stopped_) {
            return false;
        }

        out_item = std::move(queue_.front());
        queue_.pop();
        lock.unlock();
        cv_not_full_.notify_one();
        return true;
    }

    // Non-blocking try_pop
    bool try_pop(T& out_item) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (queue_.empty() || stopped_) {
            return false;
        }

        out_item = std::move(queue_.front());
        queue_.pop();
        lock.unlock();
        cv_not_full_.notify_one();
        return true;
    }

    void stop() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            stopped_ = true;
        }
        cv_not_empty_.notify_all();
        cv_not_full_.notify_all();
    }

    void resume() {
        std::lock_guard<std::mutex> lock(mutex_);
        stopped_ = false;
    }

    void clear() {
        std::lock_guard<std::mutex> lock(mutex_);
        while (!queue_.empty()) {
            queue_.pop();
        }
        cv_not_full_.notify_all();
    }

    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }

    bool empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.empty();
    }

    uint64_t get_dropped_count() const {
        return dropped_count_.load(std::memory_order_relaxed);
    }

    void reset_dropped_count() {
        dropped_count_.store(0, std::memory_order_relaxed);
    }

private:
    const size_t max_capacity_;
    const QueueDropPolicy drop_policy_;
    std::queue<T> queue_;
    mutable std::mutex mutex_;
    std::condition_variable cv_not_empty_;
    std::condition_variable cv_not_full_;
    std::atomic<uint64_t> dropped_count_;
    std::atomic<bool> stopped_;
};

} // namespace aether::vision
