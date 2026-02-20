"""
Movement patterns for InputHog testing.
"""

import math
import time
from typing import Callable, Optional

from client import InputHogClient


def _step(client: InputHogClient, dx: int, dy: int, delay_ms: float, on_move: Optional[Callable[..., None]]) -> bool:
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
    on_move: Optional[Callable[[int, int, bool], None]] = None,
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
    on_move: Optional[Callable[[int, int, bool], None]] = None,
) -> int:
    """Move in a circle. Returns number of successful moves."""
    success = 0
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        dx = int(radius * math.cos(angle))
        dy = int(radius * math.sin(angle))
        if _step(client, dx, dy, delay_ms, on_move):
            success += 1
    return success


def move(client: InputHogClient, x: int, y: int) -> bool:
    """Single move. Returns True on success."""
    return client.move_mouse(x, y)
