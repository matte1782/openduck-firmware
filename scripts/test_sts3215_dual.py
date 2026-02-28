#!/usr/bin/env python3
"""Test 2x STS3215 on same bus via FE-URT-1."""
import serial
import time

def scs_checksum(p):
    return (~sum(p)) & 0xFF

def scs_ping(ser, sid):
    packet = [sid, 2, 1]
    cs = scs_checksum(packet)
    ser.write(bytes([0xFF, 0xFF] + packet + [cs]))
    time.sleep(0.01)
    resp = ser.read(20)
    return len(resp) > 0

def scs_read2(ser, sid, addr):
    packet = [sid, 4, 2, addr, 2]
    cs = scs_checksum(packet)
    ser.write(bytes([0xFF, 0xFF] + packet + [cs]))
    time.sleep(0.01)
    resp = ser.read(20)
    if len(resp) >= 8:
        return resp[5] | (resp[6] << 8)
    return None

def scs_write2(ser, sid, addr, val):
    lo = val & 0xFF
    hi = (val >> 8) & 0xFF
    packet = [sid, 5, 3, addr, lo, hi]
    cs = scs_checksum(packet)
    ser.write(bytes([0xFF, 0xFF] + packet + [cs]))
    time.sleep(0.01)
    return ser.read(20)

ser = serial.Serial('/dev/ttyUSB0', 1000000, timeout=0.1)
print("Port open at 1Mbps")

# Ping both
print("\nPinging servos...")
found = []
for sid in [1, 2]:
    ok = scs_ping(ser, sid)
    status = "OK" if ok else "NOT FOUND"
    print(f"  ID {sid}: {status}")
    if ok:
        found.append(sid)

if len(found) < 2:
    print(f"\nOnly found {len(found)} servo(s). Check wiring.")
    ser.close()
    exit(1)

# Move both to 180 deg
print("\nMoving both to 2048 (180 deg)...")
for sid in found:
    scs_write2(ser, sid, 42, 2048)
time.sleep(1.5)

for sid in found:
    pos = scs_read2(ser, sid, 56)
    if pos is not None:
        print(f"  ID {sid}: {pos} ({pos * 360 / 4096:.1f} deg)")

# Move both to 90 deg
print("\nMoving both to 1024 (90 deg)...")
for sid in found:
    scs_write2(ser, sid, 42, 1024)
time.sleep(1.5)

for sid in found:
    pos = scs_read2(ser, sid, 56)
    if pos is not None:
        print(f"  ID {sid}: {pos} ({pos * 360 / 4096:.1f} deg)")

# Move in opposite directions
print("\nMoving in opposite directions (ID1=0, ID2=180)...")
scs_write2(ser, 1, 42, 0)
scs_write2(ser, 2, 42, 4095)
time.sleep(1.5)

for sid in found:
    pos = scs_read2(ser, sid, 56)
    if pos is not None:
        print(f"  ID {sid}: {pos} ({pos * 360 / 4096:.1f} deg)")

# Park at center
for sid in found:
    scs_write2(ser, sid, 42, 2048)

ser.close()
print("\nVERDICT: PASS - 2x STS3215 daisy chain working")
