#include "camera/RealSenseCamera.hpp"
#include "processing/VisionProcessor.hpp"
#include "io/ProtobufPublisher.hpp"
#include "io/ProtobufStdinHandler.hpp"
#include "pipeline/PipelineManager.hpp"
#include "core/Logger.hpp"

#include <csignal>
#include <atomic>
#include <memory>
#include <iostream>

namespace {
    std::atomic<bool> g_shutdown_requested{false};
    std::shared_ptr<aether::vision::PipelineManager> g_pipeline;

    void signalHandler(int signum) {
        if (signum == SIGINT || signum == SIGTERM) {
            LOG_INFO("Interrupt signal (" << signum << ") received. Requesting shutdown...");
            g_shutdown_requested = true;
            if (g_pipeline) {
                g_pipeline->stop();
            }
        }
    }
}

int main(int /*argc*/, char** /*argv*/) {
    // Configure signal handling for graceful shutdown
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);

    LOG_INFO("Initializing Aether RealSense Vision Pipeline (Protobuf Native)...");

    try {
        // 1. Initial configurations (Protobuf structs used directly)
        aether::vision::CameraConfig cam_config;
        cam_config.set_width(640);
        cam_config.set_height(480);
        cam_config.set_fps(30);
        cam_config.set_enable_color(true);
        cam_config.set_enable_depth(true);
        cam_config.set_align_depth_to_color(true);
        cam_config.set_auto_exposure(true);
        cam_config.set_laser_power(150);
        cam_config.set_emitter_enabled(true);

        aether::vision::ProcessingConfig proc_config;
        proc_config.set_min_depth_m(0.2f);
        proc_config.set_max_depth_m(5.0f);
        proc_config.set_enable_color_filter(false);

        // 2. Instantiate abstract subsystem components
        auto camera = std::make_shared<aether::vision::RealSenseCamera>();
        auto processor = std::make_shared<aether::vision::VisionProcessor>(proc_config);
        auto publisher = std::make_shared<aether::vision::ProtobufPublisher>(std::cout);

        // 3. Instantiate pipeline manager orchestrating the 3 threads
        auto pipeline = std::make_shared<aether::vision::PipelineManager>(
            camera,
            processor,
            publisher,
            cam_config,
            proc_config
        );
        g_pipeline = pipeline;

        // 4. Instantiate Protobuf STDIN command listener
        aether::vision::ProtobufStdinHandler stdin_handler(*pipeline, std::cin);

        // 5. Start STDIN listener & pipeline threads
        stdin_handler.start();
        pipeline->start();

        LOG_INFO("Pipeline running. Listening for Protobuf commands on STDIN, publishing Protobuf messages to STDOUT.");

        // 6. Main loop waiting for shutdown
        while (!g_shutdown_requested.load() && pipeline->isRunning()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }

        LOG_INFO("Shutting down Vision Pipeline...");
        stdin_handler.stop();
        pipeline->stop();
        g_pipeline.reset();

        LOG_INFO("Pipeline shut down cleanly.");
        return 0;

    } catch (const std::exception& e) {
        LOG_ERROR("Fatal exception in vision pipeline: " << e.what());
        return 1;
    }
}
