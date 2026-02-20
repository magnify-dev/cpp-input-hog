"""
Movement patterns for InputHog testing.
"""

import math
import time
from typing import Callable, Optional

from client import InputHogClient

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


def move(client: InputHogClient, x: int, y: int) -> bool:
    """Single move. Returns True on success."""
    return client.move_mouse(x, y)
