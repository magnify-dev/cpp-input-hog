# FindWDK - CMake module for building Windows kernel drivers with WDK
# Based on https://github.com/SergiusTheBest/FindWDK

if(DEFINED ENV{WDKContentRoot})
  file(GLOB WDK_NTDDK_FILES
    "$ENV{WDKContentRoot}/Include/*/km/ntddk.h"
    "$ENV{WDKContentRoot}/Include/km/ntddk.h"
  )
else()
  file(GLOB WDK_NTDDK_FILES
    "C:/Program Files (x86)/Windows Kits/10/Include/*/km/ntddk.h"
    "C:/Program Files (x86)/Windows Kits/10/Include/km/ntddk.h"
  )
endif()

if(WDK_NTDDK_FILES)
  list(SORT WDK_NTDDK_FILES)
  list(GET WDK_NTDDK_FILES -1 WDK_LATEST_NTDDK_FILE)
endif()

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(WDK REQUIRED_VARS WDK_LATEST_NTDDK_FILE)

if(NOT WDK_FOUND)
  return()
endif()

get_filename_component(WDK_ROOT ${WDK_LATEST_NTDDK_FILE} DIRECTORY)
get_filename_component(WDK_ROOT ${WDK_ROOT} DIRECTORY)
get_filename_component(WDK_VERSION ${WDK_ROOT} NAME)
get_filename_component(WDK_ROOT ${WDK_ROOT} DIRECTORY)
if(NOT WDK_ROOT MATCHES ".*/[0-9][0-9.]*$")
  get_filename_component(WDK_ROOT ${WDK_ROOT} DIRECTORY)
  set(WDK_LIB_VERSION "${WDK_VERSION}")
  set(WDK_INC_VERSION "${WDK_VERSION}")
else()
  set(WDK_INC_VERSION "")
  foreach(VERSION winv6.3 win8 win7)
    if(EXISTS "${WDK_ROOT}/Lib/${VERSION}/")
      set(WDK_LIB_VERSION "${VERSION}")
      break()
    endif()
  endforeach()
  set(WDK_VERSION "${WDK_LIB_VERSION}")
endif()

message(STATUS "WDK_ROOT: ${WDK_ROOT}")
message(STATUS "WDK_VERSION: ${WDK_VERSION}")

set(WDK_WINVER "0x0A00" CACHE STRING "Default WINVER for WDK targets")
set(WDK_COMPILE_FLAGS
  "/Zp8" "/GF" "/GR-" "/Gz" "/kernel"
  "/FI${CMAKE_CURRENT_BINARY_DIR}/wdkflags.h"
  "/Oi"
)
set(WDK_ADDITIONAL_FLAGS_FILE "${CMAKE_CURRENT_BINARY_DIR}/wdkflags.h")
file(WRITE ${WDK_ADDITIONAL_FLAGS_FILE} "#pragma runtime_checks(\"suc\", off)\n")
list(APPEND WDK_COMPILE_FLAGS "/FI${WDK_ADDITIONAL_FLAGS_FILE}")

set(WDK_COMPILE_DEFINITIONS "WINNT=1;_WIN32_WINNT=${WDK_WINVER}")
set(WDK_COMPILE_DEFINITIONS_DEBUG "MSC_NOOPT;DEPRECATE_DDK_FUNCTIONS=1;DBG=1")

# WDK 10+ only provides x64 and arm64 kernel libs (x86 dropped)
if(CMAKE_SIZEOF_VOID_P EQUAL 4)
  message(FATAL_ERROR
    "InputHog driver requires x64. The selected kit is 32-bit (x86).\n"
    "Fix: Ctrl+Shift+P -> 'CMake: Select a Kit' -> choose one with 'amd64' or 'x64' (e.g. 'Visual Studio Community 2022 - amd64')")
elseif(CMAKE_SIZEOF_VOID_P EQUAL 8 AND CMAKE_SYSTEM_PROCESSOR MATCHES "ARM64")
  list(APPEND WDK_COMPILE_DEFINITIONS "_ARM64_;ARM64;_USE_DECLSPECS_FOR_SAL=1;STD_CALL")
  set(WDK_PLATFORM "arm64")
elseif(CMAKE_SIZEOF_VOID_P EQUAL 8)
  list(APPEND WDK_COMPILE_DEFINITIONS "_AMD64_;AMD64")
  set(WDK_PLATFORM "x64")
else()
  message(FATAL_ERROR "Unsupported architecture")
endif()

set(WDK_LINK_FLAGS
  "/MANIFEST:NO" "/DRIVER" "/OPT:REF" "/INCREMENTAL:NO" "/OPT:ICF"
  "/SUBSYSTEM:NATIVE" "/MERGE:_TEXT=.text" "/MERGE:_PAGE=PAGE" "/NODEFAULTLIB"
  "/SECTION:INIT,d" "/VERSION:10.0"
)

file(GLOB WDK_LIBRARIES "${WDK_ROOT}/Lib/${WDK_LIB_VERSION}/km/${WDK_PLATFORM}/*.lib")
foreach(LIBRARY IN LISTS WDK_LIBRARIES)
  get_filename_component(LIBRARY_NAME ${LIBRARY} NAME_WE)
  string(TOUPPER ${LIBRARY_NAME} LIBRARY_NAME)
  add_library(WDK::${LIBRARY_NAME} INTERFACE IMPORTED)
  set_property(TARGET WDK::${LIBRARY_NAME} PROPERTY INTERFACE_LINK_LIBRARIES ${LIBRARY})
endforeach()
unset(WDK_LIBRARIES)

function(wdk_add_driver _target)
  add_executable(${_target} ${ARGN})
  set_target_properties(${_target} PROPERTIES SUFFIX ".sys")
  target_compile_options(${_target} PRIVATE ${WDK_COMPILE_FLAGS})
  target_compile_definitions(${_target} PRIVATE ${WDK_COMPILE_DEFINITIONS}
    $<$<CONFIG:Debug>:${WDK_COMPILE_DEFINITIONS_DEBUG}>)
  target_link_options(${_target} PRIVATE ${WDK_LINK_FLAGS})
  target_include_directories(${_target} SYSTEM PRIVATE
    "${WDK_ROOT}/Include/${WDK_INC_VERSION}/shared"
    "${WDK_ROOT}/Include/${WDK_INC_VERSION}/km"
    "${WDK_ROOT}/Include/${WDK_INC_VERSION}/km/crt"
  )
  target_link_libraries(${_target} WDK::NTOSKRNL WDK::HAL WDK::WMILIB)
  if(TARGET WDK::BUFFEROVERFLOWK)
    target_link_libraries(${_target} WDK::BUFFEROVERFLOWK)
  else()
    target_link_libraries(${_target} WDK::BUFFEROVERFLOWFASTFAILK)
  endif()
  if(CMAKE_SIZEOF_VOID_P EQUAL 4)
    target_link_options(${_target} PRIVATE "/ENTRY:GsDriverEntry@8")
  else()
    target_link_options(${_target} PRIVATE "/ENTRY:GsDriverEntry")
  endif()
endfunction()
