"""
InputHog controller — sends mouse move requests to the kernel driver via IOCTL.
"""

import ctypes
from ctypes import wintypes

# Constants (must match shared/ioctl.h)
INPUT_HOG_DEVICE_TYPE = 0x8000
FILE_ANY_ACCESS = 0
METHOD_BUFFERED = 0


def _ctl_code(device_type: int, function: int, method: int, access: int) -> int:
    return (device_type << 16) | (access << 14) | (function << 2) | method


IOCTL_INPUT_HOG_MOVE_MOUSE = _ctl_code(
    INPUT_HOG_DEVICE_TYPE, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS
)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80


class MOUSE_MOVE_REQUEST(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class InputHogClient:
    """Client for communicating with the InputHog kernel driver."""

    def __init__(self, device_path: str = r"\\.\InputHog"):
        self._device_path = device_path
        self._handle = None

    def open(self) -> bool:
        """Open a handle to the driver. Returns True on success."""
        self._handle = ctypes.windll.kernel32.CreateFileW(
            self._device_path,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        return self._handle != wintypes.HANDLE(-1).value

    def close(self) -> None:
        """Close the driver handle."""
        if self._handle is not None:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def move_mouse(self, x: int, y: int) -> bool:
        """
        Send a relative mouse movement request.
        Returns True if the IOCTL succeeded.
        """
        if self._handle is None:
            return False

        req = MOUSE_MOVE_REQUEST(x=x, y=y)
        buffer = ctypes.create_string_buffer(ctypes.sizeof(req))
        ctypes.memmove(buffer, ctypes.byref(req), ctypes.sizeof(req))

        bytes_returned = wintypes.DWORD()
        ok = ctypes.windll.kernel32.DeviceIoControl(
            self._handle,
            IOCTL_INPUT_HOG_MOVE_MOUSE,
            buffer,
            ctypes.sizeof(req),
            None,
            0,
            ctypes.byref(bytes_returned),
            None,
        )
        return bool(ok)

    def __enter__(self) -> "InputHogClient":
        if not self.open():
            raise RuntimeError("Failed to open InputHog driver. Is it loaded?")
        return self

    def __exit__(self, *args) -> None:
        self.close()


def main() -> None:
    """Demo: move mouse in a small square."""
    try:
        with InputHogClient() as client:
            for dx, dy in [(10, 0), (0, 10), (-10, 0), (0, -10)]:
                if client.move_mouse(dx, dy):
                    print(f"  Moved ({dx}, {dy})")
                else:
                    print(f"  Failed ({dx}, {dy})")
    except RuntimeError as e:
        print(f"Error: {e}")
        print("Ensure the driver is loaded and test signing is enabled.")


if __name__ == "__main__":
    main()
