import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import re
import platform
from typing import List

from validator import validate_script, get_error_summary
from arduino_serial import ArduinoController


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Robot Controller")
        # Default window: thinner and taller
        self.geometry("900x900")

        # State
        self.arduino = ArduinoController()
        self.arduino.set_response_callback(self.on_arduino_response)
        
        # Z position tracking: starts at -50mm (safe distance from contact)
        # Updated by script simulation; persists across runs until 'zero z' resets it
        self.z_position = -50.0  # mm
        
        # Detect OS for modifier key
        self.is_mac = platform.system() == 'Darwin'
        self.mod_key = 'Command' if self.is_mac else 'Control'
        self.mod_symbol = '⌘' if self.is_mac else 'Ctrl'
        self.showing_shortcuts = False

        # Build UI
        self._build_ui()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Bind keyboard shortcuts
        self._bind_shortcuts()

    def _build_ui(self):
        # Top toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        self.connect_btn = ttk.Button(toolbar, text="Connect", command=self.connect_arduino)
        self.connect_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.connect_btn_text = "Connect"

        self.send_btn = ttk.Button(toolbar, text="Send to Arduino", command=self.send_to_arduino)
        self.send_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.send_btn_text = "Send to Arduino"

        self.stop_btn = ttk.Button(toolbar, text="STOP", command=self.emergency_stop)
        self.stop_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.stop_btn_text = "STOP"

        self.reportz_btn = ttk.Button(toolbar, text="Report Z", command=self.report_z)
        self.reportz_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.reportz_btn_text = "Report Z"

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        self.save_btn = ttk.Button(toolbar, text="Save Script", command=self.save_script)
        self.save_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.save_btn_text = "Save Script"

        self.load_btn = ttk.Button(toolbar, text="Load Script", command=self.load_script)
        self.load_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.load_btn_text = "Load Script"

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        self.clear_console_btn = ttk.Button(toolbar, text="Clear Console", command=self.clear_console)
        self.clear_console_btn.pack(side=tk.LEFT, padx=4, pady=4)
        self.clear_console_btn_text = "Clear Console"

        # Paned window: editor left, console right
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Editor frame
        editor_frame = ttk.Frame(paned)
        paned.add(editor_frame, weight=3)

        # Editor label and help
        lbl = ttk.Label(editor_frame, text="Script Editor (Arduino format + loop/endloop)")
        lbl.pack(anchor=tk.W, padx=6, pady=(6, 2))

        # Editor with line numbers
        editor_container = ttk.Frame(editor_frame)
        editor_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Line numbers
        self.line_numbers = tk.Text(editor_container, width=4, padx=3, takefocus=0, 
                                      border=0, background='#f0f0f0', state='disabled',
                                      font=("Consolas", 12), wrap=tk.NONE)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Editor Text
        self.text_area = ScrolledText(editor_container, wrap=tk.NONE, font=("Consolas", 12), undo=True)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Sample starter text
        starter = (
            "# Example script\n"
            "speed x 5.0\n"
            "speed z 5.0\n"
            "move x 10\n"
            "wait 500\n"
            "move z -5\n"
            "\n"
            "loop 3\n"
            "  move x 10\n"
            "  wait 200\n"
            "  move x -10\n"
            "endloop\n"
        )
        self.text_area.insert("1.0", starter)

        # Syntax highlighting tags
        self.text_area.tag_config("kw_move", foreground="#9b59b6", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("kw_speed", foreground="#2980b9", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("kw_loop", foreground="#f39c12", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("kw_endloop", foreground="#f39c12", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("kw_wait", foreground="#27ae60", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("kw_pulse", foreground="#e91e63", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("kw_zero", foreground="#e74c3c", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("kw_report", foreground="#16a085", font=("Consolas", 12, "bold"))
        self.text_area.tag_config("comment", foreground="#95a5a6", font=("Consolas", 12, "italic"))
        self.text_area.tag_config("error", background="#ffcccc")
        self.text_area.bind("<KeyRelease>", self._highlight_syntax)
        self.text_area.bind("<KeyRelease>", self._update_line_numbers, add="+")
        self.text_area.bind("<<Modified>>", self._update_line_numbers, add="+")
        self._highlight_syntax()
        self._update_line_numbers()

        # Console frame
        console_frame = ttk.Frame(paned)
        paned.add(console_frame, weight=2)
        ttk.Label(console_frame, text="Arduino Console").pack(anchor=tk.W, padx=6, pady=(6, 2))
        self.console = ScrolledText(console_frame, wrap=tk.WORD, height=10, state=tk.NORMAL, font=("Consolas", 10))
        self.console.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.console.insert(tk.END, "<console output will appear here>\n")
        self.console.configure(state=tk.DISABLED)

        # Status bar
        self.status_var = tk.StringVar(value="Disconnected")
        status = ttk.Label(self, textvariable=self.status_var, anchor=tk.W, relief=tk.SUNKEN)
        status.pack(side=tk.BOTTOM, fill=tk.X)

    # =====================
    # Syntax highlighting
    # =====================
    def _highlight_syntax(self, event=None):
        # Clear tags
        for tag in ["kw_move", "kw_speed", "kw_loop", "kw_endloop", "kw_wait", "kw_pulse", "kw_zero", "kw_report", "comment", "error"]:
            self.text_area.tag_remove(tag, "1.0", tk.END)

        text = self.text_area.get("1.0", tk.END)
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            s = line.lstrip()
            if not s:
                continue
            if s.startswith('#'):
                self.text_area.tag_add("comment", f"{i}.0", f"{i}.end")
                continue
            for kw, tag in [(r"\bmove\b", "kw_move"), (r"\bspeed\b", "kw_speed"), (r"\bloop\b", "kw_loop"), (r"\bendloop\b", "kw_endloop"), (r"\bwait\b", "kw_wait"), (r"\bpulse\b", "kw_pulse"), (r"\bzero\b", "kw_zero"), (r"\breport\b", "kw_report")]:
                m = re.search(kw, line, flags=re.IGNORECASE)
                if m:
                    self.text_area.tag_add(tag, f"{i}.{m.start()}", f"{i}.{m.end()}")

    def _update_line_numbers(self, event=None):
        # Update line numbers display
        line_count = int(self.text_area.index('end-1c').split('.')[0])
        line_numbers_string = "\n".join(str(i) for i in range(1, line_count + 1))
        
        self.line_numbers.config(state='normal')
        self.line_numbers.delete('1.0', tk.END)
        self.line_numbers.insert('1.0', line_numbers_string)
        self.line_numbers.config(state='disabled')

    # =====================
    # File operations
    # =====================
    def save_script(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=".",
            title="Save Script"
        )
        if not filepath:
            return
        
        try:
            content = self.text_area.get("1.0", tk.END).rstrip()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self._set_status(f"Saved to {filepath}")
            self._log_console(f"[info] Script saved to {filepath}\n")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save file: {e}")
            self._set_status(f"Save failed: {e}")

    def load_script(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=".",
            title="Load Script"
        )
        if not filepath:
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", content)
            self._highlight_syntax()
            self._update_line_numbers()
            self._set_status(f"Loaded from {filepath}")
            self._log_console(f"[info] Script loaded from {filepath}\n")
        except Exception as e:
            messagebox.showerror("Load Failed", f"Could not load file: {e}")
            self._set_status(f"Load failed: {e}")


    # =====================
    # Connection handling
    # =====================
    def connect_arduino(self):
        if self.arduino.is_connected:
            messagebox.showinfo("Arduino", f"Already connected to {self.arduino.port}")
            return

        ports = self.arduino.list_ports()
        if not ports:
            messagebox.showerror("Arduino", "No serial ports found")
            return

        selected = self._port_selection_dialog(ports)
        if not selected:
            self._set_status("Connect canceled")
            return

        ok, msg = self.arduino.connect(selected, baudrate=115200)
        self._set_status(msg)
        if not ok:
            messagebox.showerror("Connect Failed", msg)
        else:
            self._log_console(f"[info] {msg}\n")

    def _port_selection_dialog(self, ports: List[str]) -> str:
        sel = {"port": None}

        dlg = tk.Toplevel(self)
        dlg.title("Select Serial Port")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text="Choose a port:").pack(anchor=tk.W, padx=10, pady=(10, 6))
        var = tk.StringVar(value=ports[0])
        for p in ports:
            ttk.Radiobutton(dlg, text=p, variable=var, value=p).pack(anchor=tk.W, padx=16)

        btns = ttk.Frame(dlg); btns.pack(fill=tk.X, padx=10, pady=10)
        def on_ok():
            sel["port"] = var.get()
            dlg.destroy()
        def on_cancel():
            sel["port"] = None
            dlg.destroy()
        ttk.Button(btns, text="OK", command=on_ok).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=6)

        self.wait_window(dlg)
        return sel["port"]

    # =====================
    # Sending and conversion
    # =====================
    def send_to_arduino(self):
        if not self.arduino.is_connected:
            messagebox.showwarning("Arduino", "Not connected")
            return

        text = self.text_area.get("1.0", tk.END)
        # Validate first
        errors = validate_script(text)
        if errors:
            summary = get_error_summary(errors)
            messagebox.showerror("Validation Errors", summary)
            self._set_status(f"Validation failed: {len(errors)} error(s)")
            return

        # Convert: expand loops and pass through commands
        cmds = self.convert_to_arduino_commands(text.splitlines())
        # Pre-check: Z soft-limit (>=0) with optional zero z resets in script
        ok_soft, msg_soft = self._check_z_soft_limit(cmds)
        if not ok_soft:
            messagebox.showerror("Z Soft-limit", msg_soft)
            self._set_status("Z soft-limit check failed")
            return
        if not cmds:
            self._set_status("Nothing to send")
            return

        ok, msg = self.arduino.send_script(cmds)
        self._set_status(msg)
        if not ok:
            messagebox.showerror("Send Failed", msg)
        else:
            self._log_console(f"[info] Sent {len(cmds)} command(s)\n")

    def convert_to_arduino_commands(self, lines: List[str]) -> List[str]:
        # Expand loop/endloop; support nesting
        out: List[str] = []
        stack = []  # list of tuples (repeat_count, body_lines)

        def push_line(target_list: List[str], line: str):
            s = line.strip()
            if not s or s.startswith('#'):
                return
            # Allowed commands: move x/z D | speed x/z S | wait T | pulse T | zero z
            parts = s.split()
            cmd = parts[0].lower()
            if cmd in ("move", "speed", "wait", "pulse", "zero", "report"):
                target_list.append(s)

        for raw in lines:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            cmd = parts[0].lower()

            if cmd == 'loop' and len(parts) == 2 and parts[1].isdigit():
                stack.append((int(parts[1]), []))
                continue
            if cmd == 'endloop':
                if not stack:
                    # unmatched endloop ignored (validator should catch)
                    continue
                count, body = stack.pop()
                expanded = body * count
                if stack:
                    # add into upper loop body
                    stack[-1][1].extend(expanded)
                else:
                    out.extend(expanded)
                continue

            # normal command
            if stack:
                push_line(stack[-1][1], line)
            else:
                push_line(out, line)

        return out

    def _check_z_soft_limit(self, cmds: List[str]):
        """Simulate Z moves with 'zero z' baseline: +Z is down; forbid Z > 2.0.
        Tracks Z position persistently across script runs.
        Returns (ok, message)."""
        z = self.z_position  # Start from last known position (persistent across runs)
        Z_BUFFER = 2.0  # mm tolerance to match firmware
        
        # Track if this script will zero Z (for position update at end)
        will_zero = False
        z_after_last_zero = 0  # Position after the last 'zero z' in script
        
        for idx, s in enumerate(cmds, start=1):
            parts = s.split()
            if not parts:
                continue
            cmd = parts[0].lower()
            if cmd == 'zero' and len(parts) == 2 and parts[1].lower() == 'z':
                z = 0  # Reset baseline to contact point for simulation
                will_zero = True
                z_after_last_zero = 0  # Track position from this zero point
                continue
            if cmd == 'move' and len(parts) == 3 and parts[1].lower() == 'z':
                try:
                    dz = float(parts[2])
                except ValueError:
                    continue
                if z + dz > Z_BUFFER:
                    print(z, dz)
                    return False, f"Command #{idx} would move Z beyond buffer (to {z+dz:.1f}, limit {Z_BUFFER}). Use 'zero z' at contact point or reduce the move."
                z += dz
                if will_zero:
                    z_after_last_zero = z  # Update position relative to last zero
        
        # Only update GUI tracking if script doesn't contain 'zero z'
        # If script has 'zero z', the Arduino will handle the actual zeroing
        if not will_zero:
            self.z_position = z
        # If script has 'zero z', update to position after last zero
        else:
            self.z_position = z_after_last_zero
            
        return True, "OK"

    # =====================
    # Emergency stop and console
    # =====================
    def emergency_stop(self):
        if not self.arduino.is_connected:
            return
        ok, msg = self.arduino.emergency_stop()
        self._log_console("\n!!! EMERGENCY STOP !!!\n")
        self._set_status(msg)

    def clear_console(self):
        self.console.configure(state=tk.NORMAL)
        self.console.delete("1.0", tk.END)
        self.console.configure(state=tk.DISABLED)

    def on_arduino_response(self, text: str):
        self._log_console(text + "\n")

    def _log_console(self, text: str):
        self.console.configure(state=tk.NORMAL)
        self.console.insert(tk.END, text)
        self.console.see(tk.END)
        self.console.configure(state=tk.DISABLED)

    def _set_status(self, text: str):
        self.status_var.set(text)

    def _bind_shortcuts(self):
        """Bind keyboard shortcuts and show/hide hints."""
        # Bind shortcuts
        # Connect moved off 'C' so Copy can use the standard binding.
        self.bind(f'<{self.mod_key}-k>', lambda e: self.connect_arduino())  # Connect
        self.bind(f'<{self.mod_key}-r>', lambda e: self.send_to_arduino())
        self.bind(f'<{self.mod_key}-e>', lambda e: self.emergency_stop())
        self.bind(f'<{self.mod_key}-s>', lambda e: self.save_script())
        self.bind(f'<{self.mod_key}-o>', lambda e: self.load_script())
        self.bind(f'<{self.mod_key}-l>', lambda e: self.clear_console())
        self.bind(f'<{self.mod_key}-z>', lambda e: self.report_z())

        # Editor common shortcuts (Select All, Copy, Paste) bound explicitly for both Control and Command
        for key in ('Control', 'Command'):
            # Select All
            self.text_area.bind(f'<{key}-a>', self._select_all)
            # Copy / Paste (use Tk virtual events so system clipboard works)
            self.text_area.bind(f'<{key}-c>', self._copy)
            self.text_area.bind(f'<{key}-v>', self._paste)
        # Also bind on root in case focus shifts
        for key in ('Control', 'Command'):
            self.bind(f'<{key}-a>', self._select_all)
            self.bind(f'<{key}-c>', self._copy)
            self.bind(f'<{key}-v>', self._paste)
        
        # Show shortcuts when modifier is held
        self.bind(f'<{self.mod_key}_L>', self._show_shortcuts)
        self.bind(f'<{self.mod_key}_R>', self._show_shortcuts)
        self.bind(f'<KeyRelease-{self.mod_key}_L>', self._hide_shortcuts)
        self.bind(f'<KeyRelease-{self.mod_key}_R>', self._hide_shortcuts)

    def _show_shortcuts(self, event=None):
        """Show keyboard shortcuts on buttons."""
        if self.showing_shortcuts:
            return
        self.showing_shortcuts = True
        self.connect_btn.config(text=f"{self.connect_btn_text} [K]")
        self.send_btn.config(text=f"{self.send_btn_text} [R]")
        self.stop_btn.config(text=f"{self.stop_btn_text} [E]")
        self.save_btn.config(text=f"{self.save_btn_text} [S]")
        self.load_btn.config(text=f"{self.load_btn_text} [O]")
        self.clear_console_btn.config(text=f"{self.clear_console_btn_text} [L]")
        self.reportz_btn.config(text=f"{self.reportz_btn_text} [Z]")

    def _hide_shortcuts(self, event=None):
        """Hide keyboard shortcuts from buttons."""
        if not self.showing_shortcuts:
            return
        self.showing_shortcuts = False
        self.connect_btn.config(text=self.connect_btn_text)
        self.send_btn.config(text=self.send_btn_text)
        self.stop_btn.config(text=self.stop_btn_text)
        self.save_btn.config(text=self.save_btn_text)
        self.load_btn.config(text=self.load_btn_text)
        self.clear_console_btn.config(text=self.clear_console_btn_text)
        self.reportz_btn.config(text=self.reportz_btn_text)

    # =====================
    # Editor convenience actions
    # =====================
    def _select_all(self, event=None):
        self.text_area.tag_add('sel', '1.0', 'end-1c')
        return 'break'

    def _copy(self, event=None):
        # Use virtual event so Tk handles clipboard
        self.text_area.event_generate('<<Copy>>')
        return 'break'

    def _paste(self, event=None):
        self.text_area.event_generate('<<Paste>>')
        return 'break'

    def report_z(self):
        """Request current Z position from firmware (report z)."""
        if not self.arduino.is_connected:
            messagebox.showwarning("Arduino", "Not connected")
            return
        ok, msg = self.arduino.send_command("report z")
        if not ok:
            self._log_console(f"[error] {msg}\n")
        else:
            # Firmware will respond asynchronously; we just set status
            self._set_status("Requested Z position")

    def _on_closing(self):
        """Send stop signal to Arduino before closing if connected."""
        if self.arduino.is_connected:
            try:
                self.arduino.emergency_stop()
            except:
                pass  # Ignore errors during cleanup
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
