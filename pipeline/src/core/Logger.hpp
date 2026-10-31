#pragma once

#include <iostream>
#include <mutex>
#include <string>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>

namespace aether::vision {

enum class LogLevel {
    DEBUG,
    INFO,
    WARN,
    ERROR
};

class Logger {
public:
    static Logger& instance() {
        static Logger instance;
        return instance;
    }

    void set_level(LogLevel level) {
        std::lock_guard<std::mutex> lock(mutex_);
        current_level_ = level;
    }

    void log(LogLevel level, const std::string& message) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (level < current_level_) {
            return;
        }

        auto now = std::chrono::system_clock::now();
        auto in_time_t = std::chrono::system_clock::to_time_t(now);
        auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;

        std::tm tm_buf{};
#if defined(_WIN32)
        localtime_s(&tm_buf, &in_time_t);
#else
        localtime_r(&in_time_t, &tm_buf);
#endif

        std::cerr << "[" << std::put_time(&tm_buf, "%Y-%m-%d %H:%M:%S")
                  << "." << std::setfill('0') << std::setw(3) << ms.count() << "] ["
                  << level_to_string(level) << "] "
                  << message << std::endl;
    }

    static void debug(const std::string& msg) { instance().log(LogLevel::DEBUG, msg); }
    static void info(const std::string& msg)  { instance().log(LogLevel::INFO, msg); }
    static void warn(const std::string& msg)  { instance().log(LogLevel::WARN, msg); }
    static void error(const std::string& msg) { instance().log(LogLevel::ERROR, msg); }

private:
    Logger() : current_level_(LogLevel::INFO) {}

    static const char* level_to_string(LogLevel level) {
        switch (level) {
            case LogLevel::DEBUG: return "DEBUG";
            case LogLevel::INFO:  return "INFO";
            case LogLevel::WARN:  return "WARN";
            case LogLevel::ERROR: return "ERROR";
            default:              return "UNKNOWN";
        }
    }

    LogLevel current_level_;
    std::mutex mutex_;
};

#define LOG_DEBUG(msg) do { std::ostringstream _oss; _oss << msg; ::aether::vision::Logger::debug(_oss.str()); } while(0)
#define LOG_INFO(msg)  do { std::ostringstream _oss; _oss << msg; ::aether::vision::Logger::info(_oss.str()); } while(0)
#define LOG_WARN(msg)  do { std::ostringstream _oss; _oss << msg; ::aether::vision::Logger::warn(_oss.str()); } while(0)
#define LOG_ERROR(msg) do { std::ostringstream _oss; _oss << msg; ::aether::vision::Logger::error(_oss.str()); } while(0)

} // namespace aether::vision
