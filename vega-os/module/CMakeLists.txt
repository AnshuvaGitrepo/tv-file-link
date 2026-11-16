cmake_minimum_required(VERSION 3.22)
project(FileLink LANGUAGES CXX C)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(turbomoduleAPI CONFIG REQUIRED)
find_package(Threads REQUIRED)
kepler_add_turbo_module_library(FileLink SHARED
    kepler/turbo-modules/generated/FileLinkSpec.cpp
    kepler/turbo-modules/FileLink.cpp
    kepler/AutoLinkInit.cpp
    shared/Transfer.cpp
)
target_include_directories(FileLink PRIVATE shared)
target_link_libraries(FileLink PRIVATE Threads::Threads)
install(TARGETS FileLink)
