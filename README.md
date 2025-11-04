# Robot Controller - Arduino Stepper Motor Control with Python GUI

A complete system for controlling X/Z stepper motors via Arduino using a Python GUI with real-time scripting, syntax highlighting, and serial communication.

## Features

### Python GUI (`src/app.py`)
- **Script Editor** with syntax highlighting for commands (move, speed, wait, loop/endloop)
- **Line numbers** for easy reference
- **Loop expansion** - write `loop N ... endloop` and it expands automatically before sending
- **Script validation** - checks syntax before sending to Arduino
- **Save/Load** scripts for reuse (Ctrl+S / Ctrl+O)
- **Real-time console** - monitor Arduino responses
- **Keyboard shortcuts** - hold Ctrl to see shortcuts on buttons
  - Ctrl+C: Connect
  - Ctrl+R: Send (Run)
  - Ctrl+E: Emergency Stop
  - Ctrl+S: Save
  - Ctrl+O: Load (Open)
  - Ctrl+L: Clear console

### Arduino Firmware (`src/interaction.ino`)
- **Command queue** (128 commands) for smooth execution
- **Real-time parsing** - accepts commands as stream
- **Emergency stop** - immediate halt with `stop` or `!`
- **Auto power-down** - disables stepper drivers when idle to keep motors cool
- Supports commands:
  - `move x|z D` - move axis by D mm
  - `speed x|z S` - set speed to S mm/s  
  - `wait T` - wait T milliseconds
  - `stop` or `!` - emergency stop

## Hardware Setup

### Wiring (CNC Shield V3 defaults)
- **X-axis stepper**: STEP=2, DIR=5
- **Z-axis stepper**: STEP=4, DIR=7
- **Enable pin**: 8 (shared, LOW=enabled)
- **Microstepping**: 1/32 configured (adjust in firmware)

### Calibration
Edit in `src/interaction.ino`:
```cpp
const float BASE_STEPS_PER_MM = 20.0f;  // Adjust for your mechanics
#define MICROSTEP_X 32
#define MICROSTEP_Z 32
```

## Quick Start

### 1. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Upload Arduino Firmware
1. Open `src/interaction.ino` in Arduino IDE
2. Install **AccelStepper** library (Tools → Manage Libraries → search "AccelStepper")
3. Select board and COM port
4. Upload

### 3. Run the GUI
```powershell
python src\app.py
```

### 4. Use the Application
1. Click **Connect** (or Ctrl+C) and select your Arduino's COM port
2. Edit the script in the editor (example provided)
3. Click **Send to Arduino** (or Ctrl+R) to validate and execute
4. Monitor the console for real-time feedback
5. Use **STOP** (or Ctrl+E) for emergency halt

## Example Script

```python
# Set speeds for both axes
speed x 5.0
speed z 5.0

# Initial positioning
move x 10
wait 500
move z -5

# Oscillate X axis 3 times
loop 3
  move x 10
  wait 200
  move x -10
endloop
```

## Command Reference

| Command | Format | Example | Description |
|---------|--------|---------|-------------|
| `move` | `move <axis> <distance>` | `move x 100` | Move axis by distance (mm) |
| `speed` | `speed <axis> <value>` | `speed z 3.5` | Set axis speed (mm/s) |
| `wait` | `wait <time>` | `wait 1000` | Pause for milliseconds |
| `loop` | `loop <count>` | `loop 5` | Start loop block |
| `endloop` | `endloop` | `endloop` | End loop block |
| `#` | `# comment` | `# This is a comment` | Comment line |

### Notes
- Loops can be nested
- Loops are expanded in the GUI before sending to Arduino
- Distance values can be negative for reverse direction
- Speed must be positive (>0)

## Project Structure

```
robot_controller/
├── src/
│   ├── app.py              # Python GUI application
│   ├── serial_comm.py      # Arduino serial communication
│   ├── validator.py        # Script validation
│   ├── script_parser.py    # Script parsing utilities
│   ├── make_script_util.py # Script generation helpers
│   └── interaction.ino     # Arduino firmware (CURRENT)
├── arduino/
│   └── stepper_controller/ # Alternative firmware (oscillation-based)
├── gui_script/             # Example scripts
├── requirements.txt        # Python dependencies
└── README.md

```

## Queue Capacity

The Arduino firmware has a command queue set to **128 commands** (adjustable in firmware):

```cpp
#define QUEUE_CAP 128  // Increase if you need longer scripts
```

If you see `[queue] full (QUEUE_CAP=128)` in the console, either:
- Reduce script length
- Increase `QUEUE_CAP` in `src/interaction.ino` and re-upload

## Safety Notes

⚠️ **Important:**
- Ensure proper power supply and current limits for your stepper drivers
- No limit switches implemented - add your own safety limits
- Emergency stop (Ctrl+E or `!`) provides immediate halt
- GUI automatically sends stop signal when closing (if connected)
- Motors are powered down when idle to prevent overheating

## Troubleshooting

**Motors not moving?**
- Verify correct firmware uploaded (`src/interaction.ino`, not `arduino/stepper_controller`)
- Check wiring and power supply
- Ensure microstepping settings match your driver configuration

**Queue full errors?**
- Reduce loop counts or script length
- Increase `QUEUE_CAP` in firmware and re-upload

**Connection issues?**
- Check COM port in Device Manager
- Ensure no other software is using the serial port
- Verify baud rate is 115200

## License

MIT
