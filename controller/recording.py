"""
Record and playback mouse and keyboard input for InputHog.
Records user mouse movements, clicks, and key presses with timestamps for playback.
"""

import ctypes
import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from pynput import keyboard, mouse
from pynput.mouse import Button

from client import (
    InputHogClient,
    MOUSE_LEFT_BUTTON_DOWN,
    MOUSE_LEFT_BUTTON_UP,
    MOUSE_RIGHT_BUTTON_DOWN,
    MOUSE_RIGHT_BUTTON_UP,
    MOUSE_MIDDLE_BUTTON_DOWN,
    MOUSE_MIDDLE_BUTTON_UP,
)

KEYEVENTF_KEYUP = 0x0002

# pynput Key enum -> Windows VK code (for keys that lack .vk)
# https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
_KEY_VK_LIST = [
    ("alt", 0x12), ("alt_l", 0xA4), ("alt_r", 0xA5), ("alt_gr", 0xA5),
    ("backspace", 0x08), ("caps_lock", 0x14), ("cmd", 0x5B), ("cmd_r", 0x5C),
    ("ctrl", 0x11), ("ctrl_l", 0xA2), ("ctrl_r", 0xA3),
    ("delete", 0x2E), ("down", 0x28), ("end", 0x23), ("enter", 0x0D),
    ("esc", 0x1B),
    ("f1", 0x70), ("f2", 0x71), ("f3", 0x72), ("f4", 0x73),
    ("f5", 0x74), ("f6", 0x75), ("f7", 0x76), ("f8", 0x77),
    ("f9", 0x78), ("f10", 0x79), ("f11", 0x7A), ("f12", 0x7B),
    ("f13", 0x7C), ("f14", 0x7D), ("f15", 0x7E), ("f16", 0x7F),
    ("f17", 0x80), ("f18", 0x81), ("f19", 0x82), ("f20", 0x83),
    ("f21", 0x84), ("f22", 0x85), ("f23", 0x86), ("f24", 0x87),
    ("home", 0x24), ("insert", 0x2D), ("left", 0x25), ("menu", 0x5D),
    ("num_lock", 0x90), ("page_down", 0x22), ("page_up", 0x21),
    ("pause", 0x13), ("print_screen", 0x2C), ("right", 0x27),
    ("scroll_lock", 0x91), ("shift", 0x10), ("shift_l", 0xA0), ("shift_r", 0xA1),
    ("space", 0x20), ("tab", 0x09), ("up", 0x26),
    ("media_play_pause", 0xB3), ("media_stop", 0xB2),
    ("media_volume_mute", 0xAD), ("media_volume_down", 0xAE), ("media_volume_up", 0xAF),
    ("media_previous", 0xB1), ("media_next", 0xB0),
]
KEY_TO_VK = {}
for k, v in _KEY_VK_LIST:
    if hasattr(keyboard.Key, k):
        KEY_TO_VK[getattr(keyboard.Key, k)] = v

# pynput Button -> driver button flags (from ntddmou.h)
BUTTON_FLAGS = {
    Button.left: (MOUSE_LEFT_BUTTON_DOWN, MOUSE_LEFT_BUTTON_UP),
    Button.right: (MOUSE_RIGHT_BUTTON_DOWN, MOUSE_RIGHT_BUTTON_UP),
    Button.middle: (MOUSE_MIDDLE_BUTTON_DOWN, MOUSE_MIDDLE_BUTTON_UP),
}

RECORDING_VERSION = 2  # Added keyboard


def _button_to_flag(button: Button, pressed: bool) -> int:
    if button not in BUTTON_FLAGS:
        return 0
    down, up = BUTTON_FLAGS[button]
    return down if pressed else up


def _key_to_vk(key) -> Optional[int]:
    """Extract virtual key code from pynput key. Returns None if unavailable."""
    if hasattr(key, "vk") and key.vk is not None:
        return int(key.vk)
    if key in KEY_TO_VK:
        return KEY_TO_VK[key]
    return None


class MouseRecorder:
    """Records mouse movements, clicks, and keyboard input with timestamps for playback."""

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._lock = threading.Lock()
        self._start_time: float = 0
        self._last_pos: tuple[int, int] | None = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None

    def start(self) -> None:
        """Start recording. Stops any existing recording."""
        self._events = []
        self._start_time = time.perf_counter()
        self._last_pos = None

        def on_move(x: int, y: int) -> None:
            if self._last_pos is not None:
                dx = x - self._last_pos[0]
                dy = y - self._last_pos[1]
                if dx != 0 or dy != 0:
                    t_ms = int((time.perf_counter() - self._start_time) * 1000)
                    with self._lock:
                        self._events.append({"t": t_ms, "type": "move", "dx": dx, "dy": dy})
            self._last_pos = (x, y)

        def on_click(x: int, y: int, button: Button, pressed: bool) -> None:
            self._last_pos = (x, y)
            flag = _button_to_flag(button, pressed)
            if flag != 0:
                t_ms = int((time.perf_counter() - self._start_time) * 1000)
                with self._lock:
                    self._events.append({"t": t_ms, "type": "button", "flag": flag})

        def on_key_press(key) -> None:
            vk = _key_to_vk(key)
            if vk is not None:
                t_ms = int((time.perf_counter() - self._start_time) * 1000)
                with self._lock:
                    self._events.append({"t": t_ms, "type": "key", "vk": vk, "pressed": True})

        def on_key_release(key) -> None:
            vk = _key_to_vk(key)
            if vk is not None:
                t_ms = int((time.perf_counter() - self._start_time) * 1000)
                with self._lock:
                    self._events.append({"t": t_ms, "type": "key", "vk": vk, "pressed": False})

        self._mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
        self._keyboard_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self) -> list[dict]:
        """Stop recording and return the list of events (sorted by time)."""
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        with self._lock:
            out = sorted(self._events, key=lambda e: e.get("t", 0))
        return out

    def get_event_count(self) -> int:
        return len(self._events)


def save_recording(events: list[dict], path: Path) -> None:
    """Save recording to a JSON file."""
    data = {"version": RECORDING_VERSION, "events": events}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_recording(path: Path) -> list[dict]:
    """Load recording from a JSON file. Returns list of events."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("events", [])


def _inject_key(vk: int, pressed: bool) -> None:
    """Inject a keyboard event via keybd_event (user-mode, no driver)."""
    flags = 0 if pressed else KEYEVENTF_KEYUP
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


def play_recording(
    client: InputHogClient,
    events: list[dict],
    on_event: Optional[Callable[[dict, bool], None]] = None,
) -> int:
    """
    Play a recording: mouse via driver, keyboard via keybd_event.
    Returns number of successful events.
    """
    if not events:
        return 0

    success = 0
    prev_t = 0

    for ev in events:
        t = ev.get("t", 0)
        delay_ms = t - prev_t
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        prev_t = t

        ev_type = ev.get("type", "")
        ok = False

        if ev_type == "move":
            dx = ev.get("dx", 0)
            dy = ev.get("dy", 0)
            ok = client.move_mouse(dx, dy)
        elif ev_type == "button":
            flag = ev.get("flag", 0)
            ok = client.mouse_input(flag, 0, 0)
        elif ev_type == "key":
            vk = ev.get("vk")
            if vk is not None:
                try:
                    _inject_key(int(vk), ev.get("pressed", True))
                    ok = True
                except Exception:
                    ok = False

        if ok:
            success += 1
        if on_event:
            on_event(ev, ok)

    return success
