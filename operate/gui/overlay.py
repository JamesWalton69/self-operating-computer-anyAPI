"""
Mini Floating Overlay Controller for Self-Operating Computer
Provides an always-on-top, draggable status pill with emergency stop during execution.
"""
import tkinter as tk
from tkinter import ttk


class FloatingOverlay(tk.Toplevel):
    def __init__(self, master, on_stop=None, on_pause=None, on_expand=None):
        super().__init__(master)
        self.on_stop_callback = on_stop
        self.on_pause_callback = on_pause
        self.on_expand_callback = on_expand
        self.is_paused = False

        # Window properties
        self.title("Operating Computer Active")
        self.overrideredirect(True)  # Frameless
        self.wm_attributes("-topmost", True)  # Always on top
        try:
            self.wm_attributes("-alpha", 0.94)  # Semi-transparent
        except Exception:
            pass

        # Dimensions & screen positioning (top-right by default)
        self.width = 380
        self.height = 56
        screen_w = self.winfo_screenwidth()
        x = max(20, screen_w - self.width - 40)
        y = 30
        self.geometry(f"{self.width}x{self.height}+{x}+{y}")

        # Dragging mechanics
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build_ui()
        self._bind_drag()

    def _build_ui(self):
        # Container frame
        self.container = tk.Frame(
            self,
            bg="#18181b",
            highlightthickness=1,
            highlightbackground="#3f3f46",
            bd=0,
        )
        self.container.pack(fill="both", expand=True)

        # Left section: Status indicator & action text
        self.left_box = tk.Frame(self.container, bg="#18181b")
        self.left_box.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=6)

        # Status row
        status_row = tk.Frame(self.left_box, bg="#18181b")
        status_row.pack(anchor="w", fill="x")

        self.status_dot = tk.Label(
            status_row,
            text="●",
            font=("Segoe UI", 11, "bold"),
            fg="#22c55e",
            bg="#18181b",
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_label = tk.Label(
            status_row,
            text="Operating...",
            font=("Segoe UI", 9, "bold"),
            fg="#f4f4f5",
            bg="#18181b",
        )
        self.status_label.pack(side="left")

        self.step_label = tk.Label(
            status_row,
            text="[Step 1/10]",
            font=("Segoe UI", 8),
            fg="#a1a1aa",
            bg="#18181b",
        )
        self.step_label.pack(side="left", padx=(8, 0))

        # Action detail text
        self.action_label = tk.Label(
            self.left_box,
            text="Initializing agent...",
            font=("Segoe UI", 8),
            fg="#e4e4e7",
            bg="#18181b",
            anchor="w",
        )
        self.action_label.pack(anchor="w", fill="x", pady=(2, 0))

        # Right section: Control buttons
        self.right_box = tk.Frame(self.container, bg="#18181b")
        self.right_box.pack(side="right", fill="y", padx=(4, 10), pady=8)

        # Stop button (Emergency)
        self.stop_btn = tk.Button(
            self.right_box,
            text="■ Stop",
            font=("Segoe UI", 8, "bold"),
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._handle_stop,
        )
        self.stop_btn.pack(side="right", padx=3)

        # Expand to studio button
        self.expand_btn = tk.Button(
            self.right_box,
            text="⤢ Studio",
            font=("Segoe UI", 8),
            bg="#27272a",
            fg="#e4e4e7",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
            command=self._handle_expand,
        )
        self.expand_btn.pack(side="right", padx=3)

    def _bind_drag(self):
        for widget in (self, self.container, self.left_box, self.action_label, self.status_label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, event):
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _on_drag(self, event):
        new_x = event.x_root - self._drag_start_x
        new_y = event.y_root - self._drag_start_y
        self.geometry(f"+{new_x}+{new_y}")

    def update_status(self, status, message, step=None, max_steps=None):
        if status == "thinking":
            self.status_dot.config(fg="#f59e0b")
            self.status_label.config(text="Thinking...")
        elif status == "acting":
            self.status_dot.config(fg="#3b82f6")
            self.status_label.config(text="Acting...")
        elif status == "done":
            self.status_dot.config(fg="#10b981")
            self.status_label.config(text="Completed")
        elif status == "error":
            self.status_dot.config(fg="#ef4444")
            self.status_label.config(text="Error")
        else:
            self.status_dot.config(fg="#22c55e")
            self.status_label.config(text="Active")

        if step is not None:
            total_text = f"/{max_steps}" if max_steps else ""
            self.step_label.config(text=f"[Step {step}{total_text}]")

        if message:
            # Truncate if long
            disp_msg = message if len(message) <= 45 else message[:42] + "..."
            self.action_label.config(text=disp_msg)

    def _handle_stop(self):
        self.status_dot.config(fg="#ef4444")
        self.status_label.config(text="Stopping...")
        self.action_label.config(text="Emergency stop triggered.")
        if self.on_stop_callback:
            self.on_stop_callback()

    def _handle_expand(self):
        if self.on_expand_callback:
            self.on_expand_callback()
