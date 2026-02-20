"""
Movement patterns for InputHog testing.
"""

import math
import random
import time
from typing import Callable, Optional

import ctypes
from ctypes import wintypes

from client import InputHogClient, MOUSE_RIGHT_BUTTON_DOWN, MOUSE_RIGHT_BUTTON_UP

MoveCallback = Callable[[int, int, bool, int], None]

def _step(client: InputHogClient, dx: int, dy: int, delay_ms: float, on_move: Optional[MoveCallback]) -> bool:
    ok = client.move_mouse(dx, dy)
    if on_move:
        err = client.get_last_error() if not ok else 0
        on_move(dx, dy, ok, err)
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    return ok


def test_square(
    client: InputHogClient,
    size: int = 50,
    delay_ms: float = 30,
    on_move: Optional[MoveCallback] = None,
) -> int:
    """Move in a square. Returns number of successful moves."""
    steps = [(size, 0), (0, size), (-size, 0), (0, -size)]
    success = 0
    for dx, dy in steps:
        if _step(client, dx, dy, delay_ms, on_move):
            success += 1
    return success


def test_circle(
    client: InputHogClient,
    radius: int = 30,
    steps: int = 24,
    delay_ms: float = 25,
    on_move: Optional[MoveCallback] = None,
) -> int:
    """Move in a closed circle and return to start. Returns successful moves."""
    if steps < 4:
        steps = 4

    success = 0

    # Move from center to the circle perimeter first.
    if _step(client, radius, 0, delay_ms, on_move):
        success += 1

    prev_x = radius
    prev_y = 0
    for i in range(1, steps + 1):
        angle = 2 * math.pi * i / steps
        x = int(round(radius * math.cos(angle)))
        y = int(round(radius * math.sin(angle)))
        dx = x - prev_x
        dy = y - prev_y
        if _step(client, dx, dy, delay_ms, on_move):
            success += 1
        prev_x, prev_y = x, y

    # Return to original cursor location.
    if _step(client, -radius, 0, delay_ms, on_move):
        success += 1

    return success


def test_triangle(
    client: InputHogClient,
    size: int = 50,
    delay_ms: float = 1000,
    on_move: Optional[MoveCallback] = None,
) -> int:
    """Move in a triangle. Returns number of successful moves."""
    # Equilateral: right, upper-left, lower-left, back to start
    h = int(size * math.sqrt(3) / 2)
    steps = [(size, 0), (-size // 2, -h), (-size // 2, h)]
    success = 0
    for dx, dy in steps:
        if _step(client, dx, dy, delay_ms, on_move):
            success += 1
    return success


def test_line(
    client: InputHogClient,
    length: int = 100,
    steps: int = 10,
    delay_ms: float = 1000,
    horizontal: bool = True,
    on_move: Optional[MoveCallback] = None,
) -> int:
    """Move in a straight line. Returns number of successful moves."""
    step_size = length // steps if steps > 0 else length
    success = 0
    for _ in range(steps):
        dx = step_size if horizontal else 0
        dy = 0 if horizontal else step_size
        if _step(client, dx, dy, delay_ms, on_move):
            success += 1
    return success


def move(client: InputHogClient, x: int, y: int) -> bool:
    """Single move. Returns True on success."""
    return client.move_mouse(x, y)


def _get_cursor_pos() -> tuple[int, int]:
    """Get current cursor position (screen coords)."""
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)


def _get_screen_size() -> tuple[int, int]:
    """Get primary screen width and height."""
    w = ctypes.windll.user32.GetSystemMetrics(0)   # SM_CXSCREEN
    h = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return (w, h)


def test_random_drag(
    client: InputHogClient,
    delay_ms: float = 1000,
    steps: int = 20,
    margin: int = 50,
    on_move: Optional[MoveCallback] = None,
) -> int:
    """
    Pick 2 random screen points, move to first, right-drag to second.
    Returns number of successful moves.
    """
    w, h = _get_screen_size()
    cx, cy = _get_cursor_pos()

    # Random points within margin of edges
    x1 = random.randint(margin, max(margin, w - margin - 1))
    y1 = random.randint(margin, max(margin, h - margin - 1))
    x2 = random.randint(margin, max(margin, w - margin - 1))
    y2 = random.randint(margin, max(margin, h - margin - 1))

    success = 0

    # Move to point 1 (relative delta)
    dx1 = x1 - cx
    dy1 = y1 - cy
    if client.move_mouse(dx1, dy1):
        success += 1
        if on_move:
            on_move(dx1, dy1, True, 0)
    elif on_move:
        on_move(dx1, dy1, False, client.get_last_error())
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    # Right button down (no movement)
    if client.mouse_input(MOUSE_RIGHT_BUTTON_DOWN, 0, 0):
        success += 1
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    # Drag to point 2 in steps (relative deltas)
    step_dx = (x2 - x1) // steps
    step_dy = (y2 - y1) // steps
    for _ in range(steps):
        if client.mouse_input(0, step_dx, step_dy):  # 0 = move only, button held
            success += 1
            if on_move:
                on_move(step_dx, step_dy, True, 0)
        elif on_move:
            on_move(step_dx, step_dy, False, client.get_last_error())
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    # Right button up
    if client.mouse_input(MOUSE_RIGHT_BUTTON_UP, 0, 0):
        success += 1
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    return success
