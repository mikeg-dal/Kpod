#!/usr/bin/env python3

"""
KPOD to MIDI Bridge Script for macOS
------------------------------------
This script interfaces with the Elecraft KPOD USB device, reads encoder and button input,
and sends MIDI Note messages to an IAC (Inter-Application Communication) virtual MIDI port.

Tested on macOS with:
  - KPOD USB (Vendor ID: 0x04d8, Product ID: 0xF12D)
  - IAC Driver enabled in Audio MIDI Setup

Dependencies:
  pip install hidapi python-rtmidi

Requires:
  - IAC Driver to be enabled and at least one port created
  - macOS MIDI setup to route MIDI data to a listening application

Author: Mike Garcia
"""

import hid
import struct
import time
import rtmidi

# KPOD USB identifiers
VENDOR_ID = 0x04d8
PRODUCT_ID = 0xF12D
KPOD_USB_CMD_UPDATE = ord('u')
REPORT_LEN = 8

# TAP buttons: flags 0x41–0x48
TAP_NOTE_MAP = {
    0x41: 64,
    0x42: 65,
    0x43: 66,
    0x44: 67,
    0x45: 68,
    0x46: 69,
    0x47: 70,
    0x48: 71,
}

# HOLD buttons: flags 0x51–0x58
HOLD_NOTE_MAP = {
    0x51: 72,
    0x52: 73,
    0x53: 74,
    0x54: 75,
    0x55: 76,
    0x56: 77,
    0x57: 78,
    0x58: 79,
}

# Encoder tick MIDI note mapping by rocker position
ROCKER_NOTE_MAP = {
    0x40: (100, 101),  # VFO A (Left)
    0x00: (102, 103),  # VFO B (Center)
    0x20: (104, 105),  # XIT/RIT (Right)
}

# Open MIDI output to IAC Driver
midi_out = rtmidi.MidiOut()
ports = midi_out.get_ports()
iac_port_index = next((i for i, p in enumerate(ports) if "IAC" in p), None)

if iac_port_index is None:
    print("❌ IAC Driver not found. Please enable it in Audio MIDI Setup.")
    exit(1)

midi_out.open_port(iac_port_index)
print(f"✅ Connected to IAC: {ports[iac_port_index]}")

def send_note(note, velocity=127):
    """Send MIDI Note On followed by Note Off."""
    midi_out.send_message([0x90, note, velocity])
    midi_out.send_message([0x80, note, 0])

def main():
    try:
        dev = hid.Device(VENDOR_ID, PRODUCT_ID)
    except Exception as e:
        print(f"❌ Could not open KPOD: {e}")
        return

    dev.nonblocking = False
    print("✅ Connected to KPOD")

    current_rocker = 0x00  # Default: Center
    last_flags = 0

    try:
        while True:
            pkt = bytes([KPOD_USB_CMD_UPDATE]) + bytes(7)
            dev.write(pkt)
            response = dev.read(REPORT_LEN)

            if response and len(response) == 8:
                ticks = struct.unpack("<h", bytes(response[1:3]))[0]
                flags = response[3]

                # Rocker detection (stateful)
                if flags & 0x40:
                    current_rocker = 0x40  # VFO A
                elif flags & 0x20:
                    current_rocker = 0x20  # XIT/RIT
                elif current_rocker in (0x40, 0x20):
                    current_rocker = 0x00  # Inferred Center

                # Get MIDI notes based on rocker position
                cw_note, ccw_note = ROCKER_NOTE_MAP.get(current_rocker, (102, 103))

                # Send MIDI notes based on encoder direction
                if ticks > 0:
                    for _ in range(ticks):
                        send_note(cw_note)
                        print(f"↻ CW → Note {cw_note} (Rocker: 0x{current_rocker:02X})")
                elif ticks < 0:
                    for _ in range(abs(ticks)):
                        send_note(ccw_note)
                        print(f"↺ CCW → Note {ccw_note} (Rocker: 0x{current_rocker:02X})")

                # TAP and HOLD detection
                if flags != last_flags:
                    if flags in TAP_NOTE_MAP:
                        note = TAP_NOTE_MAP[flags]
                        send_note(note)
                        print(f"🎯 TAP {note} (flags=0x{flags:02X})")
                    elif flags in HOLD_NOTE_MAP:
                        note = HOLD_NOTE_MAP[flags]
                        send_note(note)
                        print(f"🕹️ HOLD {note} (flags=0x{flags:02X})")

                    last_flags = flags

            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\nExiting gracefully.")
    finally:
        dev.close()
        midi_out.close_port()

if __name__ == "__main__":
    main()
