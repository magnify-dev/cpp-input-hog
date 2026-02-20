"""
InputHog Control — GUI for testing kernel-mode mouse injection.
"""

import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

from client import InputHogClient, ERROR_CODES
from movements import test_square, test_circle, move

# Log file for debugging (next to exe, or current dir)
def _log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "inputhog_debug.log"
    return Path.cwd() / "inputhog_debug.log"

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


class InputHogApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("InputHog Control")
        self.root.resizable(False, False)
        self.root.minsize(320, 280)

        self.client = InputHogClient()
        self.connected = False
        self.error_count = 0
        self.last_move = (0, 0)
        self._last_error_msg = ""
        self._busy = False

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

        # Test buttons
        test_frame = ttk.LabelFrame(self.root, text="Test Patterns", padding=8)
        test_frame.pack(fill=tk.X, **pad)
        btn_frame = ttk.Frame(test_frame)
        btn_frame.pack(fill=tk.X)
        self.btn_square = ttk.Button(btn_frame, text="Test Square", command=self._on_test_square)
        self.btn_square.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_circle = ttk.Button(btn_frame, text="Test Circle", command=self._on_test_circle)
        self.btn_circle.pack(side=tk.LEFT)

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

    def _update_status(self) -> None:
        if self.connected:
            self.status_label.config(text="● Connected", foreground="green")
            self.driver_label.config(text="Driver: InputHog.sys")
            self.btn_square.config(state=tk.NORMAL)
            self.btn_circle.config(state=tk.NORMAL)
            self.btn_move.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="● Disconnected", foreground="red")
            self.driver_label.config(text="Driver not loaded")
            self.btn_square.config(state=tk.DISABLED)
            self.btn_circle.config(state=tk.DISABLED)
            self.btn_move.config(state=tk.DISABLED)

    def _update_help(self) -> None:
        self.help_text.config(state=tk.NORMAL)
        self.help_text.delete(1.0, tk.END)
        if not self.connected:
            self.help_text.insert(tk.END, "1. Enable test signing: bcdedit /set testsigning on (reboot)\n")
            self.help_text.insert(tk.END, "2. Install driver: sc create InputHog type= kernel binPath= \"path\\InputHog.sys\"\n")
            self.help_text.insert(tk.END, "3. Start driver: sc start InputHog\n")
            self.help_text.insert(tk.END, "4. Run this app as Administrator")
        self.help_text.config(state=tk.DISABLED)

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
        self.btn_move.config(state=tk.DISABLED)

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
            self.btn_move.config(state=tk.NORMAL)

    def _on_test_square(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return

        def do():
            def on_move(dx, dy, ok, err=0):
                self.root.after(0, lambda d=dx, e=dy, o=ok, r=err: self._update_feedback(d, e, o, r))
            test_square(self.client, size=50, delay_ms=30, on_move=on_move)

        self._run_in_thread(do)

    def _on_test_circle(self) -> None:
        if not self.connected:
            self._check_connection()
        if not self.connected:
            messagebox.showerror("Not Connected", "Driver not loaded. See instructions below.")
            return

        def do():
            def on_move(dx, dy, ok, err=0):
                self.root.after(0, lambda d=dx, e=dy, o=ok, r=err: self._update_feedback(d, e, o, r))
            test_circle(self.client, radius=30, steps=24, delay_ms=25, on_move=on_move)

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
