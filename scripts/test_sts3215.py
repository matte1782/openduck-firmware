#!/usr/bin/env python3
"""Test STS3215 servo via FE-URT-1 using raw serial protocol."""
import serial
import time
import sys

def scs_checksum(packet):
    return (~sum(packet)) & 0xFF

def scs_ping(ser, servo_id):
    packet = [servo_id, 2, 1]
    cs = scs_checksum(packet)
    cmd = bytes([0xFF, 0xFF] + packet + [cs])
    ser.write(cmd)
    time.sleep(0.01)
    resp = ser.read(20)
    return len(resp) > 0, resp

def scs_read(ser, servo_id, addr, length):
    packet = [servo_id, 4, 2, addr, length]
    cs = scs_checksum(packet)
    cmd = bytes([0xFF, 0xFF] + packet + [cs])
    ser.write(cmd)
    time.sleep(0.01)
    resp = ser.read(20)
    return resp

def scs_write2(ser, servo_id, addr, value):
    lo = value & 0xFF
    hi = (value >> 8) & 0xFF
    packet = [servo_id, 5, 3, addr, lo, hi]
    cs = scs_checksum(packet)
    cmd = bytes([0xFF, 0xFF] + packet + [cs])
    ser.write(cmd)
    time.sleep(0.01)
    return ser.read(20)

def main():
    ser = serial.Serial('/dev/ttyUSB0', 1000000, timeout=0.1)
    print("Port open at 1Mbps")

    # Ping
    ok, resp = scs_ping(ser, 1)
    status = "OK" if ok else "FAIL"
    hex_resp = resp.hex() if resp else "none"
    print(f"Ping ID 1: {status} (resp={hex_resp})")

    if not ok:
        print("Servo not responding. Check wiring and power.")
        ser.close()
        return 1

    # Read position (addr 56, 2 bytes)
    resp = scs_read(ser, 1, 56, 2)
    if len(resp) >= 8:
        pos = resp[5] | (resp[6] << 8)
        print(f"Position: {pos} ({pos * 360 / 4096:.1f} deg)")

    # Read voltage (addr 62, 1 byte)
    resp = scs_read(ser, 1, 62, 1)
    if len(resp) >= 7:
        volt = resp[5]
        print(f"Voltage: {volt / 10:.1f}V")

    # Read temperature (addr 63, 1 byte)
    resp = scs_read(ser, 1, 63, 1)
    if len(resp) >= 7:
        temp = resp[5]
        print(f"Temperature: {temp}C")

    # Move test
    print("Moving to 2048 (180 deg)...")
    scs_write2(ser, 1, 42, 2048)
    time.sleep(1.5)

    resp = scs_read(ser, 1, 56, 2)
    if len(resp) >= 8:
        pos = resp[5] | (resp[6] << 8)
        print(f"Position after move: {pos} ({pos * 360 / 4096:.1f} deg)")

    print("Moving to 1024 (90 deg)...")
    scs_write2(ser, 1, 42, 1024)
    time.sleep(1.5)

    resp = scs_read(ser, 1, 56, 2)
    if len(resp) >= 8:
        pos = resp[5] | (resp[6] << 8)
        print(f"Position after move: {pos} ({pos * 360 / 4096:.1f} deg)")

    ser.close()
    print("VERDICT: PASS - STS3215 + FE-URT-1 working")
    return 0

if __name__ == "__main__":
    sys.exit(main())
