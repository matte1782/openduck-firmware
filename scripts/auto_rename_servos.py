#!/usr/bin/env python3
"""Auto-detect and rename STS3215 servos.
Polls for ID 1, renames to next available ID."""
import serial
import time
import sys

def scs_checksum(p):
    return (~sum(p)) & 0xFF

def scs_write1(ser, sid, addr, val):
    packet = [sid, 4, 3, addr, val]
    cs = scs_checksum(packet)
    ser.write(bytes([0xFF, 0xFF] + packet + [cs]))
    time.sleep(0.01)
    return ser.read(20)

def scs_ping(ser, sid):
    packet = [sid, 2, 1]
    cs = scs_checksum(packet)
    ser.write(bytes([0xFF, 0xFF] + packet + [cs]))
    time.sleep(0.01)
    return len(ser.read(20)) > 0

ser = serial.Serial('/dev/ttyUSB0', 1000000, timeout=0.1)
next_id = 7  # start from 7, we already have 2-6

print(f"=== Auto Servo Renamer ===")
print(f"Polling for new servos at ID 1...")
print(f"Next ID to assign: {next_id}")
print(f"Press Ctrl+C to stop")
print()

try:
    while next_id <= 17:
        if scs_ping(ser, 1):
            print(f"[FOUND] Servo at ID 1 -> Renaming to ID {next_id}...")
            scs_write1(ser, 1, 55, 0)
            time.sleep(0.1)
            scs_write1(ser, 1, 5, next_id)
            time.sleep(0.1)
            scs_write1(ser, next_id, 55, 1)
            time.sleep(0.1)

            if scs_ping(ser, next_id):
                print(f"[OK] ID {next_id} confirmed!")
            else:
                print(f"[ERROR] ID {next_id} not responding!")

            # Quick verify all
            count = 0
            for sid in range(2, next_id + 1):
                if scs_ping(ser, sid):
                    count += 1
            print(f"[STATUS] {count} servos on bus (IDs 2-{next_id})")
            print(f"[WAITING] Plug in next servo... (will become ID {next_id + 1})")
            print()
            next_id += 1
        time.sleep(2)
except KeyboardInterrupt:
    print("\nStopped.")

# Final count
print("\n=== Final Status ===")
total = 0
for sid in range(2, next_id):
    ok = scs_ping(ser, sid)
    status = "OK" if ok else "FAIL"
    print(f"  ID {sid}: {status}")
    if ok:
        total += 1
print(f"\nTotal servos configured: {total}")
ser.close()
