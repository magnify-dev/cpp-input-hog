"""
Play recordings using high-level user-mode input (no driver).
Uses pyautogui for mouse and keybd_event for keyboard.
Reuses recording format and load/save from recording.py.
"""

import sys
import time
from pathlib import Path
from typing import Callable, Optional

# High-level mouse/keyboard via pyautogui (no driver)
try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

import ctypes

from recording import load_recording
from client import (
    MOUSE_LEFT_BUTTON_DOWN,
    MOUSE_LEFT_BUTTON_UP,
    MOUSE_RIGHT_BUTTON_DOWN,
    MOUSE_RIGHT_BUTTON_UP,
    MOUSE_MIDDLE_BUTTON_DOWN,
    MOUSE_MIDDLE_BUTTON_UP,
)

KEYEVENTF_KEYUP = 0x0002

# Button flag -> pyautogui button name
_FLAG_TO_BUTTON = {
    MOUSE_LEFT_BUTTON_DOWN: "left",
    MOUSE_LEFT_BUTTON_UP: "left",
    MOUSE_RIGHT_BUTTON_DOWN: "right",
    MOUSE_RIGHT_BUTTON_UP: "right",
    MOUSE_MIDDLE_BUTTON_DOWN: "middle",
    MOUSE_MIDDLE_BUTTON_UP: "middle",
}


def _inject_key(vk: int, pressed: bool) -> None:
    """Inject keyboard event via keybd_event (user-mode, no driver)."""
    flags = 0 if pressed else KEYEVENTF_KEYUP
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


def play_recording_user32(
    events: list[dict],
    on_event: Optional[Callable[[dict, bool], None]] = None,
    fail_fast: bool = False,
) -> int:
    """
    Play a recording using user-mode APIs only (no InputHog driver).
    - Mouse: pyautogui.moveRel / mouseDown / mouseUp
    - Keyboard: keybd_event
    Returns number of successful events.
    """
    if not HAS_PYAUTOGUI:
        raise RuntimeError(
            "pyautogui is required. Install with: pip install pyautogui"
        )

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
            try:
                pyautogui.moveRel(dx, dy, _pause=False)
                ok = True
            except Exception:
                ok = False

        elif ev_type == "button":
            flag = ev.get("flag", 0)
            button = _FLAG_TO_BUTTON.get(flag)
            pressed = flag in (
                MOUSE_LEFT_BUTTON_DOWN,
                MOUSE_RIGHT_BUTTON_DOWN,
                MOUSE_MIDDLE_BUTTON_DOWN,
            )
            if button is not None:
                try:
                    if pressed:
                        pyautogui.mouseDown(button=button, _pause=False)
                    else:
                        pyautogui.mouseUp(button=button, _pause=False)
                    ok = True
                except Exception:
                    ok = False

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
        if fail_fast and not ok:
            break

    return success


def main() -> None:
    """CLI: load recording and play it with user32/pyautogui (no driver)."""
    if not HAS_PYAUTOGUI:
        print("Error: pyautogui is required. Install with: pip install pyautogui")
        sys.exit(1)

    recordings_dir = Path(__file__).resolve().parent / "recordings"
    if len(sys.argv) < 2:
        # List available recordings or use default
        if recordings_dir.exists():
            files = list(recordings_dir.glob("*.json"))
            if not files:
                print(f"No .json recordings in {recordings_dir}")
                sys.exit(1)
            path = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            print(f"Using most recent: {path.name}")
        else:
            print("Usage: python playback_user32.py <recording.json>")
            sys.exit(1)
    else:
        path = Path(sys.argv[1])
        if not path.is_absolute():
            candidate = recordings_dir / path.name
            path = candidate if candidate.exists() else path
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)

    events = load_recording(path)
    print(f"Loaded {len(events)} events. Playing in 2 seconds...")
    time.sleep(2)

    n = play_recording_user32(events)
    print(f"Played {n}/{len(events)} events (user-mode, no driver)")


if __name__ == "__main__":
    main()
