"""
Centralized theme constants for the Self-Operating Computer GUI.
Keeps all colors, fonts, and sizing tokens in one place.
"""

# ── Color Palette (Refined dark theme with indigo/cyan accents) ────────────────
# Base / background
BG = "#121214"           # Deeper, premium background
CARD = "#1e1e24"         # Card/container with subtle depth
CARD_BORDER = "#2a2a30"  # More subtle card borders
INPUT_BG = "#18181b"     # Input/text backgrounds

# Text
TEXT = "#fafafa"
TEXT_MUTED = "#a1a1aa"

# Primary / accent
PRIMARY = "#6366f1"      # Indigo - modern, unique
PRIMARY_HOVER = "#818cf8"
ACCENT = "#06b6d4"       # Cyan for secondary highlights

# Status colors
GREEN = "#34d399"
GREEN_BG = "#064e3b"
BLUE = "#3b82f6"
BLUE_HOVER = "#60a5fa"
AMBER = "#f59e0b"
RED = "#f87171"
RED_BG = "#7f1d1d"

# Log tag colors
LOG_INFO = "#60a5fa"
LOG_SUCCESS = "#34d399"
LOG_WARN = "#fbbf24"
LOG_ERROR = "#f87171"
LOG_THOUGHT = "#c084fc"
LOG_ACTION = "#38bdf8"
LOG_DEFAULT = "#e4e4e7"

# Badges / status dot
BADGE_READY_FG = "#34d399"
BADGE_READY_BG = "#064e3b"
BADGE_RUNNING_FG = "#60a5fa"
BADGE_RUNNING_BG = "#1e3a8a"
BADGE_ERROR_FG = "#f87171"
BADGE_ERROR_BG = "#450a0a"
BADGE_STOPPED_FG = "#fbbf24"
BADGE_STOPPED_BG = "#422006"

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"

FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_HEADING = (FONT_FAMILY, 10, "bold")
FONT_LABEL = (FONT_FAMILY, 9)
FONT_LABEL_BOLD = (FONT_FAMILY, 9, "bold")
FONT_SMALL = (FONT_FAMILY, 8)
FONT_SMALL_BOLD = (FONT_FAMILY, 8, "bold")
FONT_LOG = (FONT_MONO, 9)
FONT_MONO_MEDIUM = (FONT_MONO, 9)

# ── Sizing ────────────────────────────────────────────────────────────────────
CARD_PADDING = 14
ROW_SPACING = 10
DIVIDER_HEIGHT = 1
BUTTON_PADDING_X = 16
BUTTON_PADDING_Y = 10

# ── Overlay (floating pill) ────────────────────────────────────────────────────
OVERLAY_WIDTH = 400
OVERLAY_HEIGHT = 64
OVERLAY_BG = "#1e1e24"
OVERLAY_BORDER = "#33333b"
OVERLAY_TEXT = "#f4f4f5"
OVERLAY_TEXT_MUTED = "#a1a1aa"
OVERLAY_GREEN = "#34d399"
OVERLAY_BLUE = "#3b82f6"
OVERLAY_AMBER = "#f59e0b"
OVERLAY_RED = "#f87171"
OVERLAY_STOP_BG = "#dc2626"
OVERLAY_STOP_HOVER = "#f87171"
OVERLAY_EXPAND_BG = "#2a2a30"
OVERLAY_EXPAND_HOVER = "#33333b"
