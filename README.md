# InputHog

Kernel-mode mouse injection prototype. A Windows kernel driver captures the mouse input callback from `MouClass`/`MouHID` and injects synthetic mouse events (moves, button presses) that appear as real hardware input. A Python GUI controller talks to the driver via IOCTL.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Required Installations](#required-installations)
- [Build](#build)
- [Driver Signing](#driver-signing)
- [Install & Run](#install--run)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Unload Driver](#unload-driver)

---

## Overview

**InputHog** lets you programmatically move the mouse and simulate button actions from user-mode without relying on `SendInput` or hooks. The driver injects events at the kernel level, so they are indistinguishable from physical mouse input to applications and games.

**Use cases:** Automation, testing, accessibility, or any scenario where low-level mouse control is needed.

**Limitations:**
- Requires **Administrator** privileges (driver load + controller)
- Requires **test signing** (or a proper code-signing certificate)
- **MouHID only:** Needs a USB mouse. PS/2 (i8042prt) can be added later.
- **x64 only** (32-bit kernel support dropped in WDK 10)

---

## Architecture

```
┌─────────────────────────────────────┐
│  InputHogControl.exe (Python/Tk)    │  User mode
│  - GUI: patterns, status, tests     │
│  - client.py: DeviceIoControl      │
└──────────────┬──────────────────────┘
               │ \\.\InputHog  (CreateFile + IOCTL)
               ▼
┌─────────────────────────────────────┐
│  InputHog.sys (kernel driver)        │  Kernel mode
│  - Creates \Device\InputHog          │
│  - Handles IOCTL_INPUT_HOG_*         │
│  - Injects via MouClass callback     │
└──────────────┬──────────────────────┘
               │ MOUSE_INPUT_DATA
               ▼
┌─────────────────────────────────────┐
│  MouClass / MouHID                   │  Windows mouse stack
│  (system mouse drivers)             │
└─────────────────────────────────────┘
```

**Data flow:**
1. User clicks a button in the GUI (e.g. "Square").
2. Controller sends an IOCTL with `MOUSE_MOVE_REQUEST` or `MOUSE_INPUT_REQUEST`.
3. Driver calls the captured `MouClass` callback with `MOUSE_INPUT_DATA`.
4. Windows delivers the input as if the physical mouse moved.

---

## Prerequisites

- **OS:** Windows 10 or 11 (x64)
- **Hardware:** USB mouse (required for MouHID)
- **BIOS / firmware:**
  - **Secure Boot** must be **disabled** (test signing is blocked otherwise)
  - **Memory Integrity (HVCI)** is often required off as well (Settings → Privacy & Security → Windows Security → Device security → Core isolation)

---

## Required Installations

### 1. Visual Studio

Install **Visual Studio 2022** or **Visual Studio 2026** (Insiders) with:

- **Desktop development with C++** workload
- **C++ ATL for latest build tools** (if prompted)
- **Windows 10 SDK** or **Windows 11 SDK** (matching your target)

For **VS 2026 Insiders**, ensure CMake 4.2+ for `Visual Studio 18 2026` generator support.

**Download:** [Visual Studio](https://visualstudio.microsoft.com/downloads/)

---

### 2. Windows Driver Kit (WDK)

Install the **standalone WDK** from Microsoft. The WDK available through the VS Installer alone may be missing kernel-mode headers.

1. Go to [Download the WDK](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk)
2. Download **Windows Driver Kit (WDK)** for your Windows version
3. Run the installer
4. Optionally install **WDK Visual Studio extension** if you want VS integration
5. Ensure kernel-mode components are installed: `C:\Program Files (x86)\Windows Kits\10\Include\<version>\km\ntddk.h` must exist

The WDK provides `MakeCert`, `SignTool`, and kernel headers used for driver build and test signing.

---

### 3. CMake (for driver build)

Needed if you build the driver with CMake.

- **Minimum:** 3.18 (for presets)
- **Recommended:** 3.28+ (for VS 2026 generator: `Visual Studio 18 2026`)

Download from [cmake.org](https://cmake.org/download/) or install via `winget install Kitware.CMake`.

---

### 4. Python 3

Required for the controller app and PyInstaller.

- **Minimum:** Python 3.9
- Install from [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12`
- Ensure `python` and `pip` are on `PATH`

---

### 5. Optional: Cursor / VS Code CMake extension

If you use Cursor or VS Code:

- **CMake Tools** (`ms-vscode.cmake-tools`) for configure/build from the editor
- `cmake.useCMakePresets` and `cmake.defaultConfigurePreset` are set in `.vscode/settings.json`

---

## Build

### Driver (kernel)

**Option A: CMake + presets (recommended)**

```powershell
# From repo root. Uses CMakePresets.json (Visual Studio 18 2026)
.\build-driver.ps1 -Config Debug
# or
.\build-driver.ps1 -Config Release
```

- Stops the InputHog service first (so the `.sys` can be overwritten)
- Configures with `cmake --preset x64-debug` or `x64-release`
- Output: `build\driver\Debug\InputHog.sys` or `build\driver\Release\InputHog.sys`

**Option B: CMake from IDE**

1. Open the folder in Cursor/VS Code with CMake extension
2. Select preset: **CMake: Select Configure Preset** → `x64-debug` or `x64-release`
3. **CMake: Configure**
4. **CMake: Build**

**Option C: Visual Studio solution**

1. Open `InputHog.sln`
2. Select **x64**, **Release** or **Debug**
3. Build Solution (F7)

Output: `driver\bin\x64\Release\InputHog.sys` (or Debug)

---

### Controller (GUI)

```powershell
cd controller
pip install -r requirements.txt
.\build.bat
```

Output: `controller\dist\InputHogControl.exe`

**Debug build** (console + tracebacks):

```powershell
cd controller
.\build-debug.bat
```

Output: `controller\dist\InputHogControl-Debug.exe`

---

## Driver Signing

Windows will not load an unsigned kernel driver even with test signing enabled on some systems. Use `sign-driver.ps1` to create a test certificate and sign the driver.

**Run as Administrator:**

```powershell
.\sign-driver.ps1
```

This script:

1. Creates `InputHogTest.cer` (if it doesn't exist)
2. Installs the cert in **Trusted Root** and **Trusted Publishers**
3. Signs the driver with SignTool (`/fd SHA256`)

It looks for the driver at:

- `build\driver\InputHog.sys`
- `build\driver\Debug\InputHog.sys`
- `build\driver\Release\InputHog.sys`
- `C:\InputHog\InputHog.sys`
- `driver\bin\x64\Release\InputHog.sys`
- `driver\bin\x64\Debug\InputHog.sys`

Or pass explicitly: `.\sign-driver.ps1 -DriverPath "C:\path\to\InputHog.sys"`

---

## Install & Run

### One-command setup (recommended)

**Run as Administrator** from the repo root:

```powershell
# First time: enable test signing (reboot if prompted)
.\setup-windows.ps1 -EnableTestSigning

# After reboot (if needed): install driver and launch app
.\setup-windows.ps1
```

What `setup-windows.ps1` does:

1. **Enable test signing** (if `-EnableTestSigning`): `bcdedit /set testsigning on` (reboot required if changed)
2. **Find driver:** Checks `build\driver\Debug`, `build\driver\Release`, etc.
3. **Copy to `C:\InputHog\InputHog.sys`** (avoids OneDrive/sync path issues that cause error 123)
4. **Create/update service:** Stops and removes old `InputHog` service, creates new one with correct path
5. **Start driver**
6. **Launch** `InputHogControl.exe` (unless `-SkipAppLaunch`)

**Parameters:**
- `-EnableTestSigning` — turn on test signing
- `-SkipAppLaunch` — install driver only, don't start the GUI
- `-TestSigningOnly` — enable test signing only, skip driver install
- `-DriverPath "path"` — use a specific driver file

---

### Manual steps

1. **Enable test signing (once):**
   ```cmd
   bcdedit /set testsigning on
   ```
   Reboot.

2. **Sign the driver (if needed):**
   ```powershell
   .\sign-driver.ps1
   ```

3. **Run setup:**
   ```powershell
   .\setup-windows.ps1
   ```

4. **Or run the app directly** (right-click → Run as administrator):
   ```
   controller\dist\InputHogControl.exe
   ```

---

### Paint test

1. Open **Paint**
2. Run `InputHogControl.exe` as Administrator
3. Click **Square**, **Circle**, or **Triangle**
4. The cursor should move without touching the mouse
5. Use **Refresh** for driver status (callback found, request counters, NTSTATUS)

---

## Project Structure

```
cpp-input-hog/
├── driver/                 # Kernel driver
│   ├── driver.c            # Device, IOCTL handling
│   ├── injection.c         # MouClass callback injection
│   ├── injection.h
│   └── CMakeLists.txt
├── shared/
│   └── ioctl.h             # IOCTL codes, request structs (driver + client)
├── controller/              # Python GUI
│   ├── app.py              # Tkinter UI
│   ├── client.py           # DeviceIoControl, IOCTL wrappers
│   ├── movements.py        # Patterns (square, circle, drag, etc.)
│   ├── requirements.txt
│   ├── InputHogControl.spec
│   └── InputHogControl-Debug.spec
├── cmake/
│   └── FindWdk.cmake       # WDK detection for CMake
├── CMakeLists.txt
├── CMakePresets.json        # x64-debug, x64-release
├── InputHog.sln            # Visual Studio solution
├── setup-windows.ps1        # Install driver + launch app
├── sign-driver.ps1          # Test-sign the driver
├── build-driver.ps1         # Build driver with CMake
└── README.md
```

---

## How It Works

### Driver

1. **Device setup:** Creates `\Device\InputHog` and symbolic link `\DosDevices\InputHog` (`\\.\InputHog` from user mode).
2. **Callback discovery:** Locates the `MouClass` mouse service callback by scanning device extensions of `MouHID` and `MouClass`.
3. **IOCTLs:**
   - `IOCTL_INPUT_HOG_MOVE_MOUSE` — relative move `(dx, dy)`
   - `IOCTL_INPUT_HOG_MOUSE_INPUT` — move + button flags (e.g. right down/up)
   - `IOCTL_INPUT_HOG_GET_STATUS` — injection status, counts, NTSTATUS
4. **Injection:** Fills `MOUSE_INPUT_DATA` and calls the captured callback so Windows processes the event as real mouse input.

### Controller

- Uses `CreateFile` on `\\.\InputHog` and `DeviceIoControl` to send IOCTLs
- `client.py` mirrors `shared/ioctl.h` (IOCTL codes, struct layouts)
- `movements.py` provides patterns (square, circle, triangle, line, random drag with right-button)

---

## Troubleshooting

### Error 577: "cannot verify digital signature"

Driver is not signed or certificate is not trusted.

1. Run `.\sign-driver.ps1` as Administrator
2. Run `.\setup-windows.ps1` again

### Error 123: "The filename, directory name, or volume label syntax is incorrect"

Driver path is invalid or inaccessible (often OneDrive/sync paths). `setup-windows.ps1` copies the driver to `C:\InputHog\InputHog.sys` to avoid this.

### Error 577 / Secure Boot

Secure Boot blocks test signing. Disable Secure Boot in BIOS/UEFI, then:

```cmd
bcdedit /set testsigning on
```

Reboot.

### Error 577 / Memory Integrity (HVCI)

Turn off Core Isolation: **Settings → Privacy & Security → Windows Security → Device security → Core isolation details** → disable **Memory integrity**.

### "Cannot open include file: ntddk.h"

WDK kernel-mode headers are missing. Install the **standalone WDK** from [Microsoft](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk) and ensure `km` headers exist under `C:\Program Files (x86)\Windows Kits\10\Include\*\km\`.

### CMake: "Visual Studio 18 2026 could not find any instance"

You need Visual Studio 2026 or CMake that supports it. Alternatives:

- Install VS 2026 Insiders, or
- Change `CMakePresets.json` to `"generator": "Visual Studio 17 2022"` and use VS 2022

### LNK1104: cannot open file 'driver\InputHog.sys'

The driver file is locked. Do the following:

1. Stop the driver: `sc stop InputHog`
2. Close the controller app if it is running
3. Rebuild with `.\build-driver.ps1`

### LNK1181: cannot open input file 'kernel32.lib'

The driver was linked with user-mode libraries. Ensure `CMAKE_C_STANDARD_LIBRARIES` is cleared in `driver/CMakeLists.txt` (already done in this project).

### Controller: "ERROR_ACCESS_DENIED" or cannot open driver

Run the controller **as Administrator**.

### Logs

Errors are written to `inputhog_debug.log` beside the executable. Use the debug build for console output: `controller\dist\InputHogControl-Debug.exe`.

---

## Unload Driver

```cmd
sc stop InputHog
sc delete InputHog
```

---

## Run from source (no PyInstaller)

```cmd
cd controller
python app.py
```

Run as Administrator.
