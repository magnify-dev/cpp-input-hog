#include "injection.h"
#include "../shared/ioctl.h"

extern POBJECT_TYPE* IoDriverObjectType;

#define DEVICE_EXT_SCAN_COUNT 128

#pragma pack(push, 1)
typedef struct _MOUSE_INPUT_DATA {
    USHORT UnitId;
    USHORT Flags;
    union {
        ULONG Buttons;
        struct {
            USHORT ButtonFlags;
            USHORT ButtonData;
        };
    };
    ULONG  RawButtons;
    LONG   LastX;
    LONG   LastY;
    ULONG  ExtraInformation;
} MOUSE_INPUT_DATA, *PMOUSE_INPUT_DATA;
#pragma pack(pop)

typedef VOID (NTAPI *MOUSE_SERVICE_CALLBACK)(
    PDEVICE_OBJECT DeviceObject,
    PMOUSE_INPUT_DATA InputDataStart,
    PMOUSE_INPUT_DATA InputDataEnd,
    PULONG InputDataConsumed
);

#define MOUSE_MOVE_RELATIVE 0

static PDEVICE_OBJECT g_ClassDeviceObject = NULL;
static MOUSE_SERVICE_CALLBACK g_ServiceCallback = NULL;

static NTSTATUS FindMouseCallback(VOID)
{
    UNICODE_STRING classDriverName;
    RtlInitUnicodeString(&classDriverName, L"\\Driver\\MouClass");

    PDRIVER_OBJECT classDriverObject = NULL;
    NTSTATUS status = ObReferenceObjectByName(
        &classDriverName,
        OBJ_CASE_INSENSITIVE,
        NULL,
        0,
        *IoDriverObjectType,
        KernelMode,
        NULL,
        &classDriverObject
    );
    if (!NT_SUCCESS(status))
        return status;

    UNICODE_STRING hidDriverName;
    RtlInitUnicodeString(&hidDriverName, L"\\Driver\\MouHID");

    PDRIVER_OBJECT hidDriverObject = NULL;
    status = ObReferenceObjectByName(
        &hidDriverName,
        OBJ_CASE_INSENSITIVE,
        NULL,
        0,
        *IoDriverObjectType,
        KernelMode,
        NULL,
        &hidDriverObject
    );
    if (!NT_SUCCESS(status)) {
        ObfDereferenceObject(classDriverObject);
        return status;
    }

    PDEVICE_OBJECT hidDevice = hidDriverObject->DeviceObject;
    while (hidDevice) {
        PDEVICE_OBJECT classDevice = classDriverObject->DeviceObject;
        while (classDevice) {
            PULONG_PTR ext = (PULONG_PTR)hidDevice->DeviceExtension;

            for (SIZE_T i = 0; i + 1 < DEVICE_EXT_SCAN_COUNT; i++) {
                if (ext[i] == (ULONG_PTR)classDevice &&
                    ext[i + 1] > (ULONG_PTR)classDriverObject->DriverStart) {
                    g_ClassDeviceObject = classDevice;
                    g_ServiceCallback = (MOUSE_SERVICE_CALLBACK)ext[i + 1];
                    ObfDereferenceObject(classDriverObject);
                    ObfDereferenceObject(hidDriverObject);
                    return STATUS_SUCCESS;
                }
            }
            classDevice = classDevice->NextDevice;
        }
        hidDevice = hidDevice->NextDevice;
    }

    if (!g_ClassDeviceObject) {
        PDEVICE_OBJECT dev = classDriverObject->DeviceObject;
        while (dev) {
            if (!dev->NextDevice) {
                g_ClassDeviceObject = dev;
                break;
            }
            dev = dev->NextDevice;
        }
    }

    ObfDereferenceObject(classDriverObject);
    ObfDereferenceObject(hidDriverObject);
    return (g_ClassDeviceObject && g_ServiceCallback) ? STATUS_SUCCESS : STATUS_NOT_FOUND;
}

NTSTATUS InjectionInitialize(VOID)
{
    return FindMouseCallback();
}

VOID InjectionCleanup(VOID)
{
    g_ClassDeviceObject = NULL;
    g_ServiceCallback = NULL;
}

NTSTATUS InjectMouseMove(LONG DeltaX, LONG DeltaY)
{
    if (!g_ServiceCallback || !g_ClassDeviceObject)
        return STATUS_DEVICE_NOT_READY;

    MOUSE_INPUT_DATA data = { 0 };
    data.UnitId = 0;
    data.Flags = MOUSE_MOVE_RELATIVE;
    data.ButtonFlags = 0;
    data.LastX = DeltaX;
    data.LastY = DeltaY;

    ULONG consumed = 0;
    g_ServiceCallback(
        g_ClassDeviceObject,
        &data,
        &data + 1,
        &consumed
    );

    return STATUS_SUCCESS;
}

BOOLEAN InjectionIsReady(VOID)
{
    return (g_ServiceCallback != NULL && g_ClassDeviceObject != NULL) ? TRUE : FALSE;
}
