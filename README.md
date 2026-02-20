# InputHog

Minimal kernel-mode input injection prototype. Mouse movement only.

## Prerequisites

- **Windows 10/11** (x64)
- **Visual Studio** with **Windows Driver Kit (WDK)** (for driver)
- **Test signing** enabled: `bcdedit /set testsigning on` (reboot required)
- **Python 3** (for controller)

---

## Build Driver

1. Open `InputHog.sln` in Visual Studio
2. Select **x64** platform, **Release** or **Debug**
3. Build Solution (F7)

Output: `driver/bin/x64/Release/InputHog.sys` (or Debug)

---

## Build Control App (GUI)

```cmd
cd controller
pip install -r requirements.txt
build.bat
```

Output: `controller/dist/InputHogControl.exe` (single executable)

---

## Install & Run

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

## Notes

- **MouHID only**: Requires a USB mouse (MouHID). PS/2 (i8042prt) can be added later.
- **Admin required**: Driver load and controller both need elevated privileges.
