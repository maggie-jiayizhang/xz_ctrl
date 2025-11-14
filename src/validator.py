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
    Distance must be a number with at most 1 decimal place (e.g., 1.5 ok, 1.55 not ok)
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 3:
        return ValidationError(line_num, f"move requires 2 parameters (axis, distance), got {len(parts)-1}")
    axis = parts[1].lower()
    if axis not in ['x', 'z']:
        return ValidationError(line_num, f"Invalid axis '{parts[1]}', must be 'x' or 'z'")
    try:
        distance = float(parts[2])
        # Check for at most 1 decimal place
        distance_str = parts[2].lstrip('-+')
        if '.' in distance_str:
            decimal_part = distance_str.split('.')[1]
            if len(decimal_part) > 1:
                return ValidationError(line_num, f"Distance '{parts[2]}' has too many decimal places (max 1 allowed, e.g., 1.5)")
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

    # Second pass: simulate Z soft-limit (<=2.0 allowed, >2.0 forbidden) with zero z resetting baseline
    z_pos = 0  # mm logical baseline; +Z is down; forbid z_pos > 2.0
    Z_BUFFER = 2  # mm tolerance buffer to match firmware
    stack: List[int] = []  # loop expansion counting (store repeat counts)
    # We will expand loops naively up to a safety cap to detect negative excursions.
    expanded: List[Tuple[int,str]] = []
    i = 0
    # Build a simple representation without full recursion complexity
    # We'll just process linearly and handle loops via a stack collecting bodies.
    loop_bodies: List[Tuple[int,List[Tuple[int,str]]]] = []  # (repeat, body)
    for line_num, raw in enumerate(lines, start=1):
        s = raw.strip()
        if not s or s.startswith('#'): continue
        parts = s.split()
        cmd = parts[0].lower()
        if cmd == 'loop' and len(parts)==2 and parts[1].isdigit():
            loop_bodies.append((int(parts[1]), []))
            continue
        if cmd == 'endloop':
            if not loop_bodies:
                continue
            rep, body = loop_bodies.pop()
            body_rep = body * rep
            if loop_bodies:
                loop_bodies[-1][1].extend(body_rep)
            else:
                expanded.extend(body_rep)
            continue
        # normal command
        if loop_bodies:
            loop_bodies[-1][1].append((line_num, s))
        else:
            expanded.append((line_num, s))
    # Unclosed loops ignored here; already reported

    # Now check Z position evolution
    for line_num, s in expanded:
        parts = s.split()
        cmd = parts[0].lower()
        if cmd == 'zero' and len(parts)==2 and parts[1].lower()=='z':
            z_pos = 0
            continue
        if cmd == 'move' and len(parts)==3 and parts[1].lower()=='z':
            try:
                delta = float(parts[2])
            except ValueError:
                continue  # already flagged in first pass
            new_z = z_pos + delta
            if new_z > Z_BUFFER:
                errors.append(ValidationError(line_num, f"Z soft-limit violation: move would reach {new_z} (> {Z_BUFFER}). Use smaller move or zero z earlier."))
            else:
                z_pos = new_z
    
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
