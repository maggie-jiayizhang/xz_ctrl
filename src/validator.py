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



def validate_move_or_trap_command(parts: List[str], line_num: int, cmd_name: str) -> Optional[ValidationError]:
    """
    Validate move/movetrap command: move x|z <distance> <speed> or movetrap x|z <distance> <speed>
    Returns ValidationError if invalid, None if valid
    """
    if len(parts) != 4:
        return ValidationError(line_num, f"{cmd_name} requires 3 parameters (axis, distance, speed), got {len(parts)-1}")
    axis = parts[1].lower()
    if axis not in ['x', 'z']:
        return ValidationError(line_num, f"Invalid axis '{parts[1]}', must be 'x' or 'z'")
    try:
        distance = int(parts[2])
    except ValueError:
        return ValidationError(line_num, f"Invalid distance '{parts[2]}', must be an integer")
    try:
        speed = int(parts[3])
    except ValueError:
        return ValidationError(line_num, f"Invalid speed '{parts[3]}', must be an integer")
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
        return validate_move_or_trap_command(parts, line_num, 'move')
    elif cmd == 'movetrap':
        return validate_move_or_trap_command(parts, line_num, 'movetrap')
    elif cmd == 'loop':
        return validate_loop_command(parts, line_num)
    elif cmd == 'endloop':
        return validate_endloop_command(parts, line_num)
    elif cmd == 'wait':
        return validate_wait_command(parts, line_num)
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
    
    # Validate each line
    for line_num, line in enumerate(lines, start=1):
        error = validate_line(line, line_num)
        if error:
            errors.append(error)
    
    # Validate loop matching
    loop_errors = validate_loop_matching(lines)
    errors.extend(loop_errors)
    
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
