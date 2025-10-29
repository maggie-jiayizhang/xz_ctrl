import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import re
import csv

import os
import csv
from validator import validate_script, get_error_summary
from make_script_util import make_script_from_csv_rows


class MotorControllerGUI:


    def save_to_csv(self, event=None):
        """Save the script to a CSV file. Each non-empty line is saved as a single row (just the text, no headers)."""
        file_path = filedialog.asksaveasfilename(
            title="Save Script as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            self.update_status("Save canceled")
            return
        content = self.text_area.get("1.0", tk.END)
        lines = content.splitlines()
        rows = []
        for line in lines:
            if line.strip():
                rows.append([line])
        if len(rows) == 0:
            if not messagebox.askyesno(
                "Empty Script",
                "No non-empty lines found. Save an empty CSV?"
            ):
                self.update_status("Nothing saved")
                return
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            self.update_status(f"Saved CSV ({len(rows)} lines)")
            messagebox.showinfo("Saved", f"Script saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save CSV.\n\n{e}")
            self.update_status("Save failed")
    def __init__(self, root):
        self.root = root
        self.root.title("Motor Controller - Script Editor")
        self.root.geometry("1100x750")

        self._setup_ui()
        # Keyboard shortcut to save (Ctrl+S on Windows/Linux, Cmd+S on Mac)
        self.root.bind("<Control-s>", self.save_to_csv)
        self.root.bind("<Command-s>", self.save_to_csv)  # For Mac
        # Keyboard shortcut to load (Ctrl+O on Windows/Linux, Cmd+O on Mac)
        self.root.bind("<Control-o>", self.load_from_csv)
        self.root.bind("<Command-o>", self.load_from_csv)
        # Keyboard shortcut to check code (Ctrl+E on Windows/Linux, Cmd+E on Mac)
        self.root.bind("<Control-e>", self.check_code)
        self.root.bind("<Command-e>", self.check_code)
        # Keyboard shortcut to toggle hints (Ctrl+H)
        self.root.bind("<Control-h>", self._toggle_hints)
    
    def _setup_ui(self):
        """Set up the user interface"""
        # Top control panel
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, side=tk.TOP)
        ttk.Label(control_frame, text="Motor Script Editor", font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        
        # Save to CSV button (S)
        self.save_btn = ttk.Button(
            control_frame,
            text="Save CSV",
            command=self.save_to_csv
        )
        self.save_btn.pack(side=tk.RIGHT, padx=5)

        # Load CSV button (O)
        self.load_btn = ttk.Button(
            control_frame,
            text="Load CSV",
            command=self.load_from_csv
        )
        self.load_btn.pack(side=tk.RIGHT, padx=5)

        # Check Code button (E)
        self.check_btn = ttk.Button(
            control_frame,
            text="Check Code",
            command=self.check_code
        )
        self.check_btn.pack(side=tk.RIGHT, padx=5)

        # Make Script button (no shortcut yet)
        self.make_btn = ttk.Button(
            control_frame,
            text="Make Script",
            command=self.make_script
        )
        self.make_btn.pack(side=tk.RIGHT, padx=5)


        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Main editor container
        editor_frame = ttk.Frame(self.root, padding=10)
        editor_frame.pack(fill=tk.BOTH, expand=True)
        
        # Main container for text area and hint panel
        main_container = ttk.Frame(editor_frame)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Text area for commands
        self.text_area = scrolledtext.ScrolledText(
            main_container,
            width=80,
            height=25,
            wrap=tk.WORD,
            font=("Consolas", 11)
        )
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Hint/Example panel (initially visible)
        self.hint_frame = ttk.LabelFrame(main_container, text="Examples & Hints", padding=8)
        self.hint_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
        
        self.hint_text = tk.Text(
            self.hint_frame,
            width=35,
            height=25,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#fffef0",
            state=tk.DISABLED,
            relief=tk.FLAT,
            borderwidth=1
        )
        self.hint_text.pack(fill=tk.BOTH, expand=True)
        
        # Add hint content
        hint_content = """COMMAND REFERENCE:

move x <distance> <speed>

move z <distance> <speed>

movetrap x <distance> <speed>

movetrap z <distance> <speed>

loop <n_iter>

endloop
    End the loop block

wait <milliseconds>
    Pause execution
    Ex: wait 1000

# Comment

SAMPLE PROGRAM:
# Initialize position
move x 100 500
wait 500
movetrap z 50 300

# Repeat pattern
loop 3
    move x -20 400
    wait 200
    movetrap z 10 200
endloop"""
        
        self.hint_text.config(state=tk.NORMAL)
        self.hint_text.insert("1.0", hint_content)
        # Configure tags for syntax highlighting in hints
        self.hint_text.tag_config("header", font=("Consolas", 9, "bold"), foreground="#333")
        self.hint_text.tag_config("move_h", foreground="#9b59b6", font=("Consolas", 9, "bold"))
        self.hint_text.tag_config("movetrap_h", foreground="#2980b9", font=("Consolas", 9, "bold"))
        self.hint_text.tag_config("loop_h", foreground="#f39c12", font=("Consolas", 9, "bold"))
        self.hint_text.tag_config("endloop_h", foreground="#f39c12", font=("Consolas", 9, "bold"))
        self.hint_text.tag_config("wait_h", foreground="#27ae60", font=("Consolas", 9, "bold"))
        self.hint_text.tag_config("comment_h", foreground="#95a5a6", font=("Consolas", 9, "italic"))
        # Apply syntax highlighting to hint examples
        self.hint_text.tag_add("header", "1.0", "1.17")
        # Highlight command keywords in examples
        self._highlight_hint_syntax()
        self.hint_text.config(state=tk.DISABLED)
        self.hint_visible = True
        
        # Configure syntax highlighting tags for main editor
        self.text_area.tag_config("move", foreground="#9b59b6", font=("Consolas", 11, "bold"))
        self.text_area.tag_config("loop", foreground="#f39c12", font=("Consolas", 11, "bold"))
        self.text_area.tag_config("endloop", foreground="#f39c12", font=("Consolas", 11, "bold"))
        self.text_area.tag_config("wait", foreground="#27ae60", font=("Consolas", 11, "bold"))
        self.text_area.tag_config("comment", foreground="#95a5a6", font=("Consolas", 11, "italic"))
        self.text_area.tag_config("error", background="#ffcccc")  # Error highlighting
        
        # Bind text change event for syntax highlighting
        self.text_area.bind("<KeyRelease>", self._highlight_syntax)
        
        # Button frame at bottom
        button_frame = ttk.Frame(editor_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))

        # Toggle hints button
        self.toggle_hint_btn = ttk.Button(
            button_frame,
            text="Hide Hints",
            command=self._toggle_hints
        )
        self.toggle_hint_btn.pack(side=tk.LEFT)

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Bind keyboard events to show/hide shortcut hints
        import platform
        self.root.bind_all("<KeyPress-Control_L>", self._show_shortcuts)
        self.root.bind_all("<KeyRelease-Control_L>", self._hide_shortcuts)
        self.root.bind_all("<KeyPress-Control_R>", self._show_shortcuts)
        self.root.bind_all("<KeyRelease-Control_R>", self._hide_shortcuts)
        if platform.system() == "Darwin":  # Mac
            self.root.bind_all("<KeyPress-Command>", self._show_shortcuts)
            self.root.bind_all("<KeyRelease-Command>", self._hide_shortcuts)
    
    def _show_shortcuts(self, event=None):
        """Show keyboard shortcut hints on buttons"""
        self.save_btn.config(text="Save CSV (S)")
        self.load_btn.config(text="Load CSV (O)")
        self.check_btn.config(text="Check Code (E)")
        self.toggle_hint_btn.config(text="Hide Hints (H)")
    
    def _hide_shortcuts(self, event=None):
        """Hide keyboard shortcut hints on buttons"""
        self.save_btn.config(text="Save CSV")
        self.load_btn.config(text="Load CSV")
        self.check_btn.config(text="Check Code")
        self.toggle_hint_btn.config(text="Hide Hints")
    
    def _toggle_hints(self, event=None):
        """Toggle hint panel visibility"""
        if self.hint_visible:
            self.hint_frame.pack_forget()
            self.toggle_hint_btn.config(text="Show Hints")
            self.update_status("Hints hidden. Press Ctrl+H to show.")
        else:
            self.hint_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
            self.toggle_hint_btn.config(text="Hide Hints")
            self.update_status("Hints shown. Press Ctrl+H to hide.")
        self.hint_visible = not self.hint_visible
    
    def _highlight_hint_syntax(self):
        """Apply syntax highlighting to the hint panel examples"""
        content = self.hint_text.get("1.0", tk.END)
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            line_stripped = line.strip()
            # Highlight movetrap commands
            if line_stripped.startswith('movetrap x') or line_stripped.startswith('movetrap z'):
                start_idx = line.find('movetrap')
                if start_idx != -1:
                    start = f"{line_num}.{start_idx}"
                    end = f"{line_num}.{start_idx + 8}"
                    self.hint_text.tag_add("movetrap_h", start, end)
            # Highlight move commands
            elif line_stripped.startswith('move x') or line_stripped.startswith('move z'):
                start_idx = line.find('move')
                if start_idx != -1:
                    start = f"{line_num}.{start_idx}"
                    end = f"{line_num}.{start_idx + 4}"
                    self.hint_text.tag_add("move_h", start, end)
            # Highlight loop
            elif line_stripped.startswith('loop '):
                start_idx = line.find('loop')
                if start_idx != -1:
                    start = f"{line_num}.{start_idx}"
                    end = f"{line_num}.{start_idx + 4}"
                    self.hint_text.tag_add("loop_h", start, end)
            # Highlight endloop
            elif line_stripped.startswith('endloop'):
                start_idx = line.find('endloop')
                if start_idx != -1:
                    start = f"{line_num}.{start_idx}"
                    end = f"{line_num}.{start_idx + 7}"
                    self.hint_text.tag_add("endloop_h", start, end)
            # Highlight wait
            elif line_stripped.startswith('wait '):
                start_idx = line.find('wait')
                if start_idx != -1:
                    start = f"{line_num}.{start_idx}"
                    end = f"{line_num}.{start_idx + 4}"
                    self.hint_text.tag_add("wait_h", start, end)
            # Highlight comments
            elif line_stripped.startswith('#'):
                start = f"{line_num}.0"
                end = f"{line_num}.end"
                self.hint_text.tag_add("comment_h", start, end)
    
    def _highlight_syntax(self, event=None):
        """Apply syntax highlighting to command keywords and comments"""
        # Remove all existing tags
        self.text_area.tag_remove("move", "1.0", tk.END)
        self.text_area.tag_remove("loop", "1.0", tk.END)
        self.text_area.tag_remove("endloop", "1.0", tk.END)
        self.text_area.tag_remove("wait", "1.0", tk.END)
        self.text_area.tag_remove("comment", "1.0", tk.END)
        
        # Get all text
        content = self.text_area.get("1.0", tk.END)
        lines = content.split('\n')
        
        # Regex patterns for commands (allow indentation)
        movetrap_pattern = r'^\s*movetrap\s+(x|z)\s+'
        move_pattern = r'^\s*move\s+(x|z)\s+'
        loop_pattern = r'^\s*loop\s+'
        endloop_pattern = r'^\s*endloop'
        wait_pattern = r'^\s*wait\s+'
        comment_pattern = r'^\s*#'

        for line_num, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            # Check for comments first
            if re.match(comment_pattern, line):
                start = f"{line_num}.0"
                end = f"{line_num}.end"
                self.text_area.tag_add("comment", start, end)
            # Check for movetrap command
            elif re.match(movetrap_pattern, line, re.IGNORECASE):
                match = re.search(r'movetrap', line, re.IGNORECASE)
                if match:
                    start = f"{line_num}.{match.start()}"
                    end = f"{line_num}.{match.end()}"
                    self.text_area.tag_add("move", start, end)
            # Check for move command
            elif re.match(move_pattern, line, re.IGNORECASE):
                match = re.search(r'move', line, re.IGNORECASE)
                if match:
                    start = f"{line_num}.{match.start()}"
                    end = f"{line_num}.{match.end()}"
                    self.text_area.tag_add("move", start, end)
            # Check for endloop command
            elif re.match(endloop_pattern, line, re.IGNORECASE):
                match = re.search(r'endloop', line, re.IGNORECASE)
                if match:
                    start = f"{line_num}.{match.start()}"
                    end = f"{line_num}.{match.end()}"
                    self.text_area.tag_add("endloop", start, end)
            # Check for loop command
            elif re.match(loop_pattern, line, re.IGNORECASE):
                match = re.search(r'loop', line, re.IGNORECASE)
                if match:
                    start = f"{line_num}.{match.start()}"
                    end = f"{line_num}.{match.end()}"
                    self.text_area.tag_add("loop", start, end)
            # Check for wait command
            elif re.match(wait_pattern, line, re.IGNORECASE):
                match = re.search(r'wait', line, re.IGNORECASE)
                if match:
                    start = f"{line_num}.{match.start()}"
                    end = f"{line_num}.{match.end()}"
                    self.text_area.tag_add("wait", start, end)
    
    
    def check_code(self, event=None):
        """Validate the script and highlight errors"""
        # Clear previous error highlighting
        self.text_area.tag_remove("error", "1.0", tk.END)
        
        # Get script content
        content = self.text_area.get("1.0", tk.END)
        
        # Validate
        errors = validate_script(content)
        
        if not errors:
            messagebox.showinfo("Validation", "✓ No errors found - script is valid!")
            self.update_status("Code validation: No errors")
            return
        
        # Highlight error lines
        for error in errors:
            line_start = f"{error.line_num}.0"
            line_end = f"{error.line_num}.end"
            self.text_area.tag_add("error", line_start, line_end)
        
        # Show error summary
        summary = get_error_summary(errors)
        messagebox.showerror("Validation Errors", summary)
        self.update_status(f"Code validation: {len(errors)} error(s) found")
    
    def make_script(self):
        """Read a CSV, validate, expand loops, join with |, and save to a text file."""
        # Ask for CSV file to process
        file_path = filedialog.askopenfilename(
            title="Select CSV to Make Script",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            self.update_status("Make script canceled")
            return
        # Read CSV rows
        try:
            with open(file_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [row for row in reader if row and row[0].strip()]
        except Exception as e:
            messagebox.showerror("Read Failed", f"Could not read CSV.\n\n{e}")
            self.update_status("Read failed")
            return
        # Validate script (as text)
        script_text = '\n'.join(row[0] for row in rows)
        errors = validate_script(script_text)
        if errors:
            summary = get_error_summary(errors)
            messagebox.showerror("Validation Errors", summary)
            self.update_status(f"Script not valid: {len(errors)} error(s)")
            return
        # Expand and join script
        script_out = make_script_from_csv_rows(rows)
        # Ask for output filename
        out_filename = filedialog.asksaveasfilename(
            title="Save Final Script",
            defaultextension=".txt",
            initialdir="script2serial",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not out_filename:
            self.update_status("Save canceled")
            return
        try:
            with open(out_filename, "w", encoding="utf-8") as f:
                f.write(script_out)
            messagebox.showinfo("Success", f"Script saved to:\n{out_filename}")
            self.update_status(f"Script generated: {os.path.basename(out_filename)}")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save script.\n\n{e}")
            self.update_status("Script save failed")
    
    def load_from_csv(self, event=None):
        """Load a script from a CSV file into the editor.
        Each row is treated as a line of text.
        """
        # Choose file to load
        file_path = filedialog.askopenfilename(
            title="Load Script from CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            self.update_status("Load canceled")
            return
        
        # Read CSV
        try:
            with open(file_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                lines = []
                for row in reader:
                    if row:  # skip completely empty rows
                        # Take the first column (or join all if multiple columns)
                        line_text = row[0] if len(row) == 1 else ",".join(row)
                        lines.append(line_text)
            
            # Load into editor
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", "\n".join(lines))
            
            # Trigger syntax highlighting
            self._highlight_syntax()
            
            self.update_status(f"Loaded CSV ({len(lines)} lines)")
            messagebox.showinfo("Loaded", f"Script loaded from:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Load Failed", f"Could not load CSV.\n\n{e}")
            self.update_status("Load failed")
    
    def update_status(self, message):
        """Update the status bar"""
        self.status_bar.config(text=message)


def main():
    root = tk.Tk()
    app = MotorControllerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

