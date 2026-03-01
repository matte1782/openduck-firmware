"""Unit tests for STS3215 serial bus servo driver.

Tests cover:
- Config validation (port whitelist, defaults)
- Checksum computation
- Degrees/raw conversion (round() not int())
- Packet building (ping, read, write1, write2)
- Response validation (header, ID, checksum, error byte)
- Mock mode behavior (all methods work without hardware)
- Error handling (bad servo ID, short responses, serial errors)
- Thread safety (concurrent access, lock coverage)
- torque_disable_all: broadcast + fallback, never raises
- deinit under lock
- Context manager

All tests run on Windows/Linux without hardware (mock mode or mocked serial).

Hostile review (Day 48): 3C + 5H found, all fixed and tested.
"""

import threading
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.drivers.servo.sts3215 import STS3215Config, STS3215Driver, _PORT_PATTERN


# ============================================================
# Helper: build valid SCS responses with correct checksums
# ============================================================

def _make_response(servo_id: int, error: int, data: bytes) -> bytes:
    """Build a valid SCS response with correct checksum.

    Response format: [0xFF 0xFF] [ID] [LEN] [ERROR] [DATA...] [CHECKSUM]
    LEN = 2 + len(data)  (error byte + data + checksum)
    """
    length = 2 + len(data)
    payload = [servo_id, length, error] + list(data)
    cs = (~sum(payload)) & 0xFF
    return b'\xFF\xFF' + bytes(payload) + bytes([cs])


# Pre-built valid responses for common operations
def _ping_response(servo_id: int = 1) -> bytes:
    return _make_response(servo_id, 0, b'')


def _position_response(servo_id: int, raw: int) -> bytes:
    lo = raw & 0xFF
    hi = (raw >> 8) & 0xFF
    return _make_response(servo_id, 0, bytes([lo, hi]))


def _voltage_response(servo_id: int, raw_voltage: int) -> bytes:
    return _make_response(servo_id, 0, bytes([raw_voltage]))


def _temperature_response(servo_id: int, temp_c: int) -> bytes:
    return _make_response(servo_id, 0, bytes([temp_c]))


# ============================================================
# Config validation
# ============================================================

class TestSTS3215Config:

    def test_defaults(self):
        cfg = STS3215Config()
        assert cfg.port == "/dev/ttyUSB0"
        assert cfg.baudrate == 1_000_000
        assert cfg.timeout == 0.05

    def test_custom_values(self):
        cfg = STS3215Config(port="/dev/ttyUSB1", baudrate=500_000, timeout=0.1)
        assert cfg.port == "/dev/ttyUSB1"
        assert cfg.baudrate == 500_000
        assert cfg.timeout == 0.1

    def test_frozen(self):
        cfg = STS3215Config()
        with pytest.raises(AttributeError):
            cfg.port = "/dev/ttyUSB1"  # type: ignore[misc]


class TestPortWhitelist:

    @pytest.mark.parametrize("port", [
        "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB99",
        "/dev/ttyACM0", "/dev/ttyACM1",
        "COM1", "COM3", "COM99",
    ])
    def test_valid_ports(self, port):
        assert _PORT_PATTERN.match(port) is not None

    @pytest.mark.parametrize("port", [
        "/dev/tty0",
        "/dev/sda1",
        "/tmp/exploit; rm -rf /",
        "../../etc/passwd",
        "",
        "/dev/ttyUSB",
        "COM",
        "com1",  # lowercase
        "/dev/ttyUSB0; cat /etc/shadow",
        "COM99999",  # L1: COM port limited to 3 digits
    ])
    def test_invalid_ports(self, port):
        assert _PORT_PATTERN.match(port) is None

    def test_driver_rejects_bad_port(self):
        cfg = STS3215Config(port="/tmp/evil; rm -rf /")
        with pytest.raises(ValueError, match="does not match allowed pattern"):
            STS3215Driver(config=cfg)


# ============================================================
# Checksum
# ============================================================

