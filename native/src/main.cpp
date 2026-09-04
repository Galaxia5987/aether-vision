//
// Created by adarw on 8/23/26.
//
#include <iostream>

#include "inference/YoloDetector.hpp"

int main() {
    std::cout << "Starting native test..." << std::endl;
    try {
        // Use a dummy path for the model just to test initialization
        aethervision::YoloDetector detector("/home/adarw/Projects/aether-vision/app/model.onnx", false);
        std::cout << "Environment initialized successfully!" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Caught exception: " << e.what() << std::endl;
    }
    return 0;
}
