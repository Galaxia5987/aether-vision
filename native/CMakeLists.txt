cmake_minimum_required(VERSION 3.22)
project(aether-vision-lib)

# TODO: Right now this build file only support x86 linux, need to make it support ARM, at least.

# Force CMake to use the Ubuntu system OpenCV rather than a manual build in /usr/local
set(OpenCV_DIR "/usr/lib/x86_64-linux-gnu/cmake/opencv4")

find_package(OpenCV REQUIRED)

if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW) # some CMake shit
endif()

include(FetchContent)

set(ONNXRUNTIME_URL "https://github.com/microsoft/onnxruntime/releases/download/v1.29.0/onnxruntime-linux-x64-1.29.0.tgz") # Fetch onnx

FetchContent_Declare(
        onnxruntime
        URL ${ONNXRUNTIME_URL}
)
FetchContent_MakeAvailable(onnxruntime)

file(GLOB_RECURSE SOURCES
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.hpp"
)

add_library(aether-vision-lib SHARED ${SOURCES})

target_include_directories(aether-vision-lib PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src"
        ${OpenCV_INCLUDE_DIRS}
        ${onnxruntime_SOURCE_DIR}/include)

target_link_libraries(aether-vision-lib PRIVATE ${OpenCV_LIBS}
        ${onnxruntime_SOURCE_DIR}/lib/libonnxruntime.so)