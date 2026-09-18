"""
Mini Floating Overlay Controller for Self-Operating Computer
Provides an always-on-top, draggable status pill with emergency stop during execution.
"""
import tkinter as tk
from tkinter import ttk
from operate.gui.animate import (
    AnimationLoop, PulseLoop, bind_hover, bind_press_sink,
    color_lerp, color_brighten, ease_out_expo, ease_in_out_cubic, lerp
)

# Centralized color palette matching the Studio theme (zinc + indigo/cyan accents)
_OVERLAY_BG = "#1e1e24"
_OVERLAY_BORDER = "#33333b"
_OVERLAY_TEXT = "#f4f4f5"
_OVERLAY_TEXT_MUTED = "#a1a1aa"
_OVERLAY_GREEN = "#34d399"
_OVERLAY_BLUE = "#3b82f6"
_OVERLAY_AMBER = "#f59e0b"
_OVERLAY_RED = "#f87171"
_OVERLAY_STOP_BG = "#dc2626"
_OVERLAY_STOP_HOVER = "#f87171"
_OVERLAY_EXPAND_BG = "#2a2a30"
_OVERLAY_EXPAND_HOVER = "#33333b"


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

        # Dimensions & screen positioning (top-right by default)
        # Increased from 380x56 to 400x64 for better visibility on high-DPI displays
        self.width = 400
        self.height = 64
        screen_w = self.winfo_screenwidth()
        x = max(20, screen_w - self.width - 40)
        y = 30

        self._final_x = x
        self._final_y = y
        self.geometry(f"{self.width}x{self.height}+{screen_w + 20}+{y}")

        try:
            self.wm_attributes("-alpha", 0.0)  # Start transparent for animation
        except Exception:
            pass

        # Dragging mechanics
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._pulse_anim = None

        self._build_ui()
        self._bind_drag()

        # Slide-in animation
        def slide_in_tick(t):
            cur_x = int(lerp(screen_w + 20, self._final_x, t))
            self.geometry(f"+{cur_x}+{self._final_y}")
            try:
                self.wm_attributes("-alpha", lerp(0.0, 0.94, t))
            except Exception:
                pass

        AnimationLoop(self, 400, slide_in_tick, easing=ease_out_expo).start()

    def _build_ui(self):
        # Container frame with subtle border
        self.container = tk.Frame(
            self,
            bg=_OVERLAY_BG,
            highlightthickness=1,
            highlightbackground=_OVERLAY_BORDER,
            bd=0,
        )
        self.container.pack(fill="both", expand=True)

        # Left section: Status indicator & action text
        self.left_box = tk.Frame(self.container, bg=_OVERLAY_BG)
        self.left_box.pack(side="left", fill="both", expand=True, padx=(14, 6), pady=8)

        # Status row
        status_row = tk.Frame(self.left_box, bg=_OVERLAY_BG)
        status_row.pack(anchor="w", fill="x")

        self.status_dot = tk.Label(
            status_row,
            text="●",
            font=("Segoe UI", 14, "bold"),
            fg=_OVERLAY_GREEN,
            bg=_OVERLAY_BG,
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_label = tk.Label(
            status_row,
            text="Operating...",
            font=("Segoe UI", 9, "bold"),
            fg=_OVERLAY_TEXT,
            bg=_OVERLAY_BG,
        )
        self.status_label.pack(side="left", padx=(0, 4))

        self.step_label = tk.Label(
            status_row,
            text="[Step 1/10]",
            font=("Segoe UI", 8, "bold"),
            fg=_OVERLAY_TEXT_MUTED,
            bg=_OVERLAY_BG,
        )
        self.step_label.pack(side="left")

        # Action detail text
        self.action_label = tk.Label(
            self.left_box,
            text="Initializing agent...",
            font=("Segoe UI", 9),
            fg=_OVERLAY_TEXT,
            bg=_OVERLAY_BG,
            anchor="w",
        )
        self.action_label.pack(anchor="w", fill="x", pady=(4, 0))

        # Right section: Control buttons
        self.right_box = tk.Frame(self.container, bg=_OVERLAY_BG)
        self.right_box.pack(side="right", fill="y", padx=(4, 12), pady=8)

        # Stop button (Emergency)
        self.stop_btn = tk.Button(
            self.right_box,
            text="■ Stop",
            font=("Segoe UI", 9, "bold"),
            bg=_OVERLAY_STOP_BG,
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._handle_stop,
        )
        self.stop_btn.pack(side="right", padx=4)

        # Expand to studio button
        self.expand_btn = tk.Button(
            self.right_box,
            text="⤢ Studio",
            font=("Segoe UI", 9),
            bg=_OVERLAY_EXPAND_BG,
            fg=_OVERLAY_TEXT,
            activebackground=_OVERLAY_EXPAND_HOVER,
            activeforeground="#ffffff",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._handle_expand,
        )
        self.expand_btn.pack(side="right", padx=4)

        bind_hover(self.stop_btn, _OVERLAY_STOP_BG, _OVERLAY_STOP_HOVER, duration_ms=150)
        bind_press_sink(self.stop_btn)
        bind_hover(self.expand_btn, _OVERLAY_EXPAND_BG, _OVERLAY_EXPAND_HOVER, duration_ms=150)
        bind_press_sink(self.expand_btn)

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
        if self._pulse_anim:
            self._pulse_anim.cancel()
            self._pulse_anim = None

        if status == "thinking":
            base_color = _OVERLAY_AMBER
            self.status_dot.config(fg=base_color)
            self.status_label.config(text="Thinking...")
            bright_color = color_brighten(base_color, 0.3)
            self._pulse_anim = PulseLoop(
                self, 1500, lambda t: self.status_dot.config(fg=color_lerp(base_color, bright_color, t))
            ).start()
        elif status == "acting":
            base_color = _OVERLAY_BLUE
            self.status_dot.config(fg=base_color)
            self.status_label.config(text="Acting...")
            bright_color = color_brighten(base_color, 0.3)
            self._pulse_anim = PulseLoop(
                self, 1000, lambda t: self.status_dot.config(fg=color_lerp(base_color, bright_color, t))
            ).start()
        elif status == "done":
            self.status_dot.config(fg=_OVERLAY_GREEN)
            self.status_label.config(text="Completed")
        elif status == "error":
            self.status_dot.config(fg=_OVERLAY_RED)
            self.status_label.config(text="Error")
            self.shake()
        else:
            self.status_dot.config(fg=_OVERLAY_GREEN)
            self.status_label.config(text="Active")

        if step is not None:
            total_text = f"/{max_steps}" if max_steps else ""
            self.step_label.config(text=f"[Step {step}{total_text}]")

        if message:
            # Truncate if long
            disp_msg = message if len(message) <= 60 else message[:57] + "..."
            self.action_label.config(text=disp_msg)

    def _handle_stop(self):
        self.status_dot.config(fg=_OVERLAY_RED)
        self.status_label.config(text="Stopping...")
        self.action_label.config(text="Emergency stop triggered.")
        if self.on_stop_callback:
            self.on_stop_callback()

    def _handle_expand(self):
        if self.on_expand_callback:
            self.on_expand_callback()

    def shake(self):
        """Quick horizontal shake on error."""
        import math
        base_x = self.winfo_x()
        base_y = self.winfo_y()
        def on_tick(t):
            offset = int(5 * math.sin(t * math.pi * 6) * (1 - t))
            self.geometry(f"+{base_x + offset}+{base_y}")
        AnimationLoop(self, 300, on_tick, easing=lambda t: t).start()

    def slide_out_and_destroy(self):
        """Slide out to the right and fade before destroying."""
        start_x = self.winfo_x()
        start_y = self.winfo_y()
        screen_w = self.winfo_screenwidth()
        def on_tick(t):
            new_x = int(lerp(start_x, screen_w + 20, t))
            self.geometry(f"+{new_x}+{start_y}")
            try:
                self.wm_attributes('-alpha', lerp(0.94, 0.0, t))
            except Exception:
                pass
        AnimationLoop(self, 250, on_tick, easing=ease_out_expo,
                      on_complete=self.destroy).start()
