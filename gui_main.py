#!/usr/bin/env python3

"""
KPOD to MIDI Bridge v2 - GUI Application
Enhanced with Tkinter GUI interface and proper rocker position detection
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import hid
import struct
import time
import rtmidi
import sys
import threading
import queue
from datetime import datetime

# KPOD USB identifiers
VENDOR_ID = 0x04d8
PRODUCT_ID = 0xF12D
KPOD_USB_CMD_UPDATE = ord('u')
REPORT_LEN = 8

# TAP buttons: flags 0x41–0x48
TAP_NOTE_MAP = {
    0x41: 64, 0x42: 65, 0x43: 66, 0x44: 67,
    0x45: 68, 0x46: 69, 0x47: 70, 0x48: 71,
}

# HOLD buttons: flags 0x51–0x58
HOLD_NOTE_MAP = {
    0x51: 72, 0x52: 73, 0x53: 74, 0x54: 75,
    0x55: 76, 0x56: 77, 0x57: 78, 0x58: 79,
}

# Rocker position change MIDI notes (unique button-like events)
ROCKER_POSITION_NOTES = {
    "VFO A": 110,      # Switch to VFO A mode
    "VFO B": 111,      # Switch to VFO B mode  
    "XIT/RIT": 112,    # Switch to XIT/RIT mode
}

# Encoder always sends the same notes regardless of rocker position
ENCODER_NOTES = {
    "CW": 100,         # Always clockwise = 100
    "CCW": 101,        # Always counter-clockwise = 101
}

class KPODBridgeGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KPOD to MIDI Bridge v2")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # State variables
        self.midi_out = None
        self.device = None
        self.current_rocker = "UNKNOWN"  # Track position: VFO A, VFO B, XIT/RIT, UNKNOWN
        self.running = False
        self.kpod_thread = None
        
        # Message queue for thread communication
        self.message_queue = queue.Queue()
        
        self.setup_gui()
        
        # Delay MIDI setup to ensure GUI is ready
        self.root.after(500, self.delayed_midi_setup)
        self.start_processing()
    
    def setup_gui(self):
        """Create the GUI interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="KPOD to MIDI Bridge v2", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Connection Status Section
        status_frame = ttk.LabelFrame(main_frame, text="Connection Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(1, weight=1)
        
        # KPOD Status
        ttk.Label(status_frame, text="KPOD:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.kpod_status = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.kpod_status.grid(row=0, column=1, sticky=tk.W)
        
        # MIDI Status  
        ttk.Label(status_frame, text="MIDI:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.midi_status = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.midi_status.grid(row=1, column=1, sticky=tk.W)
        
        # Current State Section
        state_frame = ttk.LabelFrame(main_frame, text="Current State", padding="10")
        state_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        state_frame.columnconfigure(1, weight=1)
        
        # Rocker Position
        ttk.Label(state_frame, text="Rocker Position:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.rocker_label = ttk.Label(state_frame, text="Unknown (move rocker to detect)")
        self.rocker_label.grid(row=0, column=1, sticky=tk.W)
        
        # Last Action
        ttk.Label(state_frame, text="Last Action:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.last_action = ttk.Label(state_frame, text="None")
        self.last_action.grid(row=1, column=1, sticky=tk.W)
        
        # Activity Log
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Log text area with scrollbar
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_kpod)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_kpod, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_button = ttk.Button(button_frame, text="Clear Log", command=self.clear_log)
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Quit", command=self.on_closing).pack(side=tk.RIGHT)
    
    def log_message(self, message, level="INFO"):
        """Add a message to the log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        self.message_queue.put(("LOG", log_entry))
    
    def update_status(self, component, status, color="black"):
        """Update connection status."""
        self.message_queue.put(("STATUS", component, status, color))
    
    def update_last_action(self, action):
        """Update last action display."""
        self.message_queue.put(("ACTION", action))
    
    def setup_midi(self):
        """Initialize MIDI output connection."""
        try:
            # Ensure we're on the main thread for MIDI initialization
            if threading.current_thread() != threading.main_thread():
                self.log_message("MIDI setup must be on main thread", "ERROR")
                return False
            
            self.midi_out = rtmidi.MidiOut()
            
            # Small delay to ensure MIDI system is ready
            time.sleep(0.1)
            
            ports = self.midi_out.get_ports()
            self.log_message(f"Available MIDI ports: {ports}")
            
            iac_port_index = next((i for i, p in enumerate(ports) if "IAC" in p), None)
            
            if iac_port_index is None:
                self.log_message("IAC Driver not found. Please enable it in Audio MIDI Setup.", "ERROR")
                self.update_status("MIDI", "IAC Driver not found", "red")
                return False
            
            self.midi_out.open_port(iac_port_index)
            port_name = ports[iac_port_index]
            self.log_message(f"Connected to MIDI: {port_name}")
            self.update_status("MIDI", f"Connected: {port_name}", "green")
            return True
            
        except Exception as e:
            self.log_message(f"MIDI setup failed: {e}", "ERROR")
            self.update_status("MIDI", f"Error: {e}", "red")
            # Clean up on error
            if hasattr(self, 'midi_out') and self.midi_out:
                try:
                    self.midi_out.close_port()
                except:
                    pass
                self.midi_out = None
            return False
    
    def send_kpod_command(self, cmd_char, data=None):
        """Send a command to KPOD and read response."""
        if not self.device:
            return None
            
        try:
            if data is None:
                data = [0] * 7
            
            # Ensure data is exactly 7 bytes
            cmd_data = data[:7] + [0] * (7 - len(data))
            
            # Create command packet
            pkt = bytes([ord(cmd_char)] + cmd_data)
            self.device.write(pkt)
            
            # Read response
            response = self.device.read(REPORT_LEN)
            return response
        except Exception as e:
            self.log_message(f"Command '{cmd_char}' failed: {e}", "ERROR")
            return None
    
    def detect_rocker_position_from_event(self, controls, has_activity):
        """
        Detect rocker position from event data.
        Returns new position string or None if no change.
        """
        new_position = None
        
        # Extract rocker bits according to API spec
        rocker_bits = (controls >> 5) & 0x03
        
        if rocker_bits == 0b10:  # Left rocker (VFO A)
            new_position = "VFO A"
        elif rocker_bits == 0b01:  # Right rocker (XIT/RIT)
            new_position = "XIT/RIT"
        elif controls == 0x00 and has_activity:
            # Controls = 0x00 with encoder/button activity = VFO B (center)
            new_position = "VFO B"
        elif controls == 0x00 and self.current_rocker not in ["VFO B", "UNKNOWN"]:
            # Transition to center from A or XIT/RIT
            new_position = "VFO B"
        
        return new_position
    
    def send_rocker_position_change(self, new_position):
        """Send MIDI note for rocker position change."""
        if new_position in ROCKER_POSITION_NOTES:
            note = ROCKER_POSITION_NOTES[new_position]
            self.send_note(note)
            action = f"Rocker → {new_position} (MIDI Note {note})"
            self.log_message(action)
            self.update_last_action(action)
            return True
        return False
    
    def get_device_info(self):
        """Get KPOD device ID and firmware version."""
        try:
            # Get Device ID
            id_response = self.send_kpod_command('=')
            if id_response and len(id_response) >= 8:
                id_string = ''.join(chr(b) for b in id_response[1:8] if b != 0)
                self.log_message(f"Device ID: {id_string}")
            
            # Get Firmware Version  
            ver_response = self.send_kpod_command('v')
            if ver_response and len(ver_response) >= 3:
                version_bcd = struct.unpack("<h", bytes(ver_response[1:3]))[0]
                # Convert BCD to version string (e.g., 108 -> "1.08")
                major = version_bcd // 100
                minor = version_bcd % 100
                version_str = f"{major}.{minor:02d}"
                self.log_message(f"Firmware Version: {version_str}")
            
        except Exception as e:
            self.log_message(f"Failed to get device info: {e}", "ERROR")
    
    def setup_hid(self):
        """Initialize HID device connection and get device info."""
        try:
            self.device = hid.Device(VENDOR_ID, PRODUCT_ID)
            self.device.nonblocking = False
            self.log_message("Connected to KPOD")
            self.update_status("KPOD", "Connected", "green")
            
            # Get device information
            self.get_device_info()
            
            return True
        except Exception as e:
            self.log_message(f"Could not open KPOD: {e}", "ERROR")
            self.update_status("KPOD", f"Error: {e}", "red")
            return False
    
    def delayed_midi_setup(self):
        """Setup MIDI after GUI is fully initialized."""
        self.setup_midi()
    
    def update_rocker_display(self, position):
        """Update rocker position display."""
        display_names = {
            "VFO A": "VFO A (Left)",
            "VFO B": "VFO B (Center)",
            "XIT/RIT": "XIT/RIT (Right)",
            "UNKNOWN": "Unknown (move rocker to detect)"
        }
        display_name = display_names.get(position, position)
        self.message_queue.put(("ROCKER", display_name))
    
    def send_note(self, note, velocity=127):
        """Send MIDI Note On followed by Note Off."""
        try:
            if self.midi_out:
                self.midi_out.send_message([0x90, note, velocity])
                self.midi_out.send_message([0x80, note, 0])
        except Exception as e:
            self.log_message(f"MIDI send error: {e}", "ERROR")
    
    def get_encoder_notes(self):
        """Get encoder MIDI notes based on rocker position."""
        if self.current_rocker == "XIT/RIT":
            # XIT/RIT mode uses different encoder notes
            return (102, 103)  # CW=102, CCW=103
        else:
            # VFO A and VFO B both use standard encoder notes
            return (ENCODER_NOTES["CW"], ENCODER_NOTES["CCW"])  # CW=100, CCW=101
    
    def kpod_worker(self):
        """Worker thread for KPOD communication."""
        if not self.setup_hid():
            return
        
        self.log_message("KPOD monitoring started")
        
        try:
            while self.running:
                # Send update request to KPOD using event-based approach
                response = self.send_kpod_command('u')
                
                if response and len(response) == 8:
                    cmd_reply = response[0]
                    ticks = struct.unpack("<h", bytes(response[1:3]))[0]
                    controls = response[3]
                    
                    # Only process if there's a new event
                    if cmd_reply == ord('u'):
                        has_activity = ticks != 0 or (controls & 0x0F) != 0
                        
                        # Detect rocker position changes
                        new_position = self.detect_rocker_position_from_event(controls, has_activity)
                        if new_position and new_position != self.current_rocker:
                            # Send MIDI note for rocker position change
                            self.send_rocker_position_change(new_position)
                            self.current_rocker = new_position
                            self.update_rocker_display(new_position)
                        
                        # Handle encoder - position-dependent notes
                        # VFO A/B: 100/101, XIT/RIT: 102/103
                        cw_note, ccw_note = self.get_encoder_notes()
                        
                        if ticks > 0:
                            for _ in range(ticks):
                                self.send_note(cw_note)
                                action = f"Encoder CW → Note {cw_note} (at {self.current_rocker})"
                                self.log_message(action)
                                self.update_last_action(action)
                        elif ticks < 0:
                            for _ in range(abs(ticks)):
                                self.send_note(ccw_note)
                                action = f"Encoder CCW → Note {ccw_note} (at {self.current_rocker})"
                                self.log_message(action)
                                self.update_last_action(action)
                        
                        # Handle buttons (using corrected bit mapping)
                        button_bits = controls & 0x0F
                        if button_bits != 0:
                            tap_hold = "HOLD" if (controls & 0x10) else "TAP"
                            
                            # Find which button was pressed
                            for i in range(8):  # Buttons 1-8
                                if button_bits & (1 << i):
                                    button_num = i + 1
                                    
                                    # Use correct note mapping
                                    if tap_hold == "TAP" and (0x40 | button_bits) in TAP_NOTE_MAP:
                                        note = TAP_NOTE_MAP[0x40 | button_bits]
                                    elif tap_hold == "HOLD" and (0x50 | button_bits) in HOLD_NOTE_MAP:
                                        note = HOLD_NOTE_MAP[0x50 | button_bits]
                                    else:
                                        # Fallback mapping
                                        base_note = 64 if tap_hold == "TAP" else 72
                                        note = base_note + i
                                    
                                    self.send_note(note)
                                    action = f"{tap_hold} Button {button_num} → Note {note}"
                                    self.log_message(action)
                                    self.update_last_action(action)
                                    break
                
                time.sleep(0.01)  # Faster polling for better responsiveness
        
        except Exception as e:
            self.log_message(f"KPOD worker error: {e}", "ERROR")
        finally:
            self.cleanup_hid()
            self.log_message("KPOD monitoring stopped")
    
    def start_kpod(self):
        """Start KPOD monitoring."""
        if not self.running:
            self.running = True
            self.kpod_thread = threading.Thread(target=self.kpod_worker, daemon=True)
            self.kpod_thread.start()
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.log_message("Starting KPOD monitoring...")
    
    def stop_kpod(self):
        """Stop KPOD monitoring."""
        if self.running:
            self.running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.update_status("KPOD", "Disconnected", "red")
            self.log_message("Stopping KPOD monitoring...")
    
    def clear_log(self):
        """Clear the activity log."""
        self.log_text.delete(1.0, tk.END)
    
    def cleanup_hid(self):
        """Clean up HID resources."""
        if self.device:
            try:
                self.device.close()
                self.device = None
            except:
                pass
    
    def cleanup_midi(self):
        """Clean up MIDI resources."""
        if self.midi_out:
            try:
                self.midi_out.close_port()
                self.midi_out = None
            except:
                pass
    
    def process_messages(self):
        """Process messages from the worker thread."""
        try:
            while True:
                message = self.message_queue.get_nowait()
                msg_type = message[0]
                
                if msg_type == "LOG":
                    # Add to log text
                    self.log_text.insert(tk.END, message[1])
                    self.log_text.see(tk.END)
                
                elif msg_type == "STATUS":
                    # Update status labels
                    component, status, color = message[1], message[2], message[3]
                    if component == "KPOD":
                        self.kpod_status.config(text=status, foreground=color)
                    elif component == "MIDI":
                        self.midi_status.config(text=status, foreground=color)
                
                elif msg_type == "ROCKER":
                    # Update rocker position
                    self.rocker_label.config(text=message[1])
                
                elif msg_type == "ACTION":
                    # Update last action
                    self.last_action.config(text=message[1])
                
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_messages)
    
    def start_processing(self):
        """Start the message processing loop."""
        self.process_messages()
    
    def on_closing(self):
        """Handle window closing."""
        self.running = False
        if self.kpod_thread and self.kpod_thread.is_alive():
            self.kpod_thread.join(timeout=1)
        self.cleanup_hid()
        self.cleanup_midi()
        self.root.destroy()
    
    def run(self):
        """Start the GUI application."""
        self.log_message("KPOD to MIDI Bridge v2 started")
        self.log_message("Click 'Start' to begin monitoring KPOD")
        self.root.mainloop()

def main():
    """Entry point for the GUI application."""
    app = KPODBridgeGUI()
    app.run()

if __name__ == "__main__":
    main()