"""
User-mode input backend using pyautogui (no driver).
Implements the same move_mouse/mouse_input interface as InputHogClient.
"""

from typing import Optional

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

from client import (
    MOUSE_LEFT_BUTTON_DOWN,
    MOUSE_LEFT_BUTTON_UP,
    MOUSE_RIGHT_BUTTON_DOWN,
    MOUSE_RIGHT_BUTTON_UP,
    MOUSE_MIDDLE_BUTTON_DOWN,
    MOUSE_MIDDLE_BUTTON_UP,
)

_FLAG_TO_BUTTON = {
    MOUSE_LEFT_BUTTON_DOWN: "left",
    MOUSE_LEFT_BUTTON_UP: "left",
    MOUSE_RIGHT_BUTTON_DOWN: "right",
    MOUSE_RIGHT_BUTTON_UP: "right",
    MOUSE_MIDDLE_BUTTON_DOWN: "middle",
    MOUSE_MIDDLE_BUTTON_UP: "middle",
}


class User32Backend:
    """
    Input backend using pyautogui for mouse (user-mode, no driver).
    Same interface as InputHogClient: move_mouse(dx, dy), mouse_input(flags, x, y).
    """

    def __init__(self) -> None:
        self._last_error = 0

    @staticmethod
    def is_available() -> bool:
        return HAS_PYAUTOGUI

    def get_last_error(self) -> int:
        return self._last_error

    def move_mouse(self, x: int, y: int) -> bool:
        if not HAS_PYAUTOGUI:
            self._last_error = 1
            return False
        try:
            pyautogui.moveRel(x, y, _pause=False)
            self._last_error = 0
            return True
        except Exception:
            self._last_error = 1
            return False

    def mouse_input(self, button_flags: int, x: int, y: int) -> bool:
        if not HAS_PYAUTOGUI:
            self._last_error = 1
            return False
        try:
            if x != 0 or y != 0:
                pyautogui.moveRel(x, y, _pause=False)
            if button_flags != 0:
                button = _FLAG_TO_BUTTON.get(button_flags)
                pressed = button_flags in (
                    MOUSE_LEFT_BUTTON_DOWN,
                    MOUSE_RIGHT_BUTTON_DOWN,
                    MOUSE_MIDDLE_BUTTON_DOWN,
                )
                if button is not None:
                    if pressed:
                        pyautogui.mouseDown(button=button, _pause=False)
                    else:
                        pyautogui.mouseUp(button=button, _pause=False)
            self._last_error = 0
            return True
        except Exception:
            self._last_error = 1
            return False
