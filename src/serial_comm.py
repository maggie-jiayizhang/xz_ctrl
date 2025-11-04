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
        
        # Convert to list if string
        if isinstance(script_lines, str):
            script_lines = [line.strip() for line in script_lines.split('\n') if line.strip()]
        
        try:
            for line in script_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Send command
                success, msg = self.send_command(line)
                if not success:
                    return False, msg
                
                # Small delay between commands to avoid overwhelming the Arduino
                time.sleep(0.01)
            
            return True, f"Sent {len(script_lines)} commands"
            
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
                    if line and self.response_callback:
                        self.response_callback(line)
            except Exception as e:
                if self.running:  # Only report errors if we're supposed to be running
                    if self.response_callback:
                        self.response_callback(f"[ERROR] {str(e)}")
            time.sleep(0.01)
