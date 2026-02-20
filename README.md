# InputHog

Minimal kernel-mode input injection prototype. Mouse movement only.

## Prerequisites

- **Windows 10/11** (x64)
- **Visual Studio 2022** with **Desktop development with C++** workload
- **Windows Driver Kit (WDK)** — use the **standalone installer** from [Microsoft](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk) (the WDK in VS Installer alone may miss kernel headers)
- **Test signing** enabled: `bcdedit /set testsigning on` (reboot required)
- **Python 3** (for controller)

---

## Build Driver

### Option A: Visual Studio

1. Open `InputHog.sln` in Visual Studio
2. Select **x64** platform, **Release** or **Debug**
3. Build Solution (F7)

Output: `driver/bin/x64/Release/InputHog.sys` (or Debug)

### Option B: CMake (command line)

```powershell
# From repo root. Run in "Developer Command Prompt for VS" or after vcvars64.bat
mkdir build
cd build
cmake -G Ninja -A x64 ..
cmake --build . --config Release
```

Output: `build/driver/InputHog.sys`

After pulling driver/shared changes, rebuild and reinstall/restart the driver service so controller and driver IOCTL contracts stay in sync.

---

## Build Control App (GUI)

```cmd
cd controller
pip install -r requirements.txt
build.bat
```

Output: `controller/dist/InputHogControl.exe` (single executable)

### Download pre-built .exe (GitHub Actions)

Push to `main` or run the workflow manually: **Actions** → **Build Windows App** → **Run workflow**. Download `InputHogControl-Windows` from the run's artifacts.

---

## Install & Run

### One-command setup (recommended)

Run in **elevated PowerShell** from repo root:

```powershell
.\setup-windows.ps1 -EnableTestSigning
```

This will:
- enable test-signing (if needed),
- install/update and start the `InputHog` driver service,
- launch `InputHogControl.exe`.

If test-signing was just enabled, reboot once, then run the script again.

### 1. Enable test signing (once)

```cmd
bcdedit /set testsigning on
```
Reboot.

### 2. Install driver (once)

```cmd
sc create InputHog type= kernel binPath= "C:\full\path\to\driver\bin\x64\Release\InputHog.sys"
sc start InputHog
```

### 3. Run the app

Right-click `InputHogControl.exe` → **Run as administrator**.

**Paint test:** Open Paint, run the app, click **Test Square** or **Test Circle**. The cursor should move without touching the mouse.
Use **Refresh** to see driver status details (callback found, request counters, NTSTATUS values).

---

## Unload Driver

```cmd
sc stop InputHog
sc delete InputHog
```

---

## Debugging

**When errors occur and you can't see what's happening:**

1. **Debug build** (console window shows tracebacks):
   ```cmd
   cd controller
   build-debug.bat
   ```
   Run `dist/InputHogControl-Debug.exe` — a console window will appear with error output.

2. **Log file** — All errors are also written to `inputhog_debug.log` (next to the exe).

3. **Run from source** — Use `python app.py` to see output in the terminal.

---

## Run from source (no build)

```cmd
cd controller
python app.py
```
Run as Administrator.

---

## Troubleshooting

### Driver fails to start (error 577: "cannot verify digital signature")

Even with test signing enabled, some systems reject unsigned drivers. **Test-sign the driver**:

```powershell
.\sign-driver.ps1
.\setup-windows.ps1 -EnableTestSigning
```

The script creates a test certificate, installs it, and signs the driver.

### "Cannot open include file: ntddk.h"

The WDK kernel-mode headers are missing. Install the **full WDK**:

1. Download the WDK from: https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk  
2. Run the installer — it will add the `km` (kernel-mode) headers to `C:\Program Files (x86)\Windows Kits\10\Include\<version>\km\`
3. Restart Visual Studio and rebuild

**Note:** Visual Studio Community 2026 Insiders may not fully integrate with WDK. If issues persist, try **Visual Studio 2022** (non-Insiders).

### Spectre-mitigated libraries required

Install from VS Installer → Individual components → search "Spectre" → add **C++ Spectre-mitigated libraries for x64/x86**. Or we disable Spectre in the project (already done).

---

## Notes

- **MouHID only**: Requires a USB mouse (MouHID). PS/2 (i8042prt) can be added later.
- **Admin required**: Driver load and controller both need elevated privileges.
