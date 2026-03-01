"""STS3215 Serial Bus Servo Driver for OpenDuck Mini V3.

Provides hardware abstraction for Feetech STS3215 serial bus servos
connected via FE-URT-1 USB adapter (CH340 chipset).

Protocol: SCS (Serial Communication Servo)
- Packet: [0xFF 0xFF] [ID] [LENGTH] [INSTRUCTION] [PARAMS...] [CHECKSUM]
- Checksum: (~sum(id, length, instruction, params...)) & 0xFF
- Multi-byte values: little-endian

Hardware:
    - FE-URT-1 USB adapter -> /dev/ttyUSB0
    - CH340 chip, 1Mbps baud
    - All 4 FE-URT-1 ports are same electrical bus (daisy chain)
    - Power: 7.4V from 2S Li-ion battery pack

Position encoding:
    - Raw range: 0-4095 (12-bit)
    - Degrees: raw * 360 / 4096
    - Center: 2048 = 180°

Velocity enforcement: NOT implemented (positional limits only).
Pending design decision on velocity profile approach.

Hostile review #1 (Day 48): 3C + 5H found and fixed.
- C1: torque_disable_all uses BROADCAST ID 254 (<1ms vs 960ms)
- C2: mock_mode check moved inside lock (TOCTOU fix)
- C3: assert replaced with IOError (survives -O flag)
- H1: response header/checksum/error-byte validation added
- H2: set_position logs warning on no response
- H3: SerialException caught in _transact, wrapped as IOError
- H4: deinit acquires lock before closing port
- H5: removed fixed 10ms sleep, rely on serial timeout

Hostile review #2 (Day 48): 2C + 2H found and fixed.
- C4: _validate_response uses LENGTH field for response boundary (not resp[-1])
- C5: ping() validates response (was accepting any bytes as success)
- H6: set_position/torque_enable/torque_disable validate response error byte
- H7: torque_disable_all fallback clamps servo IDs to [0, 253]

Created: Day 48, 3 March 2026
"""

import re
import logging
import threading
from dataclasses import dataclass
from typing import Optional

try:
    import serial
    _HAS_SERIAL = True
except ImportError:
    serial = None  # type: ignore[assignment]
    _HAS_SERIAL = False

logger = logging.getLogger(__name__)

# Port whitelist regex — only /dev/ttyUSB*, /dev/ttyACM*, COM ports
_PORT_PATTERN = re.compile(r'^(/dev/tty(USB|ACM)\d+|COM\d{1,3})$')


@dataclass(frozen=True)
class STS3215Config:
    """Configuration for STS3215 serial bus connection.

    Attributes:
        port: Serial port path (must match whitelist pattern).
        baudrate: Communication speed (default 1Mbps per STS3215 spec).
        timeout: Serial read timeout in seconds.
    """
    port: str = "/dev/ttyUSB0"
    baudrate: int = 1_000_000
    timeout: float = 0.05


