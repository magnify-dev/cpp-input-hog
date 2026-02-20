#pragma once

#include <ntddk.h>

#define INPUT_HOG_DEVICE_TYPE 0x8000

#define IOCTL_INPUT_HOG_MOVE_MOUSE \
    CTL_CODE(INPUT_HOG_DEVICE_TYPE, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

#pragma pack(push, 1)

typedef struct _MOUSE_MOVE_REQUEST {
    LONG x;
    LONG y;
} MOUSE_MOVE_REQUEST, *PMOUSE_MOVE_REQUEST;

#pragma pack(pop)
