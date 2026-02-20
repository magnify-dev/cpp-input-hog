#include <ntddk.h>
#include <wdm.h>
#include "../shared/ioctl.h"
#include "injection.h"

#define DEVICE_NAME L"\\Device\\InputHog"
#define SYMLINK_NAME L"\\DosDevices\\InputHog"

static PDEVICE_OBJECT g_DeviceObject = NULL;

static NTSTATUS DeviceCreate(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);
    Irp->IoStatus.Status = STATUS_SUCCESS;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

static NTSTATUS DeviceClose(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);
    Irp->IoStatus.Status = STATUS_SUCCESS;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

static NTSTATUS DeviceControl(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);

    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
    NTSTATUS status = STATUS_SUCCESS;

    if (stack->Parameters.DeviceIoControl.IoControlCode == IOCTL_INPUT_HOG_MOVE_MOUSE) {
        if (stack->Parameters.DeviceIoControl.InputBufferLength >= sizeof(MOUSE_MOVE_REQUEST)) {
            PMOUSE_MOVE_REQUEST req = (PMOUSE_MOVE_REQUEST)Irp->AssociatedIrp.SystemBuffer;
            status = InjectMouseMove(req->x, req->y);
        } else {
            status = STATUS_BUFFER_TOO_SMALL;
        }
    } else {
        status = STATUS_INVALID_DEVICE_REQUEST;
    }

    Irp->IoStatus.Status = status;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return status;
}

static VOID DriverUnload(PDRIVER_OBJECT DriverObject)
{
    UNICODE_STRING symlink;
    RtlInitUnicodeString(&symlink, SYMLINK_NAME);
    IoDeleteSymbolicLink(&symlink);

    if (g_DeviceObject)
        IoDeleteDevice(g_DeviceObject);

    InjectionCleanup();
}

NTSTATUS DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath)
{
    UNREFERENCED_PARAMETER(RegistryPath);

    NTSTATUS status = InjectionInitialize();
    if (!NT_SUCCESS(status))
        return status;

    UNICODE_STRING deviceName;
    RtlInitUnicodeString(&deviceName, DEVICE_NAME);

    status = IoCreateDevice(
        DriverObject,
        0,
        &deviceName,
        FILE_DEVICE_UNKNOWN,
        0,
        FALSE,
        &g_DeviceObject
    );
    if (!NT_SUCCESS(status)) {
        InjectionCleanup();
        return status;
    }

    UNICODE_STRING symlinkName;
    RtlInitUnicodeString(&symlinkName, SYMLINK_NAME);
    status = IoCreateSymbolicLink(&symlinkName, &deviceName);
    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(g_DeviceObject);
        InjectionCleanup();
        return status;
    }

    DriverObject->DriverUnload = DriverUnload;
    DriverObject->MajorFunction[IRP_MJ_CREATE] = DeviceCreate;
    DriverObject->MajorFunction[IRP_MJ_CLOSE] = DeviceClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = DeviceControl;

    return STATUS_SUCCESS;
}
