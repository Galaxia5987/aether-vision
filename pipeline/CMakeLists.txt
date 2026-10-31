cmake_minimum_required(VERSION 3.22)
project(pipeline LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)
find_package(Threads REQUIRED)
find_package(Protobuf REQUIRED)

# Protobuf generation
set(PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/proto")
set(PROTO_FILES "${PROTO_DIR}/vision_pipeline.proto")
protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILES})

# Find Intel RealSense SDK
find_package(realsense2 QUIET)
if(NOT realsense2_FOUND)
    pkg_check_modules(realsense2 REQUIRED IMPORTED_TARGET realsense2)
endif()

# Find OpenCV
find_package(OpenCV REQUIRED)

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.c"
)
file(GLOB_RECURSE HEADERS CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.hpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/*.h"
)

add_executable(${PROJECT_NAME} ${SOURCES} ${HEADERS} ${PROTO_SRCS} ${PROTO_HDRS})

target_include_directories(${PROJECT_NAME} PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src"
        "${CMAKE_CURRENT_BINARY_DIR}"
        ${Protobuf_INCLUDE_DIRS}
        ${OpenCV_INCLUDE_DIRS}
)

# 1. Tell the linker to search /usr/local/lib where your custom OpenCV/FFmpeg likely reside
target_link_directories(${PROJECT_NAME} PRIVATE /usr/local/lib)

# 2. Link OpenCV and RealSense FIRST
if(TARGET realsense2::realsense2)
    target_link_libraries(${PROJECT_NAME} PRIVATE ${OpenCV_LIBS} realsense2::realsense2)
elseif(TARGET PkgConfig::realsense2)
    target_link_libraries(${PROJECT_NAME} PRIVATE ${OpenCV_LIBS} PkgConfig::realsense2)
else()
    target_link_libraries(${PROJECT_NAME} PRIVATE ${OpenCV_LIBS} ${realsense2_LIBRARY})
    target_include_directories(${PROJECT_NAME} PRIVATE ${realsense2_INCLUDE_DIRS})
endif()

# 3. Force FFmpeg to link LAST by providing raw library names at the end of the file.
# This guarantees they appear after OpenCV on the final compiler command line.
target_link_libraries(${PROJECT_NAME} PRIVATE
        Threads::Threads
        ${Protobuf_LIBRARIES}
        avcodec
        avformat
        avutil
        swscale
)

target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)