class TestChecksum:

    def test_ping_packet(self):
        # Ping ID 1: packet = [1, 2, 1] -> ~(1+2+1) = ~4 = 251
        assert STS3215Driver._checksum([1, 2, 1]) == 251

    def test_read_packet(self):
        # Read ID 1, addr 56, length 2: [1, 4, 2, 56, 2]
        total = 1 + 4 + 2 + 56 + 2  # 65
        expected = (~65) & 0xFF  # 190
        assert STS3215Driver._checksum([1, 4, 2, 56, 2]) == expected

    def test_write_packet(self):
        # Write ID 1, addr 42, value 2048 -> lo=0, hi=8
        # [1, 5, 3, 42, 0, 8]
        total = 1 + 5 + 3 + 42 + 0 + 8  # 59
        expected = (~59) & 0xFF  # 196
        assert STS3215Driver._checksum([1, 5, 3, 42, 0, 8]) == expected

    def test_checksum_wraps(self):
        # Sum > 255 should still produce valid single byte
        packet = [254, 255, 255, 255, 255]
        cs = STS3215Driver._checksum(packet)
        assert 0 <= cs <= 255


# ============================================================
# Degree/raw conversion
# ============================================================

class TestConversions:

    def test_degrees_to_raw_zero(self):
        assert STS3215Driver._degrees_to_raw(0.0) == 0

    def test_degrees_to_raw_180(self):
        assert STS3215Driver._degrees_to_raw(180.0) == 2048

    def test_degrees_to_raw_360(self):
        # round(360 * 4096/360) = 4096, clamped to 4095
        assert STS3215Driver._degrees_to_raw(360.0) == 4095

    def test_degrees_to_raw_90(self):
        assert STS3215Driver._degrees_to_raw(90.0) == 1024

    def test_degrees_to_raw_clamps_negative(self):
        assert STS3215Driver._degrees_to_raw(-10.0) == 0

    def test_degrees_to_raw_clamps_over(self):
        assert STS3215Driver._degrees_to_raw(400.0) == 4095

    def test_degrees_to_raw_uses_round_not_truncate(self):
        """M2 FIX: round() eliminates systematic -0.044 deg bias from int()."""
        # 89.9 deg: int(89.9*4096/360) = 1022, round(89.9*4096/360) = 1023
        assert STS3215Driver._degrees_to_raw(89.9) == 1023

    def test_raw_to_degrees_zero(self):
        assert STS3215Driver._raw_to_degrees(0) == pytest.approx(0.0)

    def test_raw_to_degrees_2048(self):
        assert STS3215Driver._raw_to_degrees(2048) == pytest.approx(180.0)

    def test_raw_to_degrees_4095(self):
        assert STS3215Driver._raw_to_degrees(4095) == pytest.approx(359.912, abs=0.01)

    def test_roundtrip(self):
        for deg in [0, 45, 90, 135, 180, 270]:
            raw = STS3215Driver._degrees_to_raw(deg)
            back = STS3215Driver._raw_to_degrees(raw)
            assert back == pytest.approx(deg, abs=0.1)


# ============================================================
# Packet building
# ============================================================

class TestPacketBuilding:

    def setup_method(self):
        self.driver = STS3215Driver()

    def test_ping_packet_format(self):
        pkt = self.driver._build_ping_packet(1)
        assert pkt[:2] == b'\xFF\xFF'
        assert pkt[2] == 1   # servo ID
        assert pkt[3] == 2   # length
        assert pkt[4] == 1   # PING instruction

    def test_read_packet_format(self):
        pkt = self.driver._build_read_packet(5, 56, 2)
        assert pkt[:2] == b'\xFF\xFF'
        assert pkt[2] == 5   # servo ID
        assert pkt[3] == 4   # length
        assert pkt[4] == 2   # READ instruction
        assert pkt[5] == 56  # address
        assert pkt[6] == 2   # read length

    def test_write1_packet_format(self):
        pkt = self.driver._build_write1_packet(3, 40, 1)
        assert pkt[:2] == b'\xFF\xFF'
        assert pkt[2] == 3   # servo ID
        assert pkt[3] == 4   # length
        assert pkt[4] == 3   # WRITE instruction
        assert pkt[5] == 40  # address
        assert pkt[6] == 1   # value

    def test_write2_packet_format(self):
        pkt = self.driver._build_write2_packet(1, 42, 2048)
        assert pkt[:2] == b'\xFF\xFF'
        assert pkt[2] == 1   # servo ID
        assert pkt[3] == 5   # length
        assert pkt[4] == 3   # WRITE instruction
        assert pkt[5] == 42  # address
        assert pkt[6] == 0   # lo byte of 2048
        assert pkt[7] == 8   # hi byte of 2048

    def test_write2_little_endian(self):
        # 0x1234 -> lo=0x34, hi=0x12
        pkt = self.driver._build_write2_packet(1, 42, 0x1234)
        assert pkt[6] == 0x34
        assert pkt[7] == 0x12


