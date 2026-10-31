#pragma once

#include "core/Types.hpp"
#include <istream>
#include <iostream>
#include <atomic>
#include <thread>
#include <memory>
#include <vector>

namespace aether::vision {

class ICommandDispatcher {
public:
    virtual ~ICommandDispatcher() = default;
    virtual void dispatchCommand(const PipelineCommand& command) = 0;
};

class ProtobufStdinHandler {
public:
    explicit ProtobufStdinHandler(ICommandDispatcher& dispatcher, std::istream& input_stream = std::cin);
    ~ProtobufStdinHandler();

    void start();
    void stop();
    bool isRunning() const { return is_running_.load(); }

    void processCommand(const PipelineCommand& command);

private:
    void readLoop();

    ICommandDispatcher& dispatcher_;
    std::istream& is_;
    std::atomic<bool> is_running_;
    std::unique_ptr<std::thread> worker_thread_;
    std::vector<char> read_buffer_;
};

} // namespace aether::vision
