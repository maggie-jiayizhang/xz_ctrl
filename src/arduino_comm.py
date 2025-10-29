"""
Arduino communication helper

Provides simple utilities to detect an attached Arduino on serial ports,
perform a basic handshake, and query a lightweight status.

Protocol expectations (from stepper_controller.ino):
- On boot, Arduino prints "READY" once.
- Responds to "PING" with "PONG".
- Responds to "STATUS" with one of:
    STATUS RUNNING
    STATUS READY    (program loaded but not running)
    STATUS IDLE     (no program loaded)

If STATUS is not supported (older firmware), we fall back to just PING and
return status "CONNECTED".
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict
import time

import serial
from serial import Serial
from serial.tools import list_ports


DEFAULT_BAUD = 115200
READ_TIMEOUT = 1.0  # seconds


@dataclass
class ArduinoStatus:
    connected: bool
    port: Optional[str]
    status: str  # RUNNING | READY | IDLE | CONNECTED | NOT_FOUND | ERROR
    detail: Optional[str] = None


class ArduinoClient:
    def __init__(self, baudrate: int = DEFAULT_BAUD, timeout: float = READ_TIMEOUT):
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[Serial] = None
        self.port: Optional[str] = None

    # ---------- Low-level helpers ----------
    def _open(self, port: str) -> bool:
        try:
            self.ser = serial.Serial(port=port, baudrate=self.baudrate, timeout=self.timeout)
            self.port = port
            # Give device a brief moment
            time.sleep(0.2)
            # Flush any noise
            self._flush_input()
            return True
        except Exception:
            self.ser = None
            self.port = None
            return False

    def _flush_input(self):
        if not self.ser:
            return
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def _read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        if not self.ser:
            return None
        prev_timeout = self.ser.timeout
        if timeout is not None:
            self.ser.timeout = timeout
        try:
            line = self.ser.readline()
            if not line:
                return None
            try:
                return line.decode(errors="ignore").strip()
            except Exception:
                return None
        finally:
            if timeout is not None:
                self.ser.timeout = prev_timeout

    def _write_line(self, s: str) -> bool:
        if not self.ser:
            return False
        try:
            data = (s.strip() + "\n").encode()
            self.ser.write(data)
            self.ser.flush()
            return True
        except Exception:
            return False

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            self.port = None

    # ---------- Detection / Handshake ----------
    def _handshake(self) -> bool:
        """Try to confirm device by PING/PONG handshake; also accept a stray READY line."""
        # Read any immediate line (e.g., READY after opening)
        start = time.time()
        while time.time() - start < 0.6:
            line = self._read_line(timeout=0.1)
            if not line:
                continue
            if line.upper().startswith("READY"):
                # Good sign; still also try PING
                break

        # Send PING and expect PONG
        if not self._write_line("PING"):
            return False
        for _ in range(10):
            line = self._read_line(timeout=0.2)
            if line and line.upper().startswith("PONG"):
                return True
        return False

    def find_and_connect(self) -> Tuple[bool, Optional[str]]:
        """Scan available serial ports and connect to the first Arduino-like device that responds to PING/PONG."""
        # Try to prioritize ports that look like Arduino/USB serial
        ports = list_ports.comports()
        # Sort to try likely candidates first
        def score(p):
            desc = (p.description or "").lower()
            manu = (p.manufacturer or "").lower()
            if "arduino" in desc or "arduino" in manu:
                return 0
            if "usb" in desc or "ch340" in desc or "serial" in desc:
                return 1
            return 2
        ports_sorted = sorted(ports, key=score)

        for p in ports_sorted:
            if self._open(p.device):
                if self._handshake():
                    return True, p.device
                # Not our device; close and try next
                self.close()
        return False, None

    # ---------- Public API ----------
    def check_connection(self) -> ArduinoStatus:
        """Attempt to connect and report if an Arduino is reachable."""
        # If already open, try a quick ping
        if self.ser and self.port:
            if self._write_line("PING"):
                line = self._read_line(timeout=0.4)
                if line and line.upper().startswith("PONG"):
                    return ArduinoStatus(True, self.port, "CONNECTED")
            # If ping fails, drop and retry
            self.close()

        ok, port = self.find_and_connect()
        if ok and port:
            return ArduinoStatus(True, port, "CONNECTED")
        return ArduinoStatus(False, None, "NOT_FOUND")

    def get_status(self) -> ArduinoStatus:
        """Ensure connected and then query STATUS; falls back to CONNECTED if STATUS unsupported."""
        status = self.check_connection()
        if not status.connected:
            return status

        # Try STATUS command
        if not self._write_line("STATUS"):
            return ArduinoStatus(True, self.port, "CONNECTED", detail="Write failed")

        line = self._read_line(timeout=0.6)
        if not line:
            # Try one more read in case of latency
            line = self._read_line(timeout=0.6)

        if line and line.upper().startswith("STATUS"):
            # Expected format: STATUS <WORD>
            parts = line.split()
            if len(parts) >= 2:
                st = parts[1].upper()
                if st in ("RUNNING", "READY", "IDLE"):
                    return ArduinoStatus(True, self.port, st)
                return ArduinoStatus(True, self.port, "CONNECTED", detail=line)
            return ArduinoStatus(True, self.port, "CONNECTED", detail=line)

        # Older firmware; we at least know it's connected
        return ArduinoStatus(True, self.port, "CONNECTED")


# Simple manual test runner
if __name__ == "__main__":
    client = ArduinoClient()
    st = client.get_status()
    print(f"Connected: {st.connected}, Port: {st.port}, Status: {st.status}")
    if st.detail:
        print(f" Detail: {st.detail}")
    client.close()
