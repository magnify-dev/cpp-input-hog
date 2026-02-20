#pragma once

#include <ntddk.h>

NTSTATUS InjectionInitialize(VOID);

VOID InjectionCleanup(VOID);

NTSTATUS InjectMouseMove(LONG DeltaX, LONG DeltaY);

BOOLEAN InjectionIsReady(VOID);