class STS3215Driver:
    """Driver for Feetech STS3215 serial bus servos.

    Thread Safety:
        All public methods are thread-safe. A single lock protects all
        serial I/O to prevent interleaved packets on the bus.
        _mock_mode is immutable after __init__ — never reassign at runtime.

    Mock Mode:
        If `pyserial` is not installed, the driver operates in mock mode.
        All methods return plausible default values without hardware access.
        This enables full test coverage on development machines.
    """

    # --- Protocol constants ---
    HEADER = b'\xFF\xFF'

    # Instructions
    INST_PING = 0x01
    INST_READ = 0x02
    INST_WRITE = 0x03

    # Register addresses (decimal)
    TORQUE_ENABLE_ADDR = 40   # 1 byte: 0=disable, 1=enable
    GOAL_POSITION_ADDR = 42   # 2 bytes: target position (0-4095)
    CURRENT_POSITION_ADDR = 56  # 2 bytes: current position (0-4095)
    VOLTAGE_ADDR = 62         # 1 byte: voltage * 10
    TEMPERATURE_ADDR = 63     # 1 byte: °C

    # Position limits
    RAW_MIN = 0
    RAW_MAX = 4095

    # Broadcast ID (write-only, no response expected from servos)
    BROADCAST_ID = 254

    # Max response size: 0xFF 0xFF + ID + LEN + ERR + data(2) + CS = 8 bytes typical.
    # 20 bytes provides margin for unexpected responses.
    _RESPONSE_SIZE = 20

    def __init__(self, config: Optional[STS3215Config] = None):
        """Initialize STS3215 driver.

        Args:
            config: Serial connection configuration. Uses defaults if None.

        Raises:
            ValueError: If port does not match whitelist pattern.
            RuntimeError: If serial port cannot be opened (hardware mode only).
        """
        self._config = config or STS3215Config()
        self._lock = threading.Lock()
        self._serial: Optional[object] = None
        self._mock_mode = not _HAS_SERIAL  # Immutable after __init__

        # Validate port against whitelist (prevents command injection)
        if not _PORT_PATTERN.match(self._config.port):
            raise ValueError(
                f"Port '{self._config.port}' does not match allowed pattern. "
                f"Expected /dev/ttyUSB*, /dev/ttyACM*, or COM*"
            )

        if not self._mock_mode:
            try:
                self._serial = serial.Serial(
                    port=self._config.port,
                    baudrate=self._config.baudrate,
                    timeout=self._config.timeout,
                )
                logger.info(
                    "STS3215 connected on %s at %d baud",
                    self._config.port, self._config.baudrate
                )
            except serial.SerialException as e:
                raise RuntimeError(
                    f"Failed to open serial port {self._config.port}: {e}"
                ) from e
        else:
            logger.warning("STS3215 running in MOCK mode (pyserial not installed)")

    @property
    def mock_mode(self) -> bool:
        """Whether the driver is operating without real hardware."""
        return self._mock_mode

    # --- Low-level protocol ---

    @staticmethod
    def _checksum(packet: list[int]) -> int:
        """Compute SCS protocol checksum.

        Args:
            packet: List of bytes [id, length, instruction, params...]

        Returns:
            Checksum byte: (~sum(packet)) & 0xFF
        """
        return (~sum(packet)) & 0xFF

    @staticmethod
    def _degrees_to_raw(degrees: float) -> int:
        """Convert degrees to raw servo position.

        Args:
            degrees: Angle in degrees (0-360).

        Returns:
            Raw position clamped to [0, 4095].
        """
        raw = round(degrees * 4096 / 360)  # round() not int() — fixes M2 truncation bias
        return max(0, min(4095, raw))

    @staticmethod
    def _raw_to_degrees(raw: int) -> float:
        """Convert raw servo position to degrees.

        Args:
            raw: Raw position (0-4095).

        Returns:
            Angle in degrees (0.0-360.0).
        """
        return raw * 360.0 / 4096.0

    def _build_ping_packet(self, servo_id: int) -> bytes:
        """Build a PING packet."""
        packet = [servo_id, 2, self.INST_PING]
        cs = self._checksum(packet)
        return self.HEADER + bytes(packet + [cs])

    def _build_read_packet(self, servo_id: int, addr: int, length: int) -> bytes:
        """Build a READ packet."""
        packet = [servo_id, 4, self.INST_READ, addr, length]
        cs = self._checksum(packet)
        return self.HEADER + bytes(packet + [cs])

    def _build_write1_packet(self, servo_id: int, addr: int, value: int) -> bytes:
        """Build a WRITE packet for a single byte."""
        packet = [servo_id, 4, self.INST_WRITE, addr, value & 0xFF]
        cs = self._checksum(packet)
        return self.HEADER + bytes(packet + [cs])

    def _build_write2_packet(self, servo_id: int, addr: int, value: int) -> bytes:
        """Build a WRITE packet for a 16-bit value (little-endian)."""
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        packet = [servo_id, 5, self.INST_WRITE, addr, lo, hi]
        cs = self._checksum(packet)
        return self.HEADER + bytes(packet + [cs])

    def _validate_response(self, resp: bytes, expected_id: int, min_len: int) -> None:
        """Validate SCS response: header, ID, LENGTH, checksum, error byte.

        C4 FIX: Uses the LENGTH field (resp[3]) to determine the actual
        response boundary, not resp[-1]. This is critical on multi-servo
        buses where serial.read(20) may return trailing garbage bytes.

        Response format: [0xFF 0xFF] [ID] [LEN] [ERR] [DATA...] [CS]
        Total bytes = 3 + LEN  (header:2 + ID:1 + LEN bytes including CS)

        Args:
            resp: Raw response bytes (may contain trailing garbage).
            expected_id: Servo ID we sent the command to.
            min_len: Minimum expected response length.

        Raises:
            IOError: If response is invalid.
        """
        if len(resp) < min_len:
            raise IOError(
                f"STS3215 ID {expected_id}: short response "
                f"({len(resp)} bytes, expected >={min_len})"
            )
        if resp[0:2] != self.HEADER:
            raise IOError(
                f"STS3215 ID {expected_id}: bad header {resp[0:2].hex()}"
            )
        if resp[2] != expected_id:
            raise IOError(
                f"STS3215 ID {expected_id}: ID mismatch (got {resp[2]})"
            )
        # Use LENGTH field to determine actual response boundary.
        # Response: [FF FF] [ID] [LEN] [ERR] [DATA...] [CS]
        # LEN counts bytes from ERR to CS inclusive.
        # Total valid bytes = 4 + LEN (2 header + ID + LEN + LEN payload).
        # Checksum is at index 3 + LEN (last valid byte).
        resp_len_field = resp[3]
        cs_index = 3 + resp_len_field  # Index of checksum byte
        if cs_index >= len(resp):
            raise IOError(
                f"STS3215 ID {expected_id}: LENGTH field ({resp_len_field}) "
                f"exceeds response size ({len(resp)})"
            )
        # Checksum over [ID, LEN, ERR, DATA...] (everything between header and CS)
        cs_byte = resp[cs_index]
        payload = list(resp[2:cs_index])  # ID + LEN + ERR + DATA (excludes CS)
        if self._checksum(payload) != cs_byte:
            raise IOError(
                f"STS3215 ID {expected_id}: checksum mismatch"
            )
        # Check error byte (byte index 4 in response)
        if resp[4] != 0:
            raise IOError(
                f"STS3215 ID {expected_id}: servo error flags 0x{resp[4]:02x}"
            )

    def _transact(self, packet: bytes, expect_response: bool = True) -> bytes:
        """Send packet and optionally read response.

        Thread-safe: acquires lock for the entire write+read cycle.
        Catches serial exceptions and wraps them as IOError.

        Args:
            packet: Raw bytes to send.
            expect_response: Whether to wait for and return a response.

        Returns:
            Response bytes, or empty bytes in mock mode or if no response expected.

        Raises:
            IOError: If serial port is unavailable or communication fails.
        """
        # C2 FIX: mock check inside lock to prevent TOCTOU race
        with self._lock:
            if self._mock_mode:
                return b''

            # C3 FIX: proper check instead of assert (survives python -O)
            if self._serial is None:
                raise IOError("STS3215: serial port is None (disconnected or not initialized)")

            try:
                self._serial.reset_input_buffer()
                self._serial.write(packet)
                if not expect_response:
                    return b''
                # H5 FIX: rely on serial timeout instead of fixed 10ms sleep.
                # At 1Mbps, a 8-byte response takes ~64us. The serial timeout
                # (default 50ms) is the upper bound for non-responsive servos.
                return self._serial.read(self._RESPONSE_SIZE)
            except Exception as e:
                # H3 FIX: wrap all serial errors as IOError
                raise IOError(f"STS3215 serial error: {e}") from e

    def _validate_servo_id(self, servo_id: int) -> None:
        """Validate servo ID range."""
        if not 0 <= servo_id <= 253:
            raise ValueError(f"Servo ID must be 0-253, got {servo_id}")

    # --- Public API ---

    def ping(self, servo_id: int) -> bool:
        """Check if a servo is responding on the bus.

        C5 FIX: Validates response header, ID, and checksum. Previously
        accepted any non-empty bytes as success, causing false positives
        from stale bus responses on multi-servo buses.

        Args:
            servo_id: Target servo ID (0-253).

        Returns:
            True if servo responded with valid packet, False otherwise.
        """
        self._validate_servo_id(servo_id)
        if self._mock_mode:
            return True
        packet = self._build_ping_packet(servo_id)
        try:
            resp = self._transact(packet)
            if len(resp) == 0:
                return False
            # Ping response: FF FF ID 02 00 CS = 6 bytes minimum
            self._validate_response(resp, servo_id, min_len=6)
            return True
        except IOError:
            return False

    def scan_bus(self, id_range: Optional[range] = None) -> list[int]:
        """Scan bus for responding servos.

        Note: With default range (1-253), this takes ~13s due to serial
        timeout on non-responding IDs. Use a narrow range for faster scans
        (e.g., range(2, 18) for known STS3215 IDs).

        Args:
            id_range: Range of IDs to scan. Defaults to range(1, 254).

        Returns:
            Sorted list of responding servo IDs.
        """
        if id_range is None:
            id_range = range(1, 254)
        found = []
        for sid in id_range:
            if self.ping(sid):
                found.append(sid)
        return sorted(found)

    def read_position(self, servo_id: int) -> float:
        """Read current servo position in degrees.

        Args:
            servo_id: Target servo ID (0-253).

        Returns:
            Current position in degrees (0.0-360.0).
            Returns 180.0 (center) in mock mode.

        Raises:
            ValueError: If servo_id out of range.
            IOError: If communication failure or invalid response.
        """
        self._validate_servo_id(servo_id)
        if self._mock_mode:
            return 180.0

        packet = self._build_read_packet(servo_id, self.CURRENT_POSITION_ADDR, 2)
        resp = self._transact(packet)
        # H1 FIX: validate response header, checksum, error byte
        self._validate_response(resp, servo_id, min_len=8)
        raw = resp[5] | (resp[6] << 8)
        return self._raw_to_degrees(raw)

    def set_position(self, servo_id: int, degrees: float) -> bool:
        """Move servo to target position.

        Args:
            servo_id: Target servo ID (0-253).
            degrees: Target angle (0-360).

        Returns:
            True if command was sent and acknowledged.

        Raises:
            ValueError: If servo_id or degrees out of range.
        """
        self._validate_servo_id(servo_id)
        if not 0.0 <= degrees <= 360.0:
            raise ValueError(f"Degrees must be 0-360, got {degrees}")

        if self._mock_mode:
            return True

        raw = self._degrees_to_raw(degrees)
        packet = self._build_write2_packet(servo_id, self.GOAL_POSITION_ADDR, raw)
        resp = self._transact(packet)
        if len(resp) == 0:
            logger.warning(
                "STS3215 ID %d: no response to set_position(%.1f deg)",
                servo_id, degrees
            )
            return False
        # H6 FIX: validate write response (catches servo error flags)
        try:
            self._validate_response(resp, servo_id, min_len=6)
        except IOError as e:
            logger.warning("STS3215 ID %d: set_position response error: %s", servo_id, e)
            return False
        return True

    def read_voltage(self, servo_id: int) -> float:
        """Read servo supply voltage.

        Args:
            servo_id: Target servo ID (0-253).

        Returns:
            Voltage in volts (e.g., 7.4). Returns 7.4 in mock mode.

        Raises:
            IOError: If communication failure or invalid response.
        """
        self._validate_servo_id(servo_id)
        if self._mock_mode:
            return 7.4

        packet = self._build_read_packet(servo_id, self.VOLTAGE_ADDR, 1)
        resp = self._transact(packet)
        self._validate_response(resp, servo_id, min_len=7)
        return resp[5] / 10.0

    def read_temperature(self, servo_id: int) -> int:
        """Read servo temperature in Celsius.

        Args:
            servo_id: Target servo ID (0-253).

        Returns:
            Temperature in °C. Returns 25 in mock mode.

        Raises:
            IOError: If communication failure or invalid response.
        """
        self._validate_servo_id(servo_id)
        if self._mock_mode:
            return 25

        packet = self._build_read_packet(servo_id, self.TEMPERATURE_ADDR, 1)
        resp = self._transact(packet)
        self._validate_response(resp, servo_id, min_len=7)
        return resp[5]

    def torque_enable(self, servo_id: int) -> bool:
        """Enable torque (hold position) on a servo.

        Args:
            servo_id: Target servo ID (0-253).

        Returns:
            True if command sent and acknowledged without error.
        """
        self._validate_servo_id(servo_id)
        if self._mock_mode:
            return True

        packet = self._build_write1_packet(servo_id, self.TORQUE_ENABLE_ADDR, 1)
        resp = self._transact(packet)
        if len(resp) < 6:
            return False
        try:
            self._validate_response(resp, servo_id, min_len=6)
        except IOError:
            return False
        return True

    def torque_disable(self, servo_id: int) -> bool:
        """Disable torque (servo goes limp) on a single servo.

        Args:
            servo_id: Target servo ID (0-253).

        Returns:
            True if command sent and acknowledged without error.
        """
        self._validate_servo_id(servo_id)
        if self._mock_mode:
            return True

        packet = self._build_write1_packet(servo_id, self.TORQUE_ENABLE_ADDR, 0)
        resp = self._transact(packet)
        if len(resp) < 6:
            return False
        try:
            self._validate_response(resp, servo_id, min_len=6)
        except IOError:
            return False
        return True

    def torque_disable_all(self, servo_ids: list[int]) -> None:
        """Disable torque on all servos using BROADCAST for minimum latency.

        SAFETY-CRITICAL: This method NEVER raises exceptions.
        Uses broadcast ID 254 for single-packet disable (<1ms).
        Falls back to individual disable if broadcast fails.

        C1 FIX: Previous implementation iterated all IDs individually,
        taking ~960ms worst case. Broadcast reduces this to <1ms.

        Args:
            servo_ids: List of servo IDs (used only for individual fallback).
        """
        if self._mock_mode:
            return

        # Primary: broadcast torque disable to ALL servos on bus (<1ms)
        try:
            packet = self._build_write1_packet(
                self.BROADCAST_ID, self.TORQUE_ENABLE_ADDR, 0
            )
            # Broadcast: no response expected from any servo
            self._transact(packet, expect_response=False)
            return
        except Exception as e:
            logger.error("torque_disable_all: broadcast failed: %s, trying individual", e)

        # Fallback: individual disable (slower but more robust)
        # H7 FIX: skip invalid IDs to prevent malformed packets on bus
        for sid in servo_ids:
            if not isinstance(sid, int) or not 0 <= sid <= 253:
                logger.error("torque_disable_all: skipping invalid ID %r", sid)
                continue
            try:
                packet = self._build_write1_packet(sid, self.TORQUE_ENABLE_ADDR, 0)
                self._transact(packet, expect_response=False)
            except Exception as e:
                logger.error(
                    "torque_disable_all: failed to disable ID %d", sid, exc_info=True
                )

    def deinit(self) -> None:
        """Close serial port and release resources."""
        # H4 FIX: acquire lock before modifying _serial
        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                    logger.info("STS3215 serial port closed")
                except Exception as e:
                    logger.error("STS3215 deinit error: %s", e)
                self._serial = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit — ensures port is closed."""
        self.deinit()