# ============================================================
# Response validation (H1 FIX)
# ============================================================

class TestResponseValidation:

    def setup_method(self):
        self.driver = STS3215Driver()

    def test_valid_response_passes(self):
        resp = _ping_response(1)
        # Should not raise
        self.driver._validate_response(resp, expected_id=1, min_len=6)

    def test_short_response_rejected(self):
        with pytest.raises(IOError, match="short response"):
            self.driver._validate_response(b'\xFF\xFF\x01', expected_id=1, min_len=6)

    def test_bad_header_rejected(self):
        resp = b'\xFE\xFF\x01\x02\x00\xFC'
        with pytest.raises(IOError, match="bad header"):
            self.driver._validate_response(resp, expected_id=1, min_len=6)

    def test_wrong_id_rejected(self):
        resp = _ping_response(2)  # Response from ID 2
        with pytest.raises(IOError, match="ID mismatch"):
            self.driver._validate_response(resp, expected_id=1, min_len=6)

    def test_bad_checksum_rejected(self):
        resp = bytearray(_ping_response(1))
        resp[-1] ^= 0xFF  # Corrupt checksum
        with pytest.raises(IOError, match="checksum mismatch"):
            self.driver._validate_response(bytes(resp), expected_id=1, min_len=6)

    def test_error_byte_rejected(self):
        resp = _make_response(1, error=0x04, data=b'')  # Error flag set
        with pytest.raises(IOError, match="servo error flags"):
            self.driver._validate_response(resp, expected_id=1, min_len=6)

    def test_position_response_validates(self):
        resp = _position_response(1, 2048)
        self.driver._validate_response(resp, expected_id=1, min_len=8)


# ============================================================
# Mock mode behavior
# ============================================================

class TestMockMode:

    def setup_method(self):
        self.driver = STS3215Driver()

    def test_is_mock(self):
        assert self.driver.mock_mode is True

    def test_ping_returns_true(self):
        assert self.driver.ping(1) is True

    def test_scan_bus(self):
        found = self.driver.scan_bus(range(1, 5))
        assert found == [1, 2, 3, 4]

    def test_read_position_returns_center(self):
        assert self.driver.read_position(1) == 180.0

    def test_set_position_returns_true(self):
        assert self.driver.set_position(1, 90.0) is True

    def test_read_voltage_returns_default(self):
        assert self.driver.read_voltage(1) == 7.4

    def test_read_temperature_returns_default(self):
        assert self.driver.read_temperature(1) == 25

    def test_torque_enable(self):
        assert self.driver.torque_enable(1) is True

    def test_torque_disable(self):
        assert self.driver.torque_disable(1) is True

    def test_torque_disable_all(self):
        # Must not raise
        self.driver.torque_disable_all([1, 2, 3, 4, 5])

    def test_deinit(self):
        self.driver.deinit()

    def test_context_manager(self):
        with STS3215Driver() as d:
            assert d.mock_mode is True
        # After exit, should not raise on second deinit
        d.deinit()


# ============================================================
# Servo ID validation
# ============================================================

