# Minimal Prototype Plan: Kernel-Mode Input Injection

## Design Principles

- **Minimal** — Only mouse movement for v1. No clicks, keyboard, or evasion logic.
- **Modular** — Clear boundaries between layers. Each module has one job.
- **Clean** — Shared contract (header), no magic numbers, easy to extend.

---

## Project Layout

```
cpp-input-hog/
├── shared/
│   └── ioctl.h              # IOCTL codes + request structs (single source of truth)
├── driver/
│   ├── driver.c             # Entry, device, dispatch, cleanup
│   ├── injection.c          # Callback lookup + MOUSE_INPUT_DATA injection
│   ├── injection.h
│   └── (WDK project files)
└── controller/
    └── client.py            # Python ctypes client
```

---

## Module Responsibilities

### 1. `shared/ioctl.h`

- Defines `CTL_MOVE_MOUSE` and `MOUSE_MOVE_REQUEST`
- Used by both driver (C) and controller (Python via ctypes)
- No logic, only data structures and constants

### 2. `driver/` (Kernel)

| File        | Responsibility                                      |
|-------------|-----------------------------------------------------|
| `driver.c`  | `DriverEntry`, create `\Device\...` + `\DosDevices\...`, IRP dispatch, `DriverUnload` |
| `injection.c`| `AuxKlibQueryModuleInformation` → find `mouclass.sys` base, pattern scan for callback, store pointer |
| `injection.h`| Declares `inject_mouse_move(long x, long y)` and init/cleanup hooks |

### 3. `controller/client.py`

- Open `\\.\InputHog` via `CreateFileW`
- `move_mouse(x, y)` → pack `MOUSE_MOVE_REQUEST`, call `DeviceIoControl`
- No screen capture, pathfinding, or AI — just the IOCTL bridge for testing

---

## Data Flow

```
client.py                    driver
   |                            |
   |  CreateFileW("\\.\InputHog")
   |--------------------------->|  Create device + symlink
   |                            |
   |  DeviceIoControl(MOVE, {x,y})
   |--------------------------->|  IRP_MJ_DEVICE_CONTROL
   |                            |  -> inject_mouse_move(x, y)
   |                            |     -> MouseClassServiceCallback(&data)
   |<---------------------------|  Success
```

---

## Minimal Scope (v1)

| Include                         | Exclude (for later)                    |
|---------------------------------|----------------------------------------|
| Relative mouse move only        | Absolute positioning                   |
| Single IOCTL code               | Button clicks, keyboard                |
| Pattern scan for callback       | Bezier/jitter, anti-detection          |
| Basic error handling            | Logging, debug output                  |

---

## Build & Run Dependencies

- Windows 10/11
- WDK + Visual Studio (driver)
- Python 3 + ctypes (controller)
- Test signing: `bcdedit /set testsigning on` + reboot

---

## Extension Points (Post-Prototype)

- Add `CTL_MOUSE_CLICK` + `MOUSE_CLICK_REQUEST` in `ioctl.h`
- Add `inject_mouse_click(button_flags)` in `injection.c`
- Add `click(button)` in `client.py`
- Same pattern for keyboard if needed
