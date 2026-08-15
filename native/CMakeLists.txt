cmake_minimum_required(VERSION 3.22)
project(aether-vision-lib)

# Force CMake to use the Ubuntu system OpenCV rather than a manual build in /usr/local
set(OpenCV_DIR "/usr/lib/x86_64-linux-gnu/cmake/opencv4")

find_package(OpenCV REQUIRED)

file(GLOB_RECURSE SOURCES
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.hpp"
)

add_library(aether-vision-lib SHARED ${SOURCES})

target_include_directories(aether-vision-lib PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src"
        ${OpenCV_INCLUDE_DIRS})
target_link_libraries(aether-vision-lib PRIVATE ${OpenCV_LIBS})