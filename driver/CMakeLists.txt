cmake_minimum_required(VERSION 3.18)
project(InputHog LANGUAGES C)

# Kernel driver must NOT link user-mode libs (kernel32, user32, etc.)
set(CMAKE_C_STANDARD_LIBRARIES "")
set(CMAKE_CXX_STANDARD_LIBRARIES "")

set(CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake ${CMAKE_MODULE_PATH})
find_package(WDK REQUIRED)

wdk_add_driver(InputHog
  driver.c
  injection.c
)

target_include_directories(InputHog PRIVATE
  ${CMAKE_SOURCE_DIR}/shared
  ${CMAKE_CURRENT_SOURCE_DIR}
)
