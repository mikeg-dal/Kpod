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

Author: [Your Name]
"""

import hid
import struct
import time
import rtmidi

# KPOD USB identifiers
VENDOR_ID = 0x04d8
PRODUCT_ID = 0xF12D
KPOD_USB_CMD_UPDATE = ord('u')  # Command to request status
REPORT_LEN = 8                  # Expected length of response packet

# Mapping for TAP buttons (front panel 1–8): flags from 0x41 to 0x48
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

# Mapping for HOLD buttons (same buttons pressed and held): flags from 0x51 to 0x58
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

# Knob turn mappings (CW = clockwise, CCW = counterclockwise)
ENCODER_CW_NOTE = 100
ENCODER_CCW_NOTE = 101

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
    """Main loop: read KPOD HID data and emit MIDI events."""
    try:
        dev = hid.Device(VENDOR_ID, PRODUCT_ID)
    except Exception as e:
        print(f"❌ Could not open KPOD: {e}")
        return

    dev.set_nonblocking = False
    print("✅ Connected to KPOD")

    last_flags = 0  # Used to detect changes (edge trigger)

    try:
        while True:
            # Send update request to KPOD
            pkt = bytes([KPOD_USB_CMD_UPDATE]) + bytes(7)
            dev.write(pkt)

            # Read back the response
            response = dev.read(REPORT_LEN)

            if response and len(response) == 8:
                ticks = struct.unpack("<h", bytes(response[1:3]))[0]  # Encoder ticks
                flags = response[3]  # Button + tap/hold + rocker state

                # --- Encoder Turned ---
                if ticks > 0:
                    for _ in range(ticks):
                        send_note(ENCODER_CW_NOTE)
                        print(f"↻ CW → Note {ENCODER_CW_NOTE}")
                elif ticks < 0:
                    for _ in range(abs(ticks)):
                        send_note(ENCODER_CCW_NOTE)
                        print(f"↺ CCW → Note {ENCODER_CCW_NOTE}")

                # --- Buttons ---
                if flags != last_flags:
                    if flags in TAP_NOTE_MAP:
                        note = TAP_NOTE_MAP[flags]
                        send_note(note)
                        print(f"🎯 TAP {note} (flags=0x{flags:02X})")
                    elif flags in HOLD_NOTE_MAP:
                        note = HOLD_NOTE_MAP[flags]
                        send_note(note)
                        print(f"🕹️ HOLD {note} (flags=0x{flags:02X})")

                    # 🚧 Future: Rocker switch decoding
                    # if flags & 0x10:  # LEFT rocker
                    #     ...
                    # if flags & 0x20:  # RIGHT rocker
                    #     ...

                last_flags = flags

            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\nExiting gracefully.")
    finally:
        dev.close()
        midi_out.close_port()

if __name__ == "__main__":
    main()%  
