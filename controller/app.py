"""
InputHog Control — GUI for testing kernel-mode mouse injection.
"""

import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from client import InputHogClient, ERROR_CODES
from movements import test_square, test_circle, test_triangle, test_line, test_random_drag, move
from recording import MouseRecorder, save_recording, load_recording, play_recording

# Log file for debugging (next to exe, or current dir)
def _log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "inputhog_debug.log"
    return Path.cwd() / "inputhog_debug.log"


def _recordings_dir() -> Path:
    """Recordings folder: next to exe when frozen, else controller/recordings/."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    folder = base / "recordings"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def _log(msg: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def _excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _log(f"Uncaught exception:\n{tb}")
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _excepthook


def _fmt_ntstatus(status: int) -> str:
    return f"0x{status & 0xFFFFFFFF:08X}"


class InputHogApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("InputHog Control")
        self.root.resizable(False, False)
        self.root.minsize(380, 480)

        self.client = InputHogClient()
        self.connected = False
        self.error_count = 0
        self.last_move = (0, 0)
        self._last_error_msg = ""
        self._busy = False
        self._recorder = MouseRecorder()
        self._current_recording: list[dict] | None = None
        self._recording = False

        self._build_ui()
        self._check_connection()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        # Status
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=8)
        status_frame.pack(fill=tk.X, **pad)
        status_row = ttk.Frame(status_frame)
        status_row.pack(fill=tk.X)
        self.status_label = ttk.Label(status_row, text="Checking...")
        self.status_label.pack(side=tk.LEFT)
        self.btn_refresh = ttk.Button(status_row, text="Refresh", command=self._check_connection, width=8)
        self.btn_refresh.pack(side=tk.RIGHT)
        self.driver_label = ttk.Label(status_frame, text="", foreground="gray")
        self.driver_label.pack(anchor=tk.W)
        self.status_detail_label = ttk.Label(status_frame, text="", foreground="gray", wraplength=300, justify=tk.LEFT)
        self.status_detail_label.pack(anchor=tk.W)

        # Pattern options (delay, size)
        opts_frame = ttk.LabelFrame(self.root, text="Pattern Options", padding=8)
        opts_frame.pack(fill=tk.X, **pad)
        opts_row = ttk.Frame(opts_frame)
        opts_row.pack(fill=tk.X)
        ttk.Label(opts_row, text="Delay (ms):").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_delay = ttk.Entry(opts_row, width=8)
        self.entry_delay.pack(side=tk.LEFT, padx=(0, 12))
        self.entry_delay.insert(0, "1000")
        ttk.Label(opts_row, text="Size:").pack(side=tk.LEFT, padx=(12, 4))
        self.entry_size = ttk.Entry(opts_row, width=6)
        self.entry_size.pack(side=tk.LEFT, padx=(0, 12))
        self.entry_size.insert(0, "50")
        ttk.Label(opts_row, text="Radius:").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_radius = ttk.Entry(opts_row, width=6)
        self.entry_radius.pack(side=tk.LEFT, padx=(0, 6))
        self.entry_radius.insert(0, "30")

        # Test buttons
        test_frame = ttk.LabelFrame(self.root, text="Test Patterns", padding=8)
        test_frame.pack(fill=tk.X, **pad)
        btn_frame = ttk.Frame(test_frame)
        btn_frame.pack(fill=tk.X)
        self.btn_square = ttk.Button(btn_frame, text="Square", command=self._on_test_square)
        self.btn_square.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_circle = ttk.Button(btn_frame, text="Circle", command=self._on_test_circle)
        self.btn_circle.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_triangle = ttk.Button(btn_frame, text="Triangle", command=self._on_test_triangle)
        self.btn_triangle.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_line = ttk.Button(btn_frame, text="Line", command=self._on_test_line)
        self.btn_line.pack(side=tk.LEFT)

        # Second row: Random drag
        btn_frame2 = ttk.Frame(test_frame)
        btn_frame2.pack(fill=tk.X, pady=(6, 0))
        self.btn_random_drag = ttk.Button(btn_frame2, text="Random Drag (right-click)", command=self._on_random_drag)
        self.btn_random_drag.pack(side=tk.LEFT)

        # Custom move
        move_frame = ttk.LabelFrame(self.root, text="Custom Move", padding=8)
        move_frame.pack(fill=tk.X, **pad)
        row = ttk.Frame(move_frame)
        row.pack(fill=tk.X)
        ttk.Label(row, text="X:").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_x = ttk.Entry(row, width=8)
        self.entry_x.pack(side=tk.LEFT, padx=(0, 12))
        self.entry_x.insert(0, "50")
        ttk.Label(row, text="Y:").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_y = ttk.Entry(row, width=8)
        self.entry_y.pack(side=tk.LEFT, padx=(0, 12))
        self.entry_y.insert(0, "50")
        self.btn_move = ttk.Button(row, text="Move", command=self._on_custom_move)
        self.btn_move.pack(side=tk.LEFT)

        # Record & Playback
        rec_frame = ttk.LabelFrame(self.root, text="Record & Playback", padding=8)
        rec_frame.pack(fill=tk.X, **pad)
        rec_row1 = ttk.Frame(rec_frame)
        rec_row1.pack(fill=tk.X)
        self.btn_record = ttk.Button(rec_row1, text="Record", command=self._on_record)
        self.btn_record.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_stop = ttk.Button(rec_row1, text="Stop", command=self._on_stop_record, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 6))
        self.rec_status_label = ttk.Label(rec_row1, text="", foreground="gray")
        self.rec_status_label.pack(side=tk.LEFT)
        rec_row2 = ttk.Frame(rec_frame)
        rec_row2.pack(fill=tk.X, pady=(6, 0))
        self.btn_save = ttk.Button(rec_row2, text="Save recording", command=self._on_save_recording)
        self.btn_save.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_load = ttk.Button(rec_row2, text="Load recording", command=self._on_load_recording)
        self.btn_load.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_play = ttk.Button(rec_row2, text="Play", command=self._on_play_recording)
        self.btn_play.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_export_exe = ttk.Button(rec_row2, text="Export as .exe", command=self._on_export_exe)
        self.btn_export_exe.pack(side=tk.LEFT)

        # Feedback
        fb_frame = ttk.Frame(self.root)
        fb_frame.pack(fill=tk.X, **pad)
        self.fb_label = ttk.Label(fb_frame, text="Last: —  |  Errors: 0")
        self.fb_label.pack(anchor=tk.W)

        # Instructions (when disconnected)
        self.help_text = tk.Text(self.root, height=5, width=45, wrap=tk.WORD, state=tk.DISABLED, font=("Segoe UI", 9))
        self.help_text.pack(fill=tk.X, **pad)

    def _check_connection(self) -> None:
        if self._busy:
            return
        if self.client._handle is not None:
            self.client.close()
        self.connected = self.client.open()
        if not self.connected:
            err = self.client.get_last_error()
            _log(f"Connection failed: {ERROR_CODES.get(err, f'Win32 error {err}')}")
        self._update_status()
        self._update_help()

    def _refresh_driver_status(self) -> None:
        if not self.connected:
            self.driver_label.config(text="Driver not loaded")
            self.status_detail_label.config(text="")
            return

        status = self.client.get_status()
        if status is None:
            err = self.client.get_last_error()
            msg = ERROR_CODES.get(err, f"Win32 error {err}")
            self.driver_label.config(text="Driver: InputHog.sys")
            self.status_detail_label.config(text=f"Status query failed: {msg}")
            _log(f"Status query failed: {msg}")
            return

        self.driver_label.config(text=f"Driver: InputHog.sys (status v{status['version']})")
        injection = "ready" if status["injection_initialized"] else "not ready"
        callback = "found" if status["callback_found"] else "missing"
        details = (
            f"Injection: {injection} | Callback: {callback}\n"
            f"Requests: {status['total_requests']} total, {status['failed_requests']} failed\n"
            f"Init: {_fmt_ntstatus(status['last_init_status'])} | "
            f"Last inject: {_fmt_ntstatus(status['last_inject_status'])}"
        )
        self.status_detail_label.config(text=details)

    def _update_status(self) -> None:
        if self.connected:
            self.status_label.config(text="● Connected", foreground="green")
            self.btn_square.config(state=tk.NORMAL)
            self.btn_circle.config(state=tk.NORMAL)
            self.btn_triangle.config(state=tk.NORMAL)
            self.btn_line.config(state=tk.NORMAL)
            self.btn_random_drag.config(state=tk.NORMAL)
            self.btn_move.config(state=tk.NORMAL)
            self._refresh_driver_status()
        else:
            self.status_label.config(text="● Disconnected", foreground="red")
            self.driver_label.config(text="Driver not loaded")
            self.status_detail_label.config(text="")
            self.btn_square.config(state=tk.DISABLED)
            self.btn_circle.config(state=tk.DISABLED)
            self.btn_triangle.config(state=tk.DISABLED)
            self.btn_line.config(state=tk.DISABLED)
            self.btn_random_drag.config(state=tk.DISABLED)
            self.btn_move.config(state=tk.DISABLED)
        self._update_recording_buttons()

    def _update_recording_buttons(self) -> None:
        if self._recording:
            self.btn_record.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_save.config(state=tk.DISABLED)
            self.btn_load.config(state=tk.DISABLED)
            self.btn_play.config(state=tk.DISABLED)
            self.btn_export_exe.config(state=tk.DISABLED)
        else:
            self.btn_record.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_save.config(state=tk.NORMAL if self._current_recording else tk.DISABLED)
            self.btn_load.config(state=tk.NORMAL)
            self.btn_play.config(state=tk.NORMAL if (self._current_recording and self.connected) else tk.DISABLED)
            self.btn_export_exe.config(state=tk.NORMAL if self._current_recording else tk.DISABLED)

    def _update_help(self) -> None:
        self.help_text.config(state=tk.NORMAL)
        self.help_text.delete(1.0, tk.END)
        if not self.connected:
            self.help_text.insert(tk.END, "1. Enable test signing: bcdedit /set testsigning on (reboot)\n")
            self.help_text.insert(tk.END, "2. Install driver: sc create InputHog type= kernel binPath= \"path\\InputHog.sys\"\n")
            self.help_text.insert(tk.END, "3. Start driver: sc start InputHog\n")
            self.help_text.insert(tk.END, "4. Run this app as Administrator")
        self.help_text.config(state=tk.DISABLED)

    def _on_record(self) -> None:
        self._recording = True
        self._recorder.start()
        self.rec_status_label.config(text="Recording... move mouse, click, type")
        self._update_recording_buttons()

    def _on_stop_record(self) -> None:
        self._recording = False
        events = self._recorder.stop()
        self._current_recording = events
        n = len(events)
        self.rec_status_label.config(text=f"Recorded {n} events")
        self._update_recording_buttons()

    def _on_save_recording(self) -> None:
        if not self._current_recording:
            return
        path = filedialog.asksaveasfilename(
            initialdir=_recordings_dir(),
            defaultextension=".json",
            filetypes=[("InputHog Recording", "*.json"), ("All files", "*.*")],
            title="Save recording",
        )
        if path:
            try:
                save_recording(self._current_recording, Path(path))
                self.rec_status_label.config(text=f"Saved to {Path(path).name}")
            except Exception as e:
                messagebox.showerror("Save failed", str(e))

    def _on_load_recording(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=_recordings_dir(),
            filetypes=[("InputHog Recording", "*.json"), ("All files", "*.*")],
            title="Load recording",
        )
        if path:
            try:
                self._current_recording = load_recording(Path(path))
                n = len(self._current_recording)
                self.rec_status_label.config(text=f"Loaded {n} events")
                self._update_recording_buttons()
            except Exception as e:
                messagebox.showerror("Load failed", str(e))

    def _on_play_recording(self) -> None:
        if not self.connected or not self._current_recording:
            return
        def do():
            def on_ev(ev: dict, ok: bool) -> None:
                pass  # could update UI
            success = play_recording(self.client, self._current_recording, on_ev)
            self.root.after(0, lambda: self.rec_status_label.config(text=f"Played {success}/{len(self._current_recording)} events"))

        self._run_in_thread(do)

    def _on_export_exe(self) -> None:
        if not self._current_recording:
            messagebox.showinfo("No recording", "Record and stop first, then export.")
            return
        path = filedialog.asksaveasfilename(
            initialdir=_recordings_dir(),
            defaultextension=".py",
            filetypes=[("Python macro", "*.py"), ("All files", "*.*")],
            title="Export as executable",
        )
        if path:
            self._do_export_exe(Path(path))

    def _do_export_exe(self, exe_path: Path) -> None:
        """Create a standalone Python script that plays the current recording (single file, no deps)."""
        embed_json = __import__("json").dumps({"version": 2, "events": self._current_recording})
        out_script = exe_path.with_suffix(".py")
        if str(out_script) == str(exe_path):
            out_script = exe_path.parent / (exe_path.stem + "_macro.py")
        playback_script = f'''"""InputHog macro — run as Administrator. Requires InputHog driver. No extra deps."""
import ctypes
from ctypes import wintypes
import sys
import time

RECORDING = {embed_json}

# Minimal client (matches shared/ioctl.h)
IOCTL_MOVE = (0x8000 << 16) | (0x801 << 2)
IOCTL_INPUT = (0x8000 << 16) | (0x803 << 2)
GENERIC_RW = 0x80000000 | 0x40000000
FILE_SHARE_RW = 0x00000001 | 0x00000002

def play():
    _b = chr(92)  # backslash for \\\\.\\ path
    h = ctypes.windll.kernel32.CreateFileW(
        _b + _b + "." + _b + "InputHog", GENERIC_RW, FILE_SHARE_RW, None, 3, 0x80, None
    )
    if h == -1:
        print("Failed to connect. Run as Administrator. Is InputHog driver loaded?")
        return 0
    success = 0
    prev_t = 0
    for ev in RECORDING["events"]:
        t = ev.get("t", 0)
        if t - prev_t > 0:
            time.sleep((t - prev_t) / 1000.0)
        prev_t = t
        if ev.get("type") == "move":
            buf = ctypes.create_string_buffer(8)
            ctypes.memmove(buf, ctypes.byref(ctypes.c_long(ev.get("dx", 0))), 4)
            ctypes.memmove(buf[4:], ctypes.byref(ctypes.c_long(ev.get("dy", 0))), 4)
            if ctypes.windll.kernel32.DeviceIoControl(h, IOCTL_MOVE, buf, 8, None, 0, ctypes.byref(wintypes.DWORD()), None):
                success += 1
        elif ev.get("type") == "button":
            buf = ctypes.create_string_buffer(10)
            ctypes.memmove(buf, ctypes.byref(ctypes.c_ushort(ev.get("flag", 0))), 2)
            ctypes.memmove(buf[2:], ctypes.byref(ctypes.c_long(0)), 4)
            ctypes.memmove(buf[6:], ctypes.byref(ctypes.c_long(0)), 4)
            if ctypes.windll.kernel32.DeviceIoControl(h, IOCTL_INPUT, buf, 10, None, 0, ctypes.byref(wintypes.DWORD()), None):
                success += 1
        elif ev.get("type") == "key":
            vk = ev.get("vk")
            if vk is not None:
                try:
                    flags = 0 if ev.get("pressed", True) else 0x0002
                    ctypes.windll.user32.keybd_event(int(vk), 0, flags, 0)
                    success += 1
                except Exception:
                    pass
    ctypes.windll.kernel32.CloseHandle(h)
    return success

if __name__ == "__main__":
    n = play()
    print(f"Played {{n}}/{{len(RECORDING['events'])}} events")
'''
        try:
            with open(out_script, "w", encoding="utf-8") as f:
                f.write(playback_script)
            self.rec_status_label.config(text=f"Exported {out_script.name}")
            messagebox.showinfo(
                "Export complete",
                f"Created {out_script.name}\n\nRun as Administrator:\n  python {out_script.name}\n\nOr build a standalone .exe with PyInstaller.",
            )
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _update_feedback(self, dx: int, dy: int, ok: bool, error_code: int = 0) -> None:
        self.last_move = (dx, dy)
        if not ok:
            self.error_count += 1
            msg = ERROR_CODES.get(error_code, f"Win32 error {error_code}")
            if msg != self._last_error_msg:
                self._last_error_msg = msg
                _log(f"Move failed: ({dx},{dy}) -> {msg} (code {error_code})")
            self.fb_label.config(text=f"Last: ({dx}, {dy})  |  Errors: {self.error_count}\n{msg}")
        else:
            self._last_error_msg = ""
            self.fb_label.config(text=f"Last: ({dx}, {dy})  |  Errors: {self.error_count}")

    def _run_in_thread(self, fn, *args, **kwargs) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn_refresh.config(state=tk.DISABLED)
        self.btn_square.config(state=tk.DISABLED)
        self.btn_circle.config(state=tk.DISABLED)
        self.btn_triangle.config(state=tk.DISABLED)
        self.btn_line.config(state=tk.DISABLED)
        self.btn_random_drag.config(state=tk.DISABLED)
        self.btn_move.config(state=tk.DISABLED)
        self.btn_record.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.DISABLED)
        self.btn_load.config(state=tk.DISABLED)
        self.btn_play.config(state=tk.DISABLED)
        self.btn_export_exe.config(state=tk.DISABLED)

        def worker():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                tb = traceback.format_exc()
                _log(f"Thread error:\n{tb}")
                err_msg = f"{e}\n\nSee inputhog_debug.log for full traceback."
                self.root.after(0, lambda m=err_msg: messagebox.showerror("Error", m))
            finally:
                self.root.after(0, self._on_thread_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_thread_done(self) -> None:
        self._busy = False
        self.btn_refresh.config(state=tk.NORMAL)
        if self.connected:
            self.btn_square.config(state=tk.NORMAL)
            self.btn_circle.config(state=tk.NORMAL)
            self.btn_triangle.config(state=tk.NORMAL)
            self.btn_line.config(state=tk.NORMAL)
            self.btn_random_drag.config(state=tk.NORMAL)
            self.btn_move.config(state=tk.NORMAL)
            self._refresh_driver_status()
        self._update_recording_buttons()

    def _get_pattern_opts(self) -> tuple[int, int, int, float]:
        """Return (size, radius, steps, delay_ms). Raises ValueError on bad input."""
        delay = float(self.entry_delay.get())
        size = int(self.entry_size.get())
        radius = int(self.entry_radius.get())
        if delay < 0 or size < 1 or radius < 1:
            raise ValueError("Delay, size, and radius must be positive.")
        return size, radius, 24, delay

    def _on_test_square(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return
        try:
            size, _, _, delay = self._get_pattern_opts()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def do():
            def on_move(dx, dy, ok, err=0):
                self.root.after(0, lambda d=dx, e=dy, o=ok, r=err: self._update_feedback(d, e, o, r))
            test_square(self.client, size=size, delay_ms=delay, on_move=on_move)

        self._run_in_thread(do)

    def _on_test_circle(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return
        try:
            _, radius, steps, delay = self._get_pattern_opts()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def do():
            def on_move(dx, dy, ok, err=0):
                self.root.after(0, lambda d=dx, e=dy, o=ok, r=err: self._update_feedback(d, e, o, r))
            test_circle(self.client, radius=radius, steps=steps, delay_ms=delay, on_move=on_move)

        self._run_in_thread(do)

    def _on_test_triangle(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return
        try:
            size, _, _, delay = self._get_pattern_opts()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def do():
            def on_move(dx, dy, ok, err=0):
                self.root.after(0, lambda d=dx, e=dy, o=ok, r=err: self._update_feedback(d, e, o, r))
            test_triangle(self.client, size=size, delay_ms=delay, on_move=on_move)

        self._run_in_thread(do)

    def _on_test_line(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return
        try:
            size, _, steps, delay = self._get_pattern_opts()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def do():
            def on_move(dx, dy, ok, err=0):
                self.root.after(0, lambda d=dx, e=dy, o=ok, r=err: self._update_feedback(d, e, o, r))
            test_line(self.client, length=size * 2, steps=min(steps, 20), delay_ms=delay, horizontal=True, on_move=on_move)

        self._run_in_thread(do)

    def _on_random_drag(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return
        try:
            _, _, steps, delay = self._get_pattern_opts()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        def do():
            def on_move(dx, dy, ok, err=0):
                self.root.after(0, lambda d=dx, e=dy, o=ok, r=err: self._update_feedback(d, e, o, r))
            test_random_drag(self.client, delay_ms=delay, steps=min(steps, 30), on_move=on_move)

        self._run_in_thread(do)

    def _on_custom_move(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return
        try:
            x = int(self.entry_x.get())
            y = int(self.entry_y.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "X and Y must be integers.")
            return
        ok = move(self.client, x, y)
        err = self.client.get_last_error() if not ok else 0
        self._update_feedback(x, y, ok, err)
        if self.connected:
            self._refresh_driver_status()

    def run(self) -> None:
        self.root.mainloop()
        self.client.close()


def main() -> None:
    try:
        app = InputHogApp()
        app.run()
    except Exception:
        tb = traceback.format_exc()
        _log(f"Startup error:\n{tb}")
        raise


if __name__ == "__main__":
    main()
