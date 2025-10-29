# Robot Controller (X/Z Steppers)

This project provides:
- A minimal Python GUI to upload and run simple stepper "programs" on an Arduino.
- An Arduino sketch that controls two stepper motors (X and Z axes) via step/dir drivers (e.g., A4988/DRV8825) and interprets a tiny program protocol.

## Features
- Program-based control: define oscillation blocks per axis with repeats
- Loop whole program or run once
- Configurable steps-per-unit (to write programs in human units)
- Connect/disconnect to a COM port with basic logs
- Arduino connectivity and status check (PING/STATUS) directly from the GUI

## Wiring assumptions
- Two step/dir drivers (A4988/DRV8825 or similar)
- Default pins (can be edited in the Arduino sketch):
  - X: STEP=2, DIR=5
  - Z: STEP=3, DIR=6
- Shared EN pin optional (set to -1 to disable)
- No limit switches by default (homing not implemented). Add safety as needed.

## Program protocol (ASCII lines)
- One command per line, newline-terminated (\n)
- Upload sequence:
  - `PROG BEGIN`
  - One or more block lines:
    - `OSCIL <axis> <neg_steps> <pos_steps> SPD <steps_per_s> REP <n>`
      - axis: X or Z
      - neg_steps: negative integer for the first half move (e.g., left/down)
      - pos_steps: positive integer for the second half move (e.g., right/up)
      - REP n: number of oscillation cycles; -1 for infinite
    - Alternatively in units from the GUI editor (converted client-side):
      - `OSCIL X LENL <units> LENR <units> SPD_U <units_per_s> REP <n>`
  - `PROG END LOOP` or `PROG END ONCE`
  - `RUN`
- Other:
  - `PING` → `PONG`
  - `STOP` → attempt to stop gracefully
  - Firmware responses: `OK`, `DONE`, `STOPPED`, `ERR <message>`, `READY`

## Calibrating steps per unit
Update `steps_per_unit_x` and `steps_per_unit_z` in `arduino/stepper_controller/stepper_controller.ino` or in the Python GUI settings field.
- For lead screw-driven Z: steps_per_rev * microsteps / lead
- For belt-driven X: steps_per_rev * microsteps / (pulley_circumference)

## Quick start (Windows, PowerShell)

1) Install Python deps:

```powershell
pip install -r requirements.txt
```

2) Upload Arduino sketch:
- Open `arduino/stepper_controller/stepper_controller.ino` in Arduino IDE
- Install the AccelStepper library (Library Manager → search "AccelStepper" by Mike McCauley)
- Select correct board and COM port, then Upload

3) Run the GUI:

```powershell
python src/app.py
```

4) Use the GUI:
- Click "Check Arduino" to verify your board is connected. The status indicator will show RUNNING/READY/IDLE.
- Write a simple program in the editor (move/loop/wait commands) and use the buttons to validate and make a CSV for serial.

### Arduino status check

- The GUI sends PING (expects PONG) and queries STATUS; firmware replies with one of:
  - `STATUS RUNNING` (a program is executing)
  - `STATUS READY` (a program is loaded but not running)
  - `STATUS IDLE` (no program is loaded)


Example program:

```
# X: left 100 steps, right 80 steps at 400 steps/s, repeat 300 cycles
OSCIL X -100 80 SPD 400 REP 300

# Z: up/down by units (converted using Z steps/unit), 5 units/s, run forever
OSCIL Z LENL 50 LENR 30 SPD_U 5 REP -1
```

## Notes
- Ensure your power supply and current limits are set correctly for your motors/drivers.
- Consider adding limit switches and homing for safety.
- For infinite block repeats (REP -1) the program will continue until you press "Stop".
- If you see `ERR` responses, check wiring, COM settings, and that the Arduino is running the provided firmware.

## License
MIT