class TestServoIdValidation:

    def setup_method(self):
        self.driver = STS3215Driver()

    def test_negative_id(self):
        with pytest.raises(ValueError, match="Servo ID must be 0-253"):
            self.driver.ping(-1)

    def test_id_254_rejected(self):
        with pytest.raises(ValueError, match="Servo ID must be 0-253"):
            self.driver.ping(254)

    def test_id_255_rejected(self):
        with pytest.raises(ValueError, match="Servo ID must be 0-253"):
            self.driver.read_position(255)

    def test_id_0_accepted(self):
        assert self.driver.ping(0) is True

    def test_id_253_accepted(self):
        assert self.driver.ping(253) is True


# ============================================================
# Position validation
# ============================================================

class TestPositionValidation:

    def setup_method(self):
        self.driver = STS3215Driver()

    def test_negative_degrees_rejected(self):
        with pytest.raises(ValueError, match="Degrees must be 0-360"):
            self.driver.set_position(1, -1.0)

    def test_over_360_rejected(self):
        with pytest.raises(ValueError, match="Degrees must be 0-360"):
            self.driver.set_position(1, 361.0)

    def test_zero_accepted(self):
        assert self.driver.set_position(1, 0.0) is True

    def test_360_accepted(self):
        assert self.driver.set_position(1, 360.0) is True


# ============================================================
# Hardware mode with mocked serial
# ============================================================

