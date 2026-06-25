"""Serial (USB CDC) transport for the arm bridge. USED NOW.

This mirrors how stm32_bridge talks to the car's STM32 over USB CDC, so the
arm uses the same proven approach while we are still on the test bench. The
Arduino Uno + CNC Shield enumerates as /dev/ttyUSB0 (CH340) or /dev/ttyACM0.

NOTE: keep the car and the arm on DIFFERENT ports. The car STM32 is usually
/dev/ttyACM0; point the arm at its own port (e.g. /dev/ttyUSB0) so the two
bridges never fight over the same device.
"""

from typing import Optional

from .transport_base import ArmTransport

try:
    import serial
    from serial import SerialException
except ImportError:  # pragma: no cover - depends on host ROS environment
    serial = None

    class SerialException(Exception):
        pass


class SerialTransport(ArmTransport):
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.0):
        self._port = port
        self._baudrate = int(baudrate)
        self._timeout = float(timeout)
        self._ser = None
        self._rx = bytearray()

    def open(self) -> None:
        if serial is None:
            raise RuntimeError(
                'pyserial is not installed; cannot open SerialTransport. '
                'Add python3-serial to the environment.')
        self._ser = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=self._timeout,
            write_timeout=0.2,
        )
        self._rx.clear()

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def is_open(self) -> bool:
        return self._ser is not None and getattr(self._ser, 'is_open', False)

    def send_line(self, line: str) -> None:
        if not self.is_open():
            raise SerialException('serial port not open')
        self._ser.write((line + '\r\n').encode('ascii', errors='ignore'))

    def read_line(self) -> Optional[str]:
        if not self.is_open():
            return None
        # Pull whatever bytes are waiting, then return one full line if we
        # have one. This keeps the node timer loop non-blocking.
        waiting = self._ser.in_waiting
        if waiting:
            self._rx.extend(self._ser.read(waiting))
        nl = self._rx.find(b'\n')
        if nl < 0:
            return None
        raw = self._rx[:nl]
        del self._rx[:nl + 1]
        return raw.decode('ascii', errors='ignore').strip()
