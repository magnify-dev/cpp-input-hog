#include <ntddk.h>
#include <wdm.h>
#include "../shared/ioctl.h"
#include "injection.h"

#define DEVICE_NAME L"\\Device\\InputHog"
#define SYMLINK_NAME L"\\DosDevices\\InputHog"
#define INPUT_HOG_STATUS_VERSION 1

static PDEVICE_OBJECT g_DeviceObject = NULL;
static volatile LONG g_TotalRequests = 0;
static volatile LONG g_FailedRequests = 0;
static NTSTATUS g_LastInitStatus = STATUS_UNSUCCESSFUL;
static NTSTATUS g_LastInjectStatus = STATUS_SUCCESS;
static BOOLEAN g_InjectionInitialized = FALSE;

static VOID FillStatus(PINPUT_HOG_STATUS status)
{
    status->version = INPUT_HOG_STATUS_VERSION;
    status->injectionInitialized = g_InjectionInitialized ? 1u : 0u;
    status->callbackFound = InjectionIsReady() ? 1u : 0u;
    status->lastInitStatus = g_LastInitStatus;
    status->lastInjectStatus = g_LastInjectStatus;
    status->totalRequests = (ULONG)g_TotalRequests;
    status->failedRequests = (ULONG)g_FailedRequests;
}

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
    ULONG_PTR information = 0;

    if (stack->Parameters.DeviceIoControl.IoControlCode == IOCTL_INPUT_HOG_MOVE_MOUSE) {
        if (Irp->AssociatedIrp.SystemBuffer == NULL) {
            status = STATUS_INVALID_PARAMETER;
        } else if (stack->Parameters.DeviceIoControl.InputBufferLength >= sizeof(MOUSE_MOVE_REQUEST)) {
            PMOUSE_MOVE_REQUEST req = (PMOUSE_MOVE_REQUEST)Irp->AssociatedIrp.SystemBuffer;
            InterlockedIncrement(&g_TotalRequests);
            status = InjectMouseMove(req->x, req->y);
            g_LastInjectStatus = status;
            if (!NT_SUCCESS(status))
                InterlockedIncrement(&g_FailedRequests);
        } else {
            status = STATUS_BUFFER_TOO_SMALL;
        }
    } else if (stack->Parameters.DeviceIoControl.IoControlCode == IOCTL_INPUT_HOG_MOUSE_INPUT) {
        if (Irp->AssociatedIrp.SystemBuffer == NULL) {
            status = STATUS_INVALID_PARAMETER;
        } else if (stack->Parameters.DeviceIoControl.InputBufferLength >= sizeof(MOUSE_INPUT_REQUEST)) {
            PMOUSE_INPUT_REQUEST req = (PMOUSE_INPUT_REQUEST)Irp->AssociatedIrp.SystemBuffer;
            InterlockedIncrement(&g_TotalRequests);
            status = InjectMouseInput(req->buttonFlags, req->x, req->y);
            g_LastInjectStatus = status;
            if (!NT_SUCCESS(status))
                InterlockedIncrement(&g_FailedRequests);
        } else {
            status = STATUS_BUFFER_TOO_SMALL;
        }
    } else if (stack->Parameters.DeviceIoControl.IoControlCode == IOCTL_INPUT_HOG_GET_STATUS) {
        if (Irp->AssociatedIrp.SystemBuffer == NULL) {
            status = STATUS_INVALID_PARAMETER;
        } else if (stack->Parameters.DeviceIoControl.OutputBufferLength >= sizeof(INPUT_HOG_STATUS)) {
            PINPUT_HOG_STATUS outStatus = (PINPUT_HOG_STATUS)Irp->AssociatedIrp.SystemBuffer;
            FillStatus(outStatus);
            information = sizeof(INPUT_HOG_STATUS);
            status = STATUS_SUCCESS;
        } else {
            status = STATUS_BUFFER_TOO_SMALL;
        }
    } else {
        status = STATUS_INVALID_DEVICE_REQUEST;
    }

    Irp->IoStatus.Status = status;
    Irp->IoStatus.Information = information;
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

    g_InjectionInitialized = FALSE;
    InjectionCleanup();
}

NTSTATUS DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath)
{
    UNREFERENCED_PARAMETER(RegistryPath);

    NTSTATUS status = InjectionInitialize();
    g_LastInitStatus = status;
    if (!NT_SUCCESS(status))
        return status;
    g_InjectionInitialized = InjectionIsReady();

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
        g_InjectionInitialized = FALSE;
        InjectionCleanup();
        return status;
    }

    UNICODE_STRING symlinkName;
    RtlInitUnicodeString(&symlinkName, SYMLINK_NAME);
    status = IoCreateSymbolicLink(&symlinkName, &deviceName);
    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(g_DeviceObject);
        g_InjectionInitialized = FALSE;
        InjectionCleanup();
        return status;
    }

    DriverObject->DriverUnload = DriverUnload;
    DriverObject->MajorFunction[IRP_MJ_CREATE] = DeviceCreate;
    DriverObject->MajorFunction[IRP_MJ_CLOSE] = DeviceClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = DeviceControl;

    return STATUS_SUCCESS;
}