class TestHardwareMode:

    @pytest.fixture
    def mock_serial_driver(self):
        """Create driver with mocked serial port."""
        with patch('src.drivers.servo.sts3215._HAS_SERIAL', True), \
             patch('src.drivers.servo.sts3215.serial') as mock_serial_mod:
            mock_port = MagicMock()
            mock_serial_mod.Serial.return_value = mock_port
            mock_serial_mod.SerialException = Exception

            driver = STS3215Driver()
            driver._mock_mode = False
            driver._serial = mock_port
            yield driver, mock_port

    def test_ping_success(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = _ping_response(1)
        assert driver.ping(1) is True

    def test_ping_no_response(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = b''
        assert driver.ping(1) is False

    def test_ping_serial_error_returns_false(self, mock_serial_driver):
        """H3 FIX: serial errors caught, ping returns False."""
        driver, mock_port = mock_serial_driver
        mock_port.write.side_effect = Exception("USB disconnected")
        assert driver.ping(1) is False

    def test_read_position(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = _position_response(1, 2048)
        pos = driver.read_position(1)
        assert pos == pytest.approx(180.0)

    def test_read_position_short_response(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = b'\xFF\xFF\x01'
        with pytest.raises(IOError, match="short response"):
            driver.read_position(1)

    def test_read_position_bad_checksum(self, mock_serial_driver):
        """H1 FIX: corrupted response detected."""
        driver, mock_port = mock_serial_driver
        resp = bytearray(_position_response(1, 2048))
        resp[-1] ^= 0xFF  # Corrupt checksum
        mock_port.read.return_value = bytes(resp)
        with pytest.raises(IOError, match="checksum mismatch"):
            driver.read_position(1)

    def test_set_position_sends_packet(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = _ping_response(1)  # Any valid response
        driver.set_position(1, 180.0)
        mock_port.write.assert_called_once()
        written = mock_port.write.call_args[0][0]
        assert written[:2] == b'\xFF\xFF'

    def test_set_position_no_response_returns_false(self, mock_serial_driver):
        """H2 FIX: logs warning and returns False on no response."""
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = b''
        assert driver.set_position(1, 90.0) is False

    def test_read_voltage(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = _voltage_response(1, 74)
        v = driver.read_voltage(1)
        assert v == pytest.approx(7.4)

    def test_read_voltage_short_response(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = b'\xFF\xFF'
        with pytest.raises(IOError, match="short response"):
            driver.read_voltage(1)

    def test_read_temperature(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = _temperature_response(1, 45)
        t = driver.read_temperature(1)
        assert t == 45

    def test_read_temperature_short_response(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = b'\xFF'
        with pytest.raises(IOError, match="short response"):
            driver.read_temperature(1)

    def test_torque_enable_sends_write(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = _ping_response(1)
        result = driver.torque_enable(1)
        assert result is True

    def test_torque_enable_short_response_fails(self, mock_serial_driver):
        """M6 FIX: need >=6 bytes for valid response, not just >0."""
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = b'\xFF'  # Too short
        result = driver.torque_enable(1)
        assert result is False

    def test_torque_disable_sends_write(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        mock_port.read.return_value = _ping_response(1)
        result = driver.torque_disable(1)
        assert result is True

    def test_deinit_closes_port(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        driver.deinit()
        mock_port.close.assert_called_once()
        assert driver._serial is None

    def test_deinit_idempotent(self, mock_serial_driver):
        driver, mock_port = mock_serial_driver
        driver.deinit()
        driver.deinit()  # second call should not raise

    def test_serial_error_wraps_as_ioerror(self, mock_serial_driver):
        """H3 FIX: SerialException wrapped as IOError."""
        driver, mock_port = mock_serial_driver
        mock_port.write.side_effect = Exception("USB yanked")
        with pytest.raises(IOError, match="serial error"):
            driver.read_position(1)

    def test_transact_with_none_serial_raises_ioerror(self, mock_serial_driver):
        """C3 FIX: proper IOError instead of assert."""
        driver, _ = mock_serial_driver
        driver._serial = None
        with pytest.raises(IOError, match="serial port is None"):
            driver._transact(b'\xFF\xFF\x01\x02\x01\xFB')


# ============================================================
# torque_disable_all safety (C1 FIX: broadcast)
# ============================================================

class TestTorqueDisableAllSafety:

    def test_uses_broadcast_id(self):
        """C1 FIX: torque_disable_all sends BROADCAST (ID 254) for <1ms."""
        driver = STS3215Driver()
        driver._mock_mode = False
        packets_sent = []

        def capture_transact(packet, expect_response=True):
            packets_sent.append((packet, expect_response))
            return b''

        driver._transact = capture_transact
        driver.torque_disable_all([2, 3, 4])

        # Should send exactly 1 broadcast packet, not 3 individual
        assert len(packets_sent) == 1
        packet, expect_resp = packets_sent[0]
        assert packet[2] == 254  # Broadcast ID
        assert expect_resp is False  # No response expected

    def test_never_raises_on_broadcast_failure(self):
        """torque_disable_all must NEVER raise, even if broadcast fails."""
        driver = STS3215Driver()
        driver._mock_mode = False

        # Make _transact raise for every call
        driver._transact = Mock(side_effect=Exception("bus error"))

        # This must not raise
        driver.torque_disable_all([1, 2, 3, 4, 5])

    def test_falls_back_to_individual_on_broadcast_failure(self):
        """If broadcast fails, tries individual disable for each ID."""
        driver = STS3215Driver()
        driver._mock_mode = False
        call_count = 0

        def counting_transact(packet, expect_response=True):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("broadcast failed")
            return b''

        driver._transact = counting_transact
        driver.torque_disable_all([2, 3, 4])
        # 1 broadcast (failed) + 3 individual = 4 calls
        assert call_count == 4

    def test_individual_fallback_never_raises(self):
        """Even if all individual disables fail, never raises."""
        driver = STS3215Driver()
        driver._mock_mode = False

        driver._transact = Mock(side_effect=Exception("everything broken"))
        # Must not raise
        driver.torque_disable_all([1, 2, 3])

    def test_mock_mode_returns_immediately(self):
        """In mock mode, torque_disable_all is a no-op."""
        driver = STS3215Driver()
        assert driver._mock_mode is True
        driver.torque_disable_all([1, 2, 3])  # Should not raise


# ============================================================
# Thread safety
# ============================================================

class TestThreadSafety:

    def test_concurrent_pings(self):
        """Multiple threads can ping without corruption."""
        driver = STS3215Driver()  # mock mode
        results = []
        errors = []

        def ping_servo(sid):
            try:
                result = driver.ping(sid)
                results.append((sid, result))
            except Exception as e:
                errors.append((sid, e))

        threads = [threading.Thread(target=ping_servo, args=(i,)) for i in range(1, 11)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert len(results) == 10

    def test_lock_exists(self):
        driver = STS3215Driver()
        assert isinstance(driver._lock, type(threading.Lock()))

    def test_transact_holds_lock_for_write_and_read(self):
        """Verify lock covers both write and read in hardware mode."""
        driver = STS3215Driver()
        driver._mock_mode = False
        mock_serial = MagicMock()
        mock_serial.read.return_value = _ping_response(1)
        driver._serial = mock_serial

        lock_held_during_write = False
        lock_held_during_read = False

        original_write = mock_serial.write
        original_read = mock_serial.read

        def tracking_write(data):
            nonlocal lock_held_during_write
            lock_held_during_write = driver._lock.locked()
            return original_write(data)

        def tracking_read(n):
            nonlocal lock_held_during_read
            lock_held_during_read = driver._lock.locked()
            return original_read(n)

        mock_serial.write = tracking_write
        mock_serial.read = tracking_read

        driver._transact(b'\xFF\xFF\x01\x02\x01\xFB')

        assert lock_held_during_write is True
        assert lock_held_during_read is True

    def test_mock_check_inside_lock(self):
        """C2 FIX: mock_mode check is inside the lock in _transact."""
        driver = STS3215Driver()  # mock mode
        lock_held_during_mock_check = False

        original_transact = driver._transact

        # We verify by checking that _transact acquires the lock even in mock mode
        def check_lock(*args, **kwargs):
            nonlocal lock_held_during_mock_check
            # If we can't acquire the lock non-blocking, it means _transact holds it
            # But in mock mode we need a different approach: patch and verify
            return original_transact(*args, **kwargs)

        # Verify the implementation: _transact starts with `with self._lock:`
        # then checks `if self._mock_mode:`. We test this by checking that
        # the lock is held when we try to acquire it from another thread.
        acquired = threading.Event()
        in_transact = threading.Event()

        def hold_lock():
            with driver._lock:
                acquired.set()
                in_transact.wait(timeout=2)

        t = threading.Thread(target=hold_lock)
        t.start()
        acquired.wait(timeout=2)

        # Lock is held by the other thread. _transact should block.
        import time
        blocked = True

        def try_transact():
            nonlocal blocked
            driver._transact(b'\xFF\xFF')
            blocked = False

        t2 = threading.Thread(target=try_transact)
        t2.start()
        time.sleep(0.05)
        # If mock check was outside lock, t2 would return immediately
        assert blocked is True  # _transact is waiting for lock

        in_transact.set()
        t.join(timeout=2)
        t2.join(timeout=2)

    def test_deinit_holds_lock(self):
        """H4 FIX: deinit acquires lock before modifying _serial."""
        driver = STS3215Driver()
        driver._mock_mode = False
        mock_serial = MagicMock()
        driver._serial = mock_serial

        lock_held_during_close = False

        def tracking_close():
            nonlocal lock_held_during_close
            lock_held_during_close = driver._lock.locked()

        mock_serial.close = tracking_close
        driver.deinit()
        assert lock_held_during_close is True


# ============================================================
# Edge cases
# ============================================================

class TestEdgeCases:

    def test_scan_bus_empty_range(self):
        driver = STS3215Driver()
        assert driver.scan_bus(range(0, 0)) == []

    def test_scan_bus_single_id(self):
        driver = STS3215Driver()
        assert driver.scan_bus(range(5, 6)) == [5]

    def test_default_config_used_when_none(self):
        driver = STS3215Driver(config=None)
        assert driver._config.port == "/dev/ttyUSB0"

    def test_set_position_boundary_0(self):
        driver = STS3215Driver()
        assert driver.set_position(1, 0.0) is True

    def test_set_position_boundary_360(self):
        driver = STS3215Driver()
        assert driver.set_position(1, 360.0) is True

    def test_context_manager_closes_on_exit(self):
        driver = STS3215Driver()
        driver._mock_mode = False
        mock_serial = MagicMock()
        driver._serial = mock_serial

        with driver:
            pass
        mock_serial.close.assert_called_once()
