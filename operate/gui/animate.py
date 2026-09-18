"""
Animation Engine for Self-Operating Computer Studio GUI
Provides smooth interpolation, easing curves, color transitions, and a reusable
AnimationLoop that drives 60fps widget updates via tkinter's after() scheduler.
"""
import math
import colorsys


# ---------------------------------------------------------------------------
# Interpolation helpers
# ---------------------------------------------------------------------------

def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between *a* and *b* by factor *t* (0.0 → 1.0)."""
    return a + (b - a) * t


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Easing curves  (t goes 0 → 1, output goes 0 → 1)
# ---------------------------------------------------------------------------

def ease_linear(t: float) -> float:
    return t


def ease_in_out_cubic(t: float) -> float:
    """Smooth acceleration then deceleration."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


def ease_out_expo(t: float) -> float:
    """Fast start, smooth landing."""
    return 1.0 if t >= 1.0 else 1 - pow(2, -10 * t)


def ease_out_cubic(t: float) -> float:
    return 1 - pow(1 - t, 3)


def ease_out_back(t: float) -> float:
    """Slight overshoot then settle – good for slide-ins."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_out_sine(t: float) -> float:
    """Smooth sine-based breathing curve."""
    return -(math.cos(math.pi * t) - 1) / 2


# ---------------------------------------------------------------------------
# Color interpolation
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert '#RRGGBB' to (r, g, b) ints 0-255."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (r, g, b) ints 0-255 to '#rrggbb'."""
    return f"#{int(clamp(r, 0, 255)):02x}{int(clamp(g, 0, 255)):02x}{int(clamp(b, 0, 255)):02x}"


def color_lerp(hex_a: str, hex_b: str, t: float) -> str:
    """Interpolate between two hex colors channel-by-channel."""
    r1, g1, b1 = _hex_to_rgb(hex_a)
    r2, g2, b2 = _hex_to_rgb(hex_b)
    return _rgb_to_hex(
        int(lerp(r1, r2, t)),
        int(lerp(g1, g2, t)),
        int(lerp(b1, b2, t)),
    )


def color_brighten(hex_color: str, factor: float = 0.3) -> str:
    """Brighten a hex color by *factor* (0.0 = no change, 1.0 = white)."""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(
        int(r + (255 - r) * factor),
        int(g + (255 - g) * factor),
        int(b + (255 - b) * factor),
    )


def color_darken(hex_color: str, factor: float = 0.15) -> str:
    """Darken a hex color by *factor* (0.0 = no change, 1.0 = black)."""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(
        int(r * (1 - factor)),
        int(g * (1 - factor)),
        int(b * (1 - factor)),
    )


# ---------------------------------------------------------------------------
# AnimationLoop – the core scheduler
# ---------------------------------------------------------------------------

