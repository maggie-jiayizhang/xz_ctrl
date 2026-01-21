"""
Motor Script Validator
Helper functions to validate motor control commands
"""

import re
from typing import List, Tuple, Optional


class ValidationError:
    """Represents a validation error"""
    def __init__(self, line_num: int, message: str):
        self.line_num = line_num
        self.message = message
    
    def __repr__(self):
        return f"Line {self.line_num}: {self.message}"


def validate_move_command(parts: List[str], line_num: int) -> Optional[ValidationError]:
    """
    Validate move command: move x|z <distance>
    Distance must be a number with at most 2 decimal places (e.g., 1.55 ok, 1.555 not ok)
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 3:
        return ValidationError(line_num, f"move requires 2 parameters (axis, distance), got {len(parts)-1}")
    axis = parts[1].lower()
    if axis not in ['x', 'z']:
        return ValidationError(line_num, f"Invalid axis '{parts[1]}', must be 'x' or 'z'")
    try:
        distance = float(parts[2])
        # Check for at most 2 decimal places
        distance_str = parts[2].lstrip('-+')
        if '.' in distance_str:
            decimal_part = distance_str.split('.')[1]
            if len(decimal_part) > 2:
                return ValidationError(line_num, f"Distance '{parts[2]}' has too many decimal places (max 2 allowed, e.g., 1.55)")
    except ValueError:
        return ValidationError(line_num, f"Invalid distance '{parts[2]}', must be a number")
    return None


def validate_speed_command(parts: List[str], line_num: int) -> Optional[ValidationError]:
    """
    Validate speed command: speed x|z <speed>
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 3:
        return ValidationError(line_num, f"speed requires 2 parameters (axis, speed), got {len(parts)-1}")
    axis = parts[1].lower()
    if axis not in ['x', 'z']:
        return ValidationError(line_num, f"Invalid axis '{parts[1]}', must be 'x' or 'z'")
    try:
        speed = float(parts[2])
    except ValueError:
        return ValidationError(line_num, f"Invalid speed '{parts[2]}', must be a number")
    if speed <= 0:
        return ValidationError(line_num, f"Speed must be positive, got {speed}")
    return None


def validate_loop_command(parts: List[str], line_num: int) -> Optional[ValidationError]:
    """
    Validate loop command: loop iterations
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 2:
        return ValidationError(line_num, f"loop requires 1 parameter (iterations), got {len(parts)-1}")
    
    try:
        iterations = int(parts[1])
    except ValueError:
        return ValidationError(line_num, f"Invalid iterations '{parts[1]}', must be an integer")
    
    if iterations <= 0:
        return ValidationError(line_num, f"Iterations must be positive, got {iterations}")
    
    return None


def validate_endloop_command(parts: List[str], line_num: int) -> Optional[ValidationError]:
    """
    Validate endloop command: endloop
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 1:
        return ValidationError(line_num, f"endloop takes no parameters, got {len(parts)-1}")
    
    return None


def validate_pulse_command(parts: List[str], line_num: int) -> Optional[ValidationError]:
    """
    Validate pulse command: pulse milliseconds
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 2:
        return ValidationError(line_num, f"pulse requires 1 parameter (milliseconds), got {len(parts)-1}")
    
    try:
        milliseconds = int(parts[1])
    except ValueError:
        return ValidationError(line_num, f"Invalid milliseconds '{parts[1]}', must be an integer")
    
    if milliseconds < 0:
        return ValidationError(line_num, f"Pulse time cannot be negative, got {milliseconds}")
    
    if milliseconds > 5000:
        return ValidationError(line_num, f"Pulse time too long (max 5000ms), got {milliseconds}")
    
    return None


def validate_wait_command(parts: List[str], line_num: int) -> Optional[ValidationError]:
    """
    Validate wait command: wait milliseconds
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 2:
        return ValidationError(line_num, f"wait requires 1 parameter (milliseconds), got {len(parts)-1}")
    
    try:
        milliseconds = int(parts[1])
    except ValueError:
        return ValidationError(line_num, f"Invalid milliseconds '{parts[1]}', must be an integer")
    
    if milliseconds < 0:
        return ValidationError(line_num, f"Wait time cannot be negative, got {milliseconds}")
    
    return None


def validate_line(line: str, line_num: int) -> Optional[ValidationError]:
    """
    Validate a single line of script
    Returns ValidationError if invalid, None if valid or comment/empty
    """
    line = line.strip()
    # Skip empty lines and comments
    if not line or line.startswith('#'):
        return None
    parts = line.split()
    if not parts:
        return None
    cmd = parts[0].lower()
    # Validate based on command type
    if cmd == 'move':
        return validate_move_command(parts, line_num)
    elif cmd == 'speed':
        return validate_speed_command(parts, line_num)
    elif cmd == 'loop':
        return validate_loop_command(parts, line_num)
    elif cmd == 'endloop':
        return validate_endloop_command(parts, line_num)
    elif cmd == 'wait':
        return validate_wait_command(parts, line_num)
    elif cmd == 'pulse':
        return validate_pulse_command(parts, line_num)
    elif cmd == 'zero':
        # zero z
        if len(parts) != 2:
            return ValidationError(line_num, f"zero requires 1 parameter (axis), got {len(parts)-1}")
        if parts[1].lower() != 'z':
            return ValidationError(line_num, "zero currently only supports axis 'z'")
        return None
    else:
        return ValidationError(line_num, f"Unknown command '{cmd}'")


def validate_loop_matching(lines: List[str]) -> List[ValidationError]:
    """
    Check that all loops have matching endloop statements
    Returns list of ValidationErrors for mismatched loops
    """
    errors = []
    loop_stack = []  # Stack of (line_num, indentation_level)
    
    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()
        
        if not stripped or stripped.startswith('#'):
            continue
        
        parts = stripped.split()
        if not parts:
            continue
        
        cmd = parts[0].lower()
        
        if cmd == 'loop':
            loop_stack.append(line_num)
        elif cmd == 'endloop':
            if not loop_stack:
                errors.append(ValidationError(line_num, "endloop without matching loop"))
            else:
                loop_stack.pop()
    
    # Check for unclosed loops
    for loop_line in loop_stack:
        errors.append(ValidationError(loop_line, "loop without matching endloop"))
    
    return errors


def validate_script(text: str) -> List[ValidationError]:
    """
    Validate entire script
    Returns list of all ValidationErrors found
    """
    errors = []
    lines = text.split('\n')
    
    # First pass: per-line validation
    for line_num, line in enumerate(lines, start=1):
        err = validate_line(line, line_num)
        if err:
            errors.append(err)
    
    # Validate loop matching
    loop_errors = validate_loop_matching(lines)
    errors.extend(loop_errors)

    # Note: Z soft-limit checking is now handled by the GUI's _check_z_soft_limit()
    # which maintains stateful position tracking across script runs.
    # The validator only checks syntax, not runtime position constraints.
    
    # Sort errors by line number
    errors.sort(key=lambda e: e.line_num)
    
    return errors


def get_error_summary(errors: List[ValidationError]) -> str:
    """
    Format errors into a readable summary
    """
    if not errors:
        return "✓ No errors found - script is valid!"
    
    lines = [f"✗ Found {len(errors)} error(s):"]
    for error in errors:
        lines.append(f"  {error}")
    return "\n".join(lines)
