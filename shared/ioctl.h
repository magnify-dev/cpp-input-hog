#pragma once

#include <ntddk.h>

#define INPUT_HOG_DEVICE_TYPE 0x8000

#define IOCTL_INPUT_HOG_MOVE_MOUSE \
    CTL_CODE(INPUT_HOG_DEVICE_TYPE, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_INPUT_HOG_MOUSE_INPUT \
    CTL_CODE(INPUT_HOG_DEVICE_TYPE, 0x803, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_INPUT_HOG_GET_STATUS \
    CTL_CODE(INPUT_HOG_DEVICE_TYPE, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)

#pragma pack(push, 1)

typedef struct _MOUSE_MOVE_REQUEST {
    LONG x;
    LONG y;
} MOUSE_MOVE_REQUEST, *PMOUSE_MOVE_REQUEST;

typedef struct _MOUSE_INPUT_REQUEST {
    USHORT buttonFlags;
    LONG x;
    LONG y;
} MOUSE_INPUT_REQUEST, *PMOUSE_INPUT_REQUEST;

typedef struct _INPUT_HOG_STATUS {
    ULONG version;
    ULONG injectionInitialized;
    ULONG callbackFound;
    LONG lastInitStatus;
    LONG lastInjectStatus;
    ULONG totalRequests;
    ULONG failedRequests;
} INPUT_HOG_STATUS, *PINPUT_HOG_STATUS;

#pragma pack(pop)