class AnimationLoop:
    """
    Drives smooth widget animations using tkinter's after() scheduler.

    Parameters
    ----------
    widget : tk widget
        Any tkinter widget (used for .after() scheduling).
    duration_ms : int
        Total animation duration in milliseconds.
    on_tick : callable(t: float)
        Called each frame with *t* eased from 0.0 → 1.0.
    easing : callable, optional
        Easing function applied to raw progress. Defaults to ease_in_out_cubic.
    on_complete : callable, optional
        Called once when the animation finishes.
    fps : int
        Target frames per second (default 60).
    """

    _FRAME_MS = 16  # ~60fps

    def __init__(self, widget, duration_ms: int, on_tick, *,
                 easing=None, on_complete=None, fps: int = 60):
        self.widget = widget
        self.duration_ms = max(1, duration_ms)
        self.on_tick = on_tick
        self.easing = easing or ease_in_out_cubic
        self.on_complete = on_complete
        self._frame_ms = max(1, 1000 // fps)
        self._elapsed = 0
        self._after_id = None
        self._cancelled = False

    def start(self):
        """Begin the animation."""
        self._elapsed = 0
        self._cancelled = False
        self._step()
        return self

    def cancel(self):
        """Cancel the running animation."""
        self._cancelled = True
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    @property
    def running(self) -> bool:
        return not self._cancelled and self._elapsed < self.duration_ms

    def _step(self):
        if self._cancelled:
            return
        try:
            if not self.widget.winfo_exists():
                return
        except Exception:
            return

        raw_t = clamp(self._elapsed / self.duration_ms)
        eased_t = self.easing(raw_t)

        try:
            self.on_tick(eased_t)
        except Exception:
            self._cancelled = True
            return

        self._elapsed += self._frame_ms

        if self._elapsed > self.duration_ms:
            # Final tick at t=1.0
            try:
                self.on_tick(self.easing(1.0))
            except Exception:
                pass
            if self.on_complete:
                try:
                    self.on_complete()
                except Exception:
                    pass
            return

        try:
            self._after_id = self.widget.after(self._frame_ms, self._step)
        except Exception:
            pass


class PulseLoop:
    """
    Continuous breathing / pulsing animation that loops until cancelled.

    Parameters
    ----------
    widget : tk widget
    cycle_ms : int
        Duration of one full pulse cycle (bright → dim → bright).
    on_tick : callable(t: float)
        Called each frame with *t* oscillating 0.0 → 1.0 → 0.0 per cycle.
    """

    _FRAME_MS = 16

    def __init__(self, widget, cycle_ms: int, on_tick):
        self.widget = widget
        self.cycle_ms = max(1, cycle_ms)
        self.on_tick = on_tick
        self._after_id = None
        self._cancelled = False
        self._elapsed = 0

    def start(self):
        self._cancelled = False
        self._elapsed = 0
        self._step()
        return self

    def cancel(self):
        self._cancelled = True
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _step(self):
        if self._cancelled:
            return
        try:
            if not self.widget.winfo_exists():
                return
        except Exception:
            return

        # Sine wave oscillation: 0 → 1 → 0 over one cycle
        raw_t = (self._elapsed % self.cycle_ms) / self.cycle_ms
        wave_t = ease_in_out_sine(raw_t * 2) if raw_t < 0.5 else ease_in_out_sine((1 - raw_t) * 2)

        try:
            self.on_tick(wave_t)
        except Exception:
            self._cancelled = True
            return

        self._elapsed += self._FRAME_MS
        try:
            self._after_id = self.widget.after(self._FRAME_MS, self._step)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# High-level helper: animated hover binding
# ---------------------------------------------------------------------------

def bind_hover(widget, normal_bg: str, hover_bg: str, duration_ms: int = 200,
               easing=None):
    """
    Bind smooth hover color transitions to a widget.
    On <Enter>, animate bg from *normal_bg* → *hover_bg*.
    On <Leave>, animate bg from current → *normal_bg*.
    Also sets cursor='hand2' for interactive feel.
    """
    _state = {"anim": None}
    easing = easing or ease_in_out_cubic

    def _animate_to(target_bg):
        if _state["anim"]:
            _state["anim"].cancel()
        try:
            current_bg = widget.cget("bg") or widget.cget("background")
        except Exception:
            current_bg = normal_bg

        def on_tick(t):
            widget.configure(bg=color_lerp(current_bg, target_bg, t))

        _state["anim"] = AnimationLoop(
            widget, duration_ms, on_tick, easing=easing
        ).start()

    def on_enter(e):
        _animate_to(hover_bg)

    def on_leave(e):
        _animate_to(normal_bg)

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")
    widget.configure(cursor="hand2")


def bind_press_sink(widget, darken_factor: float = 0.15, duration_ms: int = 80):
    """
    On <ButtonPress-1>, briefly darken the widget bg, then spring back.
    """
    _state = {"anim": None, "original_bg": None}

    def on_press(e):
        if _state["anim"]:
            _state["anim"].cancel()
        try:
            current_bg = widget.cget("bg") or widget.cget("background")
        except Exception:
            return
        _state["original_bg"] = current_bg
        dark = color_darken(current_bg, darken_factor)
        widget.configure(bg=dark)

        def restore():
            if _state["original_bg"]:
                widget.configure(bg=_state["original_bg"])

        _state["anim"] = AnimationLoop(
            widget, duration_ms, lambda t: None, on_complete=restore
        ).start()

    widget.bind("<ButtonPress-1>", on_press, add="+")


# ---------------------------------------------------------------------------
# High-level helper: focus glow for input fields
# ---------------------------------------------------------------------------

def bind_focus_glow(widget, normal_border: str = "#27272a",
                    focus_border: str = "#3b82f6", duration_ms: int = 200):
    """
    Animate the highlight border color of an Entry/Text on focus/blur.
    """
    _state = {"anim": None}

    # ttk widgets don't support highlight* options; ttkbootstrap styles their focus instead
    try:
        widget.cget("highlightcolor")
    except Exception:
        return

    def _animate_border(target):
        if _state["anim"]:
            _state["anim"].cancel()
        try:
            current = widget.cget("highlightcolor") or normal_border
        except Exception:
            current = normal_border

        def on_tick(t):
            c = color_lerp(current, target, t)
            widget.configure(highlightcolor=c)

        _state["anim"] = AnimationLoop(
            widget, duration_ms, on_tick, easing=ease_in_out_cubic
        ).start()

    def on_focus(e):
        _animate_border(focus_border)

    def on_blur(e):
        _animate_border(normal_border)

    widget.bind("<FocusIn>", on_focus, add="+")
    widget.bind("<FocusOut>", on_blur, add="+")
    widget.configure(highlightthickness=1, highlightcolor=normal_border)
