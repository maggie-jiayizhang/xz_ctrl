"""
Motor Script Parser
Processes validated motor control scripts and generates output
"""

import csv
import os
from typing import List, Tuple, Optional
from validator import validate_script, get_error_summary


class ScriptParser:
    """Parser for motor control scripts"""
    
    def __init__(self):
        self.output_lines = []
    
    def parse_and_generate(self, script_text: str, output_path: str = None) -> Tuple[bool, str]:
        """
        Parse and process a motor script.
        
        Args:
            script_text: The script content to parse
            output_path: Optional path to save CSV output
        
        Returns:
            Tuple of (success: bool, message: str)
            - If successful: (True, "Success message")
            - If failed: (False, "Error message")
        """
        # Step 0: Validate the script first
        errors = validate_script(script_text)
        if errors:
            error_msg = get_error_summary(errors)
            return False, f"Script validation failed:\n\n{error_msg}"
        
        # Step 1: Process the script line by line
        self.output_lines = []
        lines = script_text.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                continue
            
            # Skip comments (but we could optionally keep them)
            if stripped.startswith('#'):
                # For now, echo comments too
                self.output_lines.append(f"# Line {line_num}: {stripped}")
                print(f"Line {line_num}: {stripped}")
                continue
            
            # Echo the command
            self.output_lines.append(f"{stripped}")
            print(f"Line {line_num}: {stripped}")
        
        # Step 2: Save to CSV if output path provided
        if output_path:
            try:
                self._save_to_csv(output_path)
                return True, f"Script processed successfully!\nOutput saved to: {output_path}\nProcessed {len(self.output_lines)} lines."
            except Exception as e:
                return False, f"Failed to save output:\n{e}"
        else:
            return True, f"Script processed successfully!\nProcessed {len(self.output_lines)} lines."
    
    def _save_to_csv(self, output_path: str):
        """Save the output lines to a CSV file"""
        # Ensure the directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Write to CSV (one line per row, no headers)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for line in self.output_lines:
                writer.writerow([line])
    
    def get_output(self) -> List[str]:
        """Get the processed output lines"""
        return self.output_lines


def process_script_file(input_csv: str, output_csv: str = None) -> Tuple[bool, str]:
    """
    Process a script from a CSV file and optionally save to another CSV.
    
    Args:
        input_csv: Path to input CSV file
        output_csv: Optional path to output CSV file
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Read the input CSV
    try:
        with open(input_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            lines = [row[0] if row else '' for row in reader]
            script_text = '\n'.join(lines)
    except Exception as e:
        return False, f"Failed to read input file:\n{e}"
    
    # Parse and generate
    parser = ScriptParser()
    return parser.parse_and_generate(script_text, output_csv)


# Example usage
if __name__ == "__main__":
    test_script = """
# Test script
move x 100 1000 500
wait 500
move z 50 1500 300

loop 3
  move x -20 1000 200
  wait 200
  move z 10 1500 100
endloop
"""
    
    print("=" * 60)
    print("Testing Script Parser")
    print("=" * 60)
    
    parser = ScriptParser()
    success, message = parser.parse_and_generate(test_script, "test_output.csv")
    
    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)
    print(message)
    
    if success:
        print("\nOutput lines:")
        for i, line in enumerate(parser.get_output(), start=1):
            print(f"  {i}. {line}")
