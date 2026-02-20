#pragma once

#include <ntddk.h>
#include <wdm.h>

NTSTATUS InjectionInitialize(VOID);

VOID InjectionCleanup(VOID);

NTSTATUS InjectMouseMove(LONG DeltaX, LONG DeltaY);

NTSTATUS InjectMouseInput(USHORT ButtonFlags, LONG DeltaX, LONG DeltaY);

BOOLEAN InjectionIsReady(VOID);
