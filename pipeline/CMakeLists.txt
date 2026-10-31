cmake_minimum_required(VERSION 3.22)
project(pipeline LANGUAGES CXX)

# Standard C++ configuration
set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Export compile commands for language servers and IDE tooling
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find Intel RealSense SDK (librealsense2)
# Supports both CMake package config and PkgConfig fallback for external toolchains
find_package(realsense2 QUIET)

if(NOT realsense2_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(realsense2 REQUIRED IMPORTED_TARGET realsense2)
endif()

# Recursive globbing for source and header files
# CONFIGURE_DEPENDS ensures CMake re-runs when files are added or removed
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.c"
)

file(GLOB_RECURSE HEADERS CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.hpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.h"
)

add_executable(${PROJECT_NAME} ${SOURCES} ${HEADERS})

# Link RealSense SDK
if(TARGET realsense2::realsense2)
    target_link_libraries(${PROJECT_NAME} PRIVATE realsense2::realsense2)
elseif(TARGET PkgConfig::realsense2)
    target_link_libraries(${PROJECT_NAME} PRIVATE PkgConfig::realsense2)
else()
    target_link_libraries(${PROJECT_NAME} PRIVATE ${realsense2_LIBRARY})
    target_include_directories(${PROJECT_NAME} PRIVATE ${realsense2_INCLUDE_DIRS} ${realsense2_INCLUDE_DIR})
endif()

# Include directories
target_include_directories(${PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
)

target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)
