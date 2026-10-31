#include <iostream>
#include <librealsense2/rs.hpp>

int main() {
    try {
        std::cout << "RealSense SDK Version: " << RS2_API_VERSION_STR << std::endl;

        rs2::context ctx;
        auto devices = ctx.query_devices();
        std::cout << "Connected RealSense devices: " << devices.size() << std::endl;

        for (const auto& dev : devices) {
            std::cout << "  - " << dev.get_info(RS2_CAMERA_INFO_NAME)
                      << " (S/N: " << dev.get_info(RS2_CAMERA_INFO_SERIAL_NUMBER) << ")"
                      << std::endl;
        }
    } catch (const rs2::error& e) {
        std::cerr << "RealSense error calling " << e.get_failed_function()
                  << "(" << e.get_failed_args() << "):\n    "
                  << e.what() << std::endl;
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
