"""
Serial communication module for Arduino stepper motor controller.
Handles sending commands to Arduino and receiving responses.
"""

import serial
import serial.tools.list_ports
import time
import threading


class ArduinoController:
    def __init__(self):
        self.ser = None
        self.is_connected = False
        self.port = None
        self.baudrate = 115200
        self.read_thread = None
        self.running = False
        self.response_callback = None
        # Flow-control counters and sync objects
        self._queue_lock = threading.Lock()
        self._queued_reports = 0
        self._dequeued_reports = 0
        self._queue_cond = threading.Condition(self._queue_lock)
        
    def list_ports(self):
        """Return a list of available serial ports"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def connect(self, port=None, baudrate=115200):
        """Connect to Arduino on specified port"""
        if self.is_connected:
            return True, "Already connected"
        
        try:
            # If no port specified, try to find Arduino
            if port is None:
                ports = serial.tools.list_ports.comports()
                for p in ports:
                    if 'Arduino' in p.description or 'CH340' in p.description or 'USB' in p.description:
                        port = p.device
                        break
                if port is None:
                    available = self.list_ports()
                    if available:
                        port = available[0]
                    else:
                        return False, "No serial ports found"
            
            self.port = port
            self.baudrate = baudrate
            self.ser = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset
            
            # Clear any startup messages
            self.ser.flushInput()
            
            self.is_connected = True
            
            # Start read thread
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            
            return True, f"Connected to {port}"
            
        except Exception as e:
            self.is_connected = False
            return False, f"Connection failed: {str(e)}"
    
    def disconnect(self):
        """Disconnect from Arduino"""
        if not self.is_connected:
            return
        
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=1)
        
        if self.ser:
            self.ser.close()
        
        self.is_connected = False
        self.ser = None
    
    def send_command(self, command):
        """Send a single command to Arduino"""
        if not self.is_connected:
            return False, "Not connected"
        
        try:
            # Add newline if not present
            if not command.endswith('\n'):
                command += '\n'
            
            self.ser.write(command.encode('utf-8'))
            self.ser.flush()
            return True, "Command sent"
            
        except Exception as e:
            return False, f"Send failed: {str(e)}"
    
    def send_script(self, script_lines):
        """
        Send multiple commands to Arduino.
        script_lines can be a list of strings or a single string with commands.
        """
        if not self.is_connected:
            return False, "Not connected"
        
        # Sliding-window stream: send up to `window` outstanding commands
        if isinstance(script_lines, str):
            raw_lines = [ln for ln in (l.strip() for l in script_lines.split('\n'))]
        else:
            raw_lines = [ln for ln in (l.strip() for l in script_lines)]
        lines = [ln for ln in raw_lines if ln and not ln.startswith('#')]

        window = 32  # number of outstanding commands to allow (safe for UNO)
        total = len(lines)
        idx = 0
        try:
            while idx < total:
                with self._queue_cond:
                    outstanding = self._queued_reports - self._dequeued_reports
                    if outstanding < window:
                        line = lines[idx]
                        success, msg = self.send_command(line)
                        if not success:
                            return False, msg
                        idx += 1
                        # give the firmware a moment to echo its queued message
                        self._queue_cond.wait(timeout=0.005)
                    else:
                        # wait until dequeues reduce outstanding
                        self._queue_cond.wait(timeout=1.0)

            return True, f"Sent {total} commands"
        except Exception as e:
            return False, f"Script send failed: {str(e)}"
    
    def emergency_stop(self):
        """Send emergency stop command"""
        if not self.is_connected:
            return False, "Not connected"
        
        try:
            self.ser.write(b'!')
            self.ser.flush()
            return True, "Emergency stop sent"
        except Exception as e:
            return False, f"Stop failed: {str(e)}"
    
    def set_response_callback(self, callback):
        """Set a callback function to receive Arduino responses"""
        self.response_callback = callback
    
    def _read_loop(self):
        """Background thread to read Arduino responses"""
        while self.running and self.is_connected:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        # Track queue occupancy messages for flow control
                        if line.startswith('[queued]'):
                            with self._queue_cond:
                                self._queued_reports += 1
                                self._queue_cond.notify_all()
                        elif line.startswith('[dequeued]'):
                            with self._queue_cond:
                                self._dequeued_reports += 1
                                self._queue_cond.notify_all()

                        if self.response_callback:
                            self.response_callback(line)
            except Exception as e:
                if self.running:  # Only report errors if we're supposed to be running
                    if self.response_callback:
                        self.response_callback(f"[ERROR] {str(e)}")
            time.sleep(0.01)
