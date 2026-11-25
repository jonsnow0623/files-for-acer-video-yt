import ctypes
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None
    TRAY_AVAILABLE = False

APP_TITLE = "Amit's Aspire RGB Studio"
THEMES = {
    "Rainbow Transform": "colourtransform",
    "Breathing": "breathe",
    "Fresh Breathe": "freshbreathe",
    "Blink": "blink",
    "Heartbeat": "heartbeat",
    "Sakura Transform": "sakuratransform",
    "Sakura Sunset": "sakurasunset",
    "Sunset Breathe": "sunsetbreathe",
    "Pink Breathe": "pinkbreathe",
    "Awesome (cycles effects)": "awesome",
}

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def relaunch_as_admin():
    # Relaunch this script with UAC so Start/Stop can manage the child process.
    params = subprocess.list2cmdline([str(Path(__file__).resolve())])
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, str(Path(__file__).resolve().parent), 1
    )
    if result <= 32:
        messagebox.showerror(APP_TITLE, "Administrator permission was not granted.")
    sys.exit(0)

class AspireRGBStudio:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("570x790")
        self.root.minsize(530, 700)
        self.root.configure(bg="#10131b")
        self.exe_path = tk.StringVar()
        self.theme_label = tk.StringVar(value="Rainbow Transform")
        self.speed = tk.IntVar(value=20)
        self.status = tk.StringVar(value="Choose CLEVO_KeyboardColour.exe to begin.")
        self.process = None
        self.tray_icon = None
        self._allow_exit = False
        self.custom_rows = []
        self.custom_stop_event = None
        self.custom_thread = None
        self.custom_child = None

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", padding=7)
        style.configure("TButton", padding=8)
        style.configure("TScale", background="#10131b")
        style.configure("TLabel", background="#10131b", foreground="#e9edf5")
        style.configure("Header.TLabel", font=("Segoe UI", 20, "bold"), foreground="#ffffff")
        style.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#aab4c8")
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"), foreground="#8fe3b0")

        main = tk.Frame(root, bg="#10131b", padx=24, pady=22)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="AMIT'S ASPIRE RGB STUDIO", style="Header.TLabel").pack(anchor="w")
        ttk.Label(main, text="A lightweight controller for your LAPTOP by AMIT ",
                  style="Sub.TLabel").pack(anchor="w", pady=(4, 4))
        ttk.Label(main, text="Created by AMIT KUMAR YADAV",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 20))

        self.section(main, "1  •  Select the keyboard controller")
        pathrow = tk.Frame(main, bg="#10131b")
        pathrow.pack(fill="x", pady=(7, 18))
        self.path_entry = ttk.Entry(pathrow, textvariable=self.exe_path)
        self.path_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(pathrow, text="Browse…", command=self.browse).pack(side="left", padx=(8, 0))

        self.section(main, "2  •  Choose an effect")
        combo = ttk.Combobox(main, textvariable=self.theme_label,
                             values=list(THEMES.keys()), state="readonly")
        combo.pack(fill="x", pady=(7, 16))

        self.section(main, "3  •  Animation speed")
        speedrow = tk.Frame(main, bg="#10131b")
        speedrow.pack(fill="x", pady=(5, 0))
        self.speed_label = ttk.Label(speedrow, text="20%")
        self.speed_label.pack(side="right")
        scale = ttk.Scale(main, from_=1, to=200, orient="horizontal",
                          command=self.on_speed, value=20)
        scale.pack(fill="x")
        ttk.Label(main, text="1 = slowest   •   100 = normal   •   200 = fastest",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 16))

        buttons = tk.Frame(main, bg="#10131b")
        buttons.pack(fill="x", pady=(6, 14))
        self.start_btn = tk.Button(buttons, text="▶  START EFFECT", command=self.start,
                                   bg="#287a56", fg="white", activebackground="#32966a",
                                   activeforeground="white", relief="flat", font=("Segoe UI", 10, "bold"),
                                   padx=12, pady=12, cursor="hand2")
        self.start_btn.pack(side="left", fill="x", expand=True)
        self.stop_btn = tk.Button(buttons, text="■  STOP", command=self.stop,
                                  bg="#8a3541", fg="white", activebackground="#a94452",
                                  activeforeground="white", relief="flat", font=("Segoe UI", 10, "bold"),
                                  padx=12, pady=12, cursor="hand2")
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(10, 0))

        ttk.Label(main, textvariable=self.status, style="Status.TLabel").pack(anchor="w", pady=(5, 4))
        ttk.Label(main, text="Only one effect can run at a time. Stop the current effect before starting another.",
                  style="Sub.TLabel", wraplength=510).pack(anchor="w", pady=(6, 0))
        ttk.Label(main, text="Uses the original CLEVO utility and InsydeDCHU.dll; it does not modify BIOS or firmware.",
                  style="Sub.TLabel", wraplength=510).pack(anchor="w", pady=(8, 0))
        ttk.Label(main, text="Minimize or close the window to keep Aspire RGB Studio in the system tray.",
                  style="Sub.TLabel", wraplength=510).pack(anchor="w", pady=(6, 0))

        # Additional custom colour cycle section. Existing controls above are intentionally unchanged.
        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=(15, 10))
        self.section(main, "4  •  Custom colour cycle (each colour has its own time)")
        ttk.Label(main, text="Choose a colour and set how many seconds it stays on before the next colour.",
                  style="Sub.TLabel", wraplength=510).pack(anchor="w", pady=(3, 7))

        self.custom_list = tk.Frame(main, bg="#10131b")
        self.custom_list.pack(fill="x")
        for colour, seconds in [
            ("#ff0000", 2), ("#ff7a00", 2), ("#ffff00", 2),
            ("#00cc66", 2), ("#008cff", 2), ("#8a2be2", 2)
        ]:
            self.add_custom_row(colour, seconds)

        custom_buttons = tk.Frame(main, bg="#10131b")
        custom_buttons.pack(fill="x", pady=(8, 4))
        ttk.Button(custom_buttons, text="+ Add colour", command=self.add_custom_row).pack(side="left")
        ttk.Button(custom_buttons, text="Reset colours", command=self.reset_custom_rows).pack(side="left", padx=(8, 0))
        self.custom_start_btn = tk.Button(
            custom_buttons, text="▶  START CUSTOM CYCLE", command=self.start_custom_cycle,
            bg="#315d9a", fg="white", activebackground="#3e75bd",
            activeforeground="white", relief="flat", font=("Segoe UI", 9, "bold"),
            padx=10, pady=9, cursor="hand2"
        )
        self.custom_start_btn.pack(side="right")

        ttk.Label(main, text="Custom cycle uses the CLEVO utility's direct colour command; colour changes are instant, not a fade.",
                  style="Sub.TLabel", wraplength=510).pack(anchor="w", pady=(5, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Unmap>", self.on_minimize)
        self.root.after(500, self.refresh_status)

    def section(self, parent, title):
        tk.Label(parent, text=title, bg="#10131b", fg="#c9d5ee",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

    def browse(self):
        chosen = filedialog.askopenfilename(
            title="Select CLEVO_KeyboardColour.exe",
            filetypes=[("CLEVO keyboard utility", "CLEVO_KeyboardColour.exe"), ("Executable", "*.exe")]
        )
        if chosen:
            self.exe_path.set(chosen)

    def on_speed(self, value):
        val = int(float(value))
        self.speed.set(val)
        self.speed_label.configure(text=f"{val}%")

    def add_custom_row(self, colour="#ffffff", seconds=2):
        row = tk.Frame(self.custom_list, bg="#10131b")
        row.pack(fill="x", pady=2)

        colour_var = tk.StringVar(value=colour)
        seconds_var = tk.StringVar(value=str(seconds))
        swatch = tk.Button(
            row, text="   ", bg=colour, activebackground=colour, relief="flat",
            width=4, command=lambda: self.pick_custom_colour(colour_var, swatch)
        )
        swatch.pack(side="left", padx=(0, 8))
        ttk.Label(row, textvariable=colour_var, width=10).pack(side="left")
        ttk.Label(row, text="Stay (sec):").pack(side="left", padx=(8, 4))
        spin = ttk.Spinbox(row, from_=1, to=3600, increment=1, width=6, textvariable=seconds_var)
        spin.pack(side="left")
        remove = ttk.Button(row, text="Remove", command=lambda: self.remove_custom_row(row))
        remove.pack(side="right")
        self.custom_rows.append({
            "frame": row, "colour": colour_var, "seconds": seconds_var, "swatch": swatch
        })

    def pick_custom_colour(self, colour_var, swatch):
        chosen = colorchooser.askcolor(color=colour_var.get(), title="Choose keyboard colour")
        if chosen and chosen[1]:
            colour_var.set(chosen[1].lower())
            swatch.configure(bg=chosen[1], activebackground=chosen[1])

    def remove_custom_row(self, row):
        self.custom_rows = [item for item in self.custom_rows if item["frame"] is not row]
        row.destroy()

    def reset_custom_rows(self):
        for item in self.custom_rows:
            item["frame"].destroy()
        self.custom_rows.clear()
        for colour, seconds in [
            ("#ff0000", 2), ("#ff7a00", 2), ("#ffff00", 2),
            ("#00cc66", 2), ("#008cff", 2), ("#8a2be2", 2)
        ]:
            self.add_custom_row(colour, seconds)

    def start_custom_cycle(self):
        if self.process is not None and self.process.poll() is None:
            self.stop()
        if self.custom_thread is not None and self.custom_thread.is_alive():
            messagebox.showinfo(APP_TITLE, "Custom colour cycle is already running. Press STOP first.")
            return

        exe = self.validate_files()
        if exe is None:
            return

        sequence = []
        try:
            for item in self.custom_rows:
                colour = item["colour"].get().strip()
                if not re.fullmatch(r"#[0-9a-fA-F]{6}", colour):
                    raise ValueError(f"Invalid colour value: {colour}")
                seconds = float(item["seconds"].get())
                if not 0.1 <= seconds <= 3600:
                    raise ValueError("Each colour duration must be between 0.1 and 3600 seconds.")
                sequence.append((colour[1:], seconds))
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror(APP_TITLE, f"Check the colour and duration values.\n\n{exc}")
            return

        if not sequence:
            messagebox.showwarning(APP_TITLE, "Add at least one colour before starting the custom cycle.")
            return

        self.custom_stop_event = threading.Event()
        self.custom_thread = threading.Thread(
            target=self._custom_cycle_worker, args=(str(exe), sequence, self.custom_stop_event),
            daemon=True
        )
        self.custom_thread.start()
        self.status.set(f"Running custom colour cycle ({len(sequence)} colours).")

    def _custom_cycle_worker(self, exe, sequence, stop_event):
        while not stop_event.is_set():
            for hex_colour, seconds in sequence:
                if stop_event.is_set():
                    break
                try:
                    child = subprocess.Popen(
                        [exe, "colour", "0x" + hex_colour],
                        cwd=str(Path(exe).parent),
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
                    self.custom_child = child
                    child.wait(timeout=10)
                    self.custom_child = None
                except subprocess.TimeoutExpired:
                    try:
                        child.terminate()
                    except Exception:
                        pass
                    self.custom_child = None
                    self.root.after(0, lambda: self.status.set("Custom colour command timed out."))
                    return
                except Exception as exc:
                    self.custom_child = None
                    self.root.after(0, lambda err=str(exc): self.status.set(f"Custom cycle error: {err}"))
                    return

                # Wait in short increments so STOP responds quickly.
                stop_event.wait(seconds)

        self.root.after(0, lambda: self.status.set("Custom colour cycle stopped."))

    def validate_files(self):
        exe = Path(self.exe_path.get().strip().strip('"'))
        if not exe.is_file() or exe.name.lower() != "clevo_keyboardcolour.exe":
            messagebox.showerror(APP_TITLE, "Select the actual CLEVO_KeyboardColour.exe file.")
            return None
        dll = exe.parent / "InsydeDCHU.dll"
        if not dll.is_file():
            messagebox.showerror(APP_TITLE, "InsydeDCHU.dll was not found beside the EXE.\n\n"
                                "Copy it from C:\\Program Files (x86)\\ControlCenter into the same folder.")
            return None
        return exe

    def start(self):
        if self.custom_thread is not None and self.custom_thread.is_alive():
            self.stop()
        if self.process is not None and self.process.poll() is None:
            messagebox.showinfo(APP_TITLE, "An effect is already running. Press STOP first.")
            return
        exe = self.validate_files()
        if exe is None:
            return
        theme = THEMES[self.theme_label.get()]
        speed = str(self.speed.get())
        try:
            # Launch the vendor utility directly; no shell command-string parsing.
            self.process = subprocess.Popen(
                [str(exe), "theme", theme, "--speed", speed],
                cwd=str(exe.parent),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            self.status.set(f"Running: {self.theme_label.get()} at {speed}%")
        except Exception as exc:
            self.process = None
            messagebox.showerror(APP_TITLE, f"Could not start the effect:\n{exc}")

    def stop(self):
        stopped_anything = False
        if self.custom_stop_event is not None:
            self.custom_stop_event.set()
            stopped_anything = True
        if self.custom_child is not None and self.custom_child.poll() is None:
            try:
                self.custom_child.terminate()
            except Exception:
                pass
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
                stopped_anything = True
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"Could not stop the effect:\n{exc}")
        self.process = None
        self.status.set("Effect stopped." if stopped_anything else "No effect is running.")

    def refresh_status(self):
        if self.process is not None and self.process.poll() is not None:
            code = self.process.returncode
            self.process = None
            self.status.set(f"Effect process exited (code {code}).")
        self.root.after(700, self.refresh_status)

    def make_tray_image(self):
        # Small custom RGB keyboard-style icon.
        image = Image.new("RGBA", (64, 64), (16, 19, 27, 255))
        draw = ImageDraw.Draw(image)
        colors = [(255, 70, 120), (255, 170, 60), (80, 220, 150),
                  (70, 170, 255), (170, 100, 255)]
        for i, color in enumerate(colors):
            x = 8 + i * 10
            draw.rounded_rectangle((x, 17, x + 8, 47), radius=3, fill=color)
        draw.rounded_rectangle((7, 10, 57, 53), radius=7, outline=(235, 240, 255), width=2)
        return image

    def show_window(self, icon=None, item=None):
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def exit_app(self, icon=None, item=None):
        self.root.after(0, self._exit_app)

    def _exit_app(self):
        if self.custom_thread is not None and self.custom_thread.is_alive():
            self.stop()
        if self.process is not None and self.process.poll() is None:
            if not messagebox.askyesno(APP_TITLE, "Stop the current keyboard effect and exit Aspire RGB Studio?"):
                return
            self.stop()
        self._allow_exit = True
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()

    def ensure_tray(self):
        if not TRAY_AVAILABLE:
            messagebox.showwarning(
                APP_TITLE,
                "System tray support needs pystray and Pillow.\n\n"
                "Open PowerShell and run:\npy -m pip install pystray pillow"
            )
            self._show_window()
            return False
        if self.tray_icon is None:
            menu = pystray.Menu(
                pystray.MenuItem("Open Aspire RGB Studio", self.show_window, default=True),
                pystray.MenuItem("Exit", self.exit_app)
            )
            self.tray_icon = pystray.Icon(APP_TITLE, self.make_tray_image(), APP_TITLE, menu)
            self.tray_icon.run_detached()
        return True

    def hide_to_tray(self):
        if self.ensure_tray():
            self.root.withdraw()
            self.status.set("Running in system tray. Click the tray icon to reopen.")

    def on_minimize(self, event):
        # Ignore child-widget unmap events; only react when the main window is minimized.
        if event.widget == self.root and self.root.state() == "iconic":
            self.root.after(150, self.hide_to_tray)

if __name__ == "__main__":
    if os.name == "nt" and not is_admin():
        # UAC is needed by the underlying CLEVO utility for WMI access.
        relaunch_as_admin()
    root = tk.Tk()
    app = AspireRGBStudio(root)
    root.mainloop()
