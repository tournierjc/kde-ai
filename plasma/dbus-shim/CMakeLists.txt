cmake_minimum_required(VERSION 3.16)
project(kde-ai-dbus-shim VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core DBus Network)
find_package(ECM QUIET NO_MODULE)

add_executable(kde-ai-dbus-shim main.cpp adaptor.h)
target_link_libraries(kde-ai-dbus-shim Qt6::Core Qt6::DBus Qt6::Network)

install(TARGETS kde-ai-dbus-shim DESTINATION bin)
