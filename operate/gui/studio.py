"""
Studio Dashboard Window for Self-Operating Computer
Provides comprehensive configuration for custom endpoints, models, visual modes, prompt input, and live logs.
"""
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox


OMNIROUTE_MODELS = [
    "agy/gemini-3.7-flash-low",
    "agy/gemini-3.7-flash-medium",
    "agy/gemini-3.7-flash-high",
    "agy/gemini-3.7-flash-tiered",
    "agy/gemini-pro-agent",
    "agy/gemini-3.1-pro-low",
    "agy/gemini-3.1-flash-lite",
    "agy/gemini-3.6-flash-low",
    "agy/claude-sonnet-4-6",
    "agy/claude-sonnet-4-6-low",
    "agy/claude-sonnet-4-6-medium",
    "agy/claude-sonnet-4-6-high",
    "agy/claude-opus-4-6-thinking",
    "agy/claude-opus-4-6-thinking-low",
    "agy/claude-opus-4-6-thinking-medium",
    "agy/claude-opus-4-6-thinking-high",
    "agy/gpt-oss-120b-medium",
    "no-think/agy/claude-opus-4-6-thinking",
    "no-think/agy/claude-sonnet-4-6",
    "antigravity/gemini-3.7-flash-low",
    "antigravity/gemini-3.7-flash-medium",
    "antigravity/gemini-3.7-flash-high",
    "antigravity/gemini-3.7-flash-tiered",
    "antigravity/gemini-pro-agent",
    "antigravity/gemini-3.1-pro-low",
    "antigravity/gemini-3.1-flash-lite",
    "antigravity/gemini-3.1-flash-image",
    "antigravity/claude-sonnet-4-6",
    "antigravity/claude-sonnet-4-6-low",
    "antigravity/claude-sonnet-4-6-medium",
    "antigravity/claude-sonnet-4-6-high",
    "antigravity/claude-opus-4-6-thinking",
    "antigravity/claude-opus-4-6-thinking-low",
    "antigravity/claude-opus-4-6-thinking-medium",
    "antigravity/claude-opus-4-6-thinking-high",
    "antigravity/gpt-oss-120b-medium",
    "no-think/antigravity/claude-opus-4-6-thinking",
    "no-think/antigravity/claude-sonnet-4-6",
]


# ─── Centralized Theme Constants ─────────────────────────────────────────────
# Single source of truth for every color, typography, and spacing token used by
# the Studio window. The floating overlay mirrors this same palette.
THEME = {
    "bg":            "#121214",
    "card":          "#1e1e24",
    "card_alt":      "#26262d",
    "card_border":   "#2a2a30",
    "input_bg":      "#26262c",
    "primary":       "#6366f1",
    "primary_hover": "#818cf8",
    "accent":        "#06b6d4",
    "accent_hover":  "#22d3ee",
    "danger":        "#dc2626",
    "danger_hover":  "#f87171",
    "success":       "#34d399",
    "success_bg":    "#052e16",
    "running":       "#818cf8",
    "running_bg":    "#1e1b4b",
    "warn":          "#fbbf24",
    "text":          "#fafafa",
    "text_muted":    "#a1a1aa",
    "thumb_bg":      "#16161d",
    "divider":       "#2a2a30",
}

# Log console tag colors (keyed by log level; None is the default)
LOG_COLORS = {
    "info":    "#60a5fa",
    "success": "#34d399",
    "warn":    "#fbbf24",
    "error":   "#f87171",
    "thought": "#c084fc",
    "action":  "#38bdf8",
    None:      "#e4e4e7",
}

# Typography tokens
F_TITLE   = ("Segoe UI", 13, "bold")
F_SECTION = ("Segoe UI", 9, "bold")
F_LABEL   = ("Segoe UI", 8, "bold")
F_BODY    = ("Segoe UI", 9)
F_SMALL   = ("Segoe UI", 8)
F_TINY    = ("Segoe UI", 7)
F_LOG     = ("Consolas", 9)

# Spacing tokens
PAD_CARD  = 14
PAD_ROW   = 8


# ─── Provider Presets ─────────────────────────────────────────────────────────
# Data-driven provider configuration. Each entry describes how the Studio
# pre-fills the Base URL / API Key / Model fields when a preset is chosen.
PROVIDER_CONFIGS = {
    "Google Account (Direct Antigravity)": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "",
        "default_model": "antigravity/gemini-3.7-flash-low",
        "models": OMNIROUTE_MODELS,
    },
    "Local OmniRoute (localhost:20128)": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "http://localhost:20128/v1",
        "default_key": "sk-b6fe217dd1fbeeda-18f222-7107776b",
        "default_model": "agy/gemini-3.7-flash-low",
        "models": OMNIROUTE_MODELS,
    },
    "Custom (OpenAI-compatible)": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "Local Ollama (localhost:11434)": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "http://localhost:11434/v1",
        "default_key": "ollama",
        "default_model": "llava",
        "models": ["llava", "llama3.2-vision", "qwen2.5-vl", "minicpm-v"],
    },
    "Local LM Studio (localhost:1234)": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "http://localhost:1234/v1",
        "default_key": "lm-studio",
        "default_model": "local-model",
        "models": ["local-model"],
    },
    "Local vLLM (localhost:8000)": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "http://localhost:8000/v1",
        "default_key": "none",
        "default_model": "llava",
        "models": ["llava", "qwen2.5-vl"],
    },
    "OpenRouter": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-3.5-sonnet",
        "models": [
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "google/gemini-flash-1.5",
        ],
    },
    "OpenAI Official": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini"],
    },
    "Anthropic Claude": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "",
        "default_model": "claude-3",
        "models": [
            "claude-3-5-sonnet-latest",
            "claude-3-opus-latest",
            "claude-3-haiku-latest",
        ],
    },
    "Google Gemini (API Key)": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-3.1-flash-lite",
        "models": ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"],
    },
    "Alibaba Qwen": {
        "env_key": "OPENAI_API_KEY",
        "default_url": "",
        "default_model": "qwen-vl",
        "models": ["qwen-vl", "qwen2.5-vl-72b"],
    },
}

# Canonical ordering of presets in the selector (drives the combobox values).
PRESET_ORDER = [
    "Google Account (Direct Antigravity)",
    "Local OmniRoute (localhost:20128)",
    "Custom (OpenAI-compatible)",
    "Local Ollama (localhost:11434)",
    "Local LM Studio (localhost:1234)",
    "Local vLLM (localhost:8000)",
    "OpenRouter",
    "OpenAI Official",
    "Anthropic Claude",
    "Google Gemini (API Key)",
    "Alibaba Qwen",
]


class _ModernProgressBar(tk.Canvas):
    """Canvas-based progress bar with a rounded fill and centered % label.

    Replaces the default themed progressbar so the bar matches the Studio's
    custom color palette exactly.
    """

    def __init__(self, master, bg=None, track=None, fill=None, border=None,
                 height=20, label_font=None, **kwargs):
        super().__init__(
            master,
            height=height,
            bg=bg or THEME["input_bg"],
            highlightthickness=1,
            highlightbackground=border or THEME["card_border"],
            bd=0,
            **kwargs,
        )
        self._track = track or THEME["input_bg"]
        self._fill = fill or THEME["accent"]
        self._border = border or THEME["card_border"]
        self._label = "0%"
        self._fraction = 0.0
        self._label_font = label_font or ("Segoe UI", 7, "bold")
        self.bind("<Configure>", lambda _e: self._redraw())

    def set_fraction(self, fraction, label=None):
        try:
            self._fraction = max(0.0, min(1.0, float(fraction)))
        except (TypeError, ValueError):
            self._fraction = 0.0
        if label is not None:
            self._label = str(label)
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        # Track (full width)
        self.create_rectangle(0, 0, w, h, fill=self._track, outline="")
        fill_w = int(w * self._fraction)
        if fill_w > 0:
            self.create_rectangle(0, 0, fill_w, h, fill=self._fill, outline="")
        # Centered percentage label — light text reads on both track and fill
        self.create_text(
            w // 2, h // 2, text=self._label,
            fill=THEME["text"], font=self._label_font,
        )


class StudioWindow(tk.Tk):
    def __init__(self, on_start=None, on_stop=None):
        super().__init__()
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self.is_running = False

        self.title("Self-Operating Computer Studio")
        self.geometry("880x720")
        self.minsize(780, 600)
        self.configure(bg=THEME["bg"])

        self._init_theme()
        self._build_ui()
        self._load_saved_config()

    def _init_theme(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Dark theme color tokens — sourced from the centralized THEME dict
        self.c_bg = THEME["bg"]
        self.c_card = THEME["card"]
        self.c_card_border = THEME["card_border"]
        self.c_primary = THEME["primary"]
        self.c_primary_hover = THEME["primary_hover"]
        self.c_accent = THEME["accent"]
        self.c_accent_hover = THEME["accent_hover"]
        self.c_danger = THEME["danger"]
        self.c_danger_hover = THEME["danger_hover"]
        self.c_success = THEME["success"]
        self.c_text = THEME["text"]
        self.c_text_muted = THEME["text_muted"]
        self.c_input_bg = THEME["input_bg"]

    def _build_ui(self):
        # Header Bar
        header = tk.Frame(self, bg=self.c_card, height=54, bd=0)
        header.pack(fill="x", side="top")

        title_label = tk.Label(
            header,
            text="⚡ Self-Operating Computer",
            font=("Segoe UI", 13, "bold"),
            fg=self.c_text,
            bg=self.c_card,
            padx=18,
            pady=14,
        )
        title_label.pack(side="left", padx=(0, 8))

        self.badge_status = tk.Label(
            header,
            text="Ready",
            font=F_LABEL,
            fg=THEME["success"],
            bg=THEME["success_bg"],
            padx=12,
            pady=4,
        )
        self.badge_status.pack(side="right", padx=16, pady=12)

        # Subtle divider between header and content
        tk.Frame(self, bg=THEME["divider"], height=1).pack(fill="x")

        # Main Scrollable / Paned Content
        self.main_container = tk.Frame(self, bg=self.c_bg, padx=20, pady=16)
        self.main_container.pack(fill="both", expand=True)
        main_container = self.main_container

        # Top Grid: Config & Setup Card
        config_card = tk.LabelFrame(
            main_container,
            text=" Provider & Model Configuration ",
            font=("Segoe UI", 10, "bold"),
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief="solid",
            padx=16,
            pady=14,
        )
        config_card.pack(fill="x", pady=(0, 16))

        # Preset Provider Selector
        row0 = tk.Frame(config_card, bg=self.c_card)
        row0.pack(fill="x", pady=3)

        tk.Label(
            row0,
            text="Provider Preset:",
            font=("Segoe UI", 8, "bold"),
            fg=self.c_text_muted,
            bg=self.c_card,
            width=16,
            anchor="w",
        ).pack(side="left")

        self.preset_var = tk.StringVar(value="Custom (OpenAI-compatible)")
        presets = list(PRESET_ORDER)
        self.preset_menu = ttk.Combobox(
            row0,
            textvariable=self.preset_var,
            values=presets,
            state="readonly",
            width=32,
        )
        self.preset_menu.pack(side="left", fill="x", expand=True, padx=(4, 10))
        self.preset_menu.bind("<<ComboboxSelected>>", self._on_preset_change)

        save_btn = tk.Button(
            row0,
            text="Save to .env",
            font=("Segoe UI", 8),
            bg="#27272a",
            fg=self.c_text,
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._save_config_to_env,
        )
        save_btn.pack(side="right")

        # Base URL Field
        row1 = tk.Frame(config_card, bg=self.c_card)
        row1.pack(fill="x", pady=3)

        tk.Label(
            row1,
            text="API Base URL:",
            font=("Segoe UI", 8, "bold"),
            fg=self.c_text_muted,
            bg=self.c_card,
            width=16,
            anchor="w",
        ).pack(side="left")

        self.base_url_entry = tk.Entry(
            row1,
            font=("Segoe UI", 9),
            bg=self.c_input_bg,
            fg=self.c_text,
            insertbackground=self.c_text,
            bd=1,
            relief="flat",
            highlightthickness=0,
        )
        self.base_url_entry.pack(side="left", fill="x", expand=True, padx=(4, 0), ipady=5)

        # API Key Field
        row2 = tk.Frame(config_card, bg=self.c_card)
        row2.pack(fill="x", pady=3)

        tk.Label(
            row2,
            text="API Key:",
            font=("Segoe UI", 8, "bold"),
            fg=self.c_text_muted,
            bg=self.c_card,
            width=16,
            anchor="w",
        ).pack(side="left")

        self.api_key_entry = tk.Entry(
            row2,
            font=("Segoe UI", 9),
            bg=self.c_input_bg,
            fg=self.c_text,
            insertbackground=self.c_text,
            show="•",
            bd=1,
            relief="flat",
            highlightthickness=0,
        )
        self.api_key_entry.pack(side="left", fill="x", expand=True, padx=(4, 6), ipady=5)

        self.show_key_var = tk.BooleanVar(value=False)
        self.show_key_btn = tk.Checkbutton(
            row2,
            text="Show",
            variable=self.show_key_var,
            command=self._toggle_show_key,
            bg=self.c_card,
            fg=self.c_text_muted,
            selectcolor=self.c_input_bg,
            activebackground=self.c_card,
            activeforeground=self.c_text,
            bd=0,
        )
        self.show_key_btn.pack(side="right")

        # Model Name & Grounding Strategy
        row3 = tk.Frame(config_card, bg=self.c_card)
        row3.pack(fill="x", pady=3)

        tk.Label(
            row3,
            text="Model Identifier:",
            font=("Segoe UI", 8, "bold"),
            fg=self.c_text_muted,
            bg=self.c_card,
            width=16,
            anchor="w",
        ).pack(side="left")

        self.model_entry = ttk.Combobox(
            row3,
            font=("Segoe UI", 9),
            values=OMNIROUTE_MODELS,
        )
        self.model_entry.pack(side="left", fill="x", expand=True, padx=(4, 10))

        tk.Label(
            row3,
            text="Grounding:",
            font=("Segoe UI", 8, "bold"),
            fg=self.c_text_muted,
            bg=self.c_card,
        ).pack(side="left", padx=(0, 4))

        self.mode_var = tk.StringVar(value="Direct Coordinates (Recommended)")
        self.mode_menu = ttk.Combobox(
            row3,
            textvariable=self.mode_var,
            values=["Direct Coordinates (Recommended)", "OCR Grounding", "Set-of-Mark (SoM)"],
            state="readonly",
            width=28,
        )
        self.mode_menu.pack(side="left")

        # Objective Prompt Card
        prompt_card = tk.LabelFrame(
            main_container,
            text=" Objective Prompt ",
            font=("Segoe UI", 10, "bold"),
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief="solid",
            padx=16,
            pady=14,
        )
        prompt_card.pack(fill="x", pady=(0, 16))

        self.prompt_text = tk.Text(
            prompt_card,
            height=4,
            font=("Segoe UI", 9),
            bg=self.c_input_bg,
            fg=self.c_text,
            insertbackground=self.c_text,
            bd=1,
            padx=12,
            pady=8,
        )
        self.prompt_text.pack(fill="x", pady=(0, 12))
        self.prompt_text.insert("1.0", "Open Google Chrome and search for latest AI news")

        # Action Bar in Prompt Card
        action_row = tk.Frame(prompt_card, bg=self.c_card)
        action_row.pack(fill="x")

        tk.Label(
            action_row,
            text="Max Steps:",
            font=("Segoe UI", 8, "bold"),
            fg=self.c_text_muted,
            bg=self.c_card,
        ).pack(side="left", padx=(0, 4))

        self.steps_spin = tk.Spinbox(
            action_row,
            from_=1,
            to=50,
            width=4,
            font=("Segoe UI", 8),
            bg=self.c_input_bg,
            fg=self.c_text,
            bd=0,
        )
        self.steps_spin.delete(0, "end")
        self.steps_spin.insert(0, "10")
        self.steps_spin.pack(side="left", padx=(0, 16))

        self.overlay_var = tk.BooleanVar(value=True)
        self.overlay_check = tk.Checkbutton(
            action_row,
            text="Mini Floating Bar during run",
            variable=self.overlay_var,
            bg=self.c_card,
            fg=self.c_text,
            selectcolor=self.c_input_bg,
            activebackground=self.c_card,
            activeforeground=self.c_text,
            bd=0,
        )
        self.overlay_check.pack(side="left")

        self.start_btn = tk.Button(
            action_row,
            text="▶ Run Objective",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_primary,
            fg="#ffffff",
            activebackground=self.c_primary_hover,
            activeforeground="#ffffff",
            bd=0,
            padx=20,
            pady=10,
            cursor="hand2",
            command=self._handle_start,
        )
        self.start_btn.pack(side="right")

        # Execution Progress Card — custom canvas-based bar matching the palette
        progress_card = tk.LabelFrame(
            main_container,
            text=" Execution Progress ",
            font=F_SECTION,
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief="solid",
            padx=16,
            pady=12,
        )
        progress_card.pack(fill="x", pady=(0, 16))

        progress_row = tk.Frame(progress_card, bg=self.c_card)
        progress_row.pack(fill="x")

        self.progress_status_label = tk.Label(
            progress_row,
            text="Idle — waiting to start",
            font=F_SMALL,
            fg=self.c_text_muted,
            bg=self.c_card,
            anchor="w",
        )
        self.progress_status_label.pack(side="left", padx=(0, 12))

        self.progress_bar = _ModernProgressBar(
            progress_row,
            bg=self.c_card,
            track=self.c_input_bg,
            fill=self.c_accent,
            border=self.c_card_border,
            height=20,
        )
        self.progress_bar.pack(side="right", fill="x", expand=True)

        # Live Execution Console Card
        log_card = tk.LabelFrame(
            main_container,
            text=" Live Activity & Visual Inspector ",
            font=F_SECTION,
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief="solid",
            padx=14,
            pady=12,
        )
        log_card.pack(fill="both", expand=True)

        # Console header: title + auto-scroll toggle + clear
        log_header = tk.Frame(log_card, bg=self.c_card)
        log_header.pack(fill="x", pady=(0, 6))

        tk.Label(
            log_header,
            text="Console",
            font=F_LABEL,
            fg=self.c_text_muted,
            bg=self.c_card,
        ).pack(side="left")

        self._log_follow = True
        self.log_follow_btn = tk.Label(
            log_header,
            text="⌖ Auto-scroll",
            font=F_LABEL,
            fg=self.c_accent,
            bg=self.c_card,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.log_follow_btn.pack(side="right")
        self.log_follow_btn.bind("<Button-1>", lambda _e: self._toggle_log_follow())

        clear_btn = tk.Button(
            log_header,
            text="Clear",
            font=F_TINY,
            bg=self.c_input_bg,
            fg=self.c_text_muted,
            activebackground=self.c_card_border,
            activeforeground=self.c_text,
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._clear_log,
        )
        clear_btn.pack(side="right", padx=(0, 6))

        # Split: console (left, expanding) + screenshot thumbnail (right)
        log_split = tk.Frame(log_card, bg=self.c_card)
        log_split.pack(fill="both", expand=True)

        self.log_console = scrolledtext.ScrolledText(
            log_split,
            bg=self.c_input_bg,
            fg="#e4e4e7",
            insertbackground="#e4e4e7",
            font=F_LOG,
            bd=1,
            padx=10,
            pady=10,
        )
        self.log_console.pack(side="left", fill="both", expand=True)

        # Vertical divider between console and thumbnail
        tk.Frame(log_split, bg=self.c_card_border, width=1).pack(side="left", fill="y", padx=(8, 8))

        # Screenshot thumbnail panel
        thumb_panel = tk.Frame(log_split, bg=self.c_card, width=300)
        thumb_panel.pack(side="right", fill="y")
        thumb_panel.pack_propagate(False)

        tk.Label(
            thumb_panel,
            text="Latest Screenshot",
            font=F_LABEL,
            fg=self.c_text_muted,
            bg=self.c_card,
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.thumb_label = tk.Label(
            thumb_panel,
            text="📷\n\nNo capture yet\n\nUpdates each step",
            font=F_BODY,
            fg=self.c_text_muted,
            bg=THEME["thumb_bg"],
            justify="center",
        )
        self.thumb_label.pack(fill="both", expand=True)
        self._thumb_photo = None

        # Tags for colored logs — refined for contrast
        self.log_console.tag_config("info", foreground=LOG_COLORS["info"])
        self.log_console.tag_config("success", foreground=LOG_COLORS["success"])
        self.log_console.tag_config("warn", foreground=LOG_COLORS["warn"])
        self.log_console.tag_config("error", foreground=LOG_COLORS["error"])
        self.log_console.tag_config("thought", foreground=LOG_COLORS["thought"])
        self.log_console.tag_config("action", foreground=LOG_COLORS["action"])

        # Configure custom tag for status text
        self.log_console.tag_config("status", foreground="#f4f4f5", font=("Consolas", 9, "bold"))

        # Google OAuth Panel (collapsible)
        self._build_oauth_panel(main_container)

        self._oauth_panel = None

    def _toggle_show_key(self):
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="•")

    def _build_oauth_panel(self, parent):
        """Build the Google OAuth connection panel at the bottom of the dashboard."""
        oauth_card = tk.LabelFrame(
            parent,
            text=" Google Account ",
            font=("Segoe UI", 10, "bold"),
            fg=self.c_text,
            bg=self.c_card,
            bd=1,
            relief="solid",
            padx=16,
            pady=12,
        )
        oauth_card.pack(fill="x", pady=(12, 0), side="bottom")

        # Status row
        status_row = tk.Frame(oauth_card, bg=self.c_card)
        status_row.pack(fill="x", pady=(0, 4))

        self.oauth_status_label = tk.Label(
            status_row,
            text="⚪ Not Connected",
            font=("Segoe UI", 8),
            fg=self.c_text_muted,
            bg=self.c_card,
        )
        self.oauth_status_label.pack(side="left")

        self.oauth_disconnect_btn = tk.Button(
            status_row,
            text="Disconnect",
            font=("Segoe UI", 7),
            bg="#3f3f46",
            fg=self.c_text_muted,
            activebackground="#52525b",
            activeforeground=self.c_text,
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._oauth_disconnect,
        )
        # Hidden by default until connected

        # Action row
        action_row = tk.Frame(oauth_card, bg=self.c_card)
        action_row.pack(fill="x")

        self.oauth_connect_btn = tk.Button(
            action_row,
            text="🔗 Connect Google Account",
            font=("Segoe UI", 9, "bold"),
            bg="#4285F4",
            fg="#ffffff",
            activebackground="#3367d6",
            activeforeground="#ffffff",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._oauth_open_consent,
        )
        self.oauth_connect_btn.pack(side="left", padx=(0, 8))

        self.oauth_code_entry = tk.Entry(
            action_row,
            font=("Segoe UI", 8),
            bg=self.c_input_bg,
            fg=self.c_text,
            insertbackground=self.c_text,
            bd=0,
            relief="flat",
        )
        self.oauth_code_entry.insert(0, "Paste authorization code or callback URL here...")
        self.oauth_code_entry.bind("<FocusIn>", self._oauth_code_focus_in)
        self.oauth_code_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)

        self.oauth_exchange_btn = tk.Button(
            action_row,
            text="Exchange",
            font=("Segoe UI", 8),
            bg="#27272a",
            fg=self.c_text,
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._oauth_exchange_code,
        )
        self.oauth_exchange_btn.pack(side="right")

        # Check if already authenticated on startup
        self.after(500, self._oauth_check_existing)

    def _oauth_code_focus_in(self, event=None):
        """Clear placeholder text on focus."""
        current = self.oauth_code_entry.get()
        if current.startswith("Paste authorization"):
            self.oauth_code_entry.delete(0, "end")

    def _oauth_check_existing(self):
        """Check if there's an existing saved token on startup."""
        try:
            from operate.config import Config
            oauth = Config().google_oauth
            if oauth and oauth.is_authenticated():
                email = oauth.get_user_email() or "Authenticated"
                self.oauth_status_label.config(
                    text=f"🟢 Connected: {email}",
                    fg="#34d399",
                )
                self.oauth_disconnect_btn.pack(side="right", padx=(8, 0))
                self.log_message("Google Account: previously authenticated token found.", "success")
        except Exception:
            pass

    def _oauth_open_consent(self):
        """Open the Google consent page in the user's browser."""
        try:
            from operate.config import Config
            oauth = Config().google_oauth
            if not oauth:
                self.log_message("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env", "error")
                return
            if not oauth.client_id:
                self.log_message("Missing GOOGLE_CLIENT_ID in .env. Cannot open consent page.", "error")
                return
            url = oauth.open_consent_in_browser()
            self.log_message("Google consent page opened in browser. Paste the authorization code below.", "info")
        except Exception as e:
            self.log_message(f"OAuth error: {e}", "error")

    def _oauth_exchange_code(self):
        """Exchange the pasted code for tokens."""
        code_input = self.oauth_code_entry.get().strip()
        if not code_input or code_input.startswith("Paste authorization"):
            self.log_message("Please paste the authorization code first.", "warn")
            return
        try:
            from operate.config import Config
            oauth = Config().google_oauth
            if not oauth:
                self.log_message("Google OAuth not initialized.", "error")
                return
            result = oauth.exchange_code_for_tokens(code_input)
            email = oauth.get_user_email() or "Connected"
            self.oauth_status_label.config(
                text=f"🟢 Connected: {email}",
                fg="#34d399",
            )
            self.oauth_disconnect_btn.pack(side="right", padx=(8, 0))
            self.oauth_code_entry.delete(0, "end")
            self.log_message(f"Google Account connected: {email}", "success")
        except Exception as e:
            self.log_message(f"Token exchange failed: {e}", "error")

    def _oauth_disconnect(self):
        """Revoke and clear Google credentials."""
        try:
            from operate.config import Config
            oauth = Config().google_oauth
            if oauth:
                oauth.revoke_and_logout()
            self.oauth_status_label.config(
                text="⚪ Not Connected",
                fg=self.c_text_muted,
            )
            self.oauth_disconnect_btn.pack_forget()
            self.log_message("Google Account disconnected.", "info")
        except Exception as e:
            self.log_message(f"Disconnect error: {e}", "error")

    def _on_preset_change(self, event=None):
        """Pre-fill Base URL / API Key / Model from the centralized PROVIDER_CONFIGS."""
        preset = self.preset_var.get()
        cfg = PROVIDER_CONFIGS.get(preset, {})

        # "Custom" is fully user-supplied — leave existing fields untouched.
        if preset == "Custom (OpenAI-compatible)":
            return

        base_url = cfg.get("default_url", "")
        api_key = cfg.get("default_key", "")
        model = cfg.get("default_model", "")

        self.base_url_entry.delete(0, "end")
        self.base_url_entry.insert(0, base_url)

        self.api_key_entry.delete(0, "end")
        self.api_key_entry.insert(0, api_key)

        if cfg.get("models"):
            self.model_entry["values"] = list(cfg["models"])
        if model:
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, model)

        # OmniRoute: try to discover live models from the running server
        if preset == "Local OmniRoute (localhost:20128)":
            try:
                import urllib.request, json
                req = urllib.request.Request(
                    "http://localhost:20128/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    m_data = json.loads(resp.read().decode())
                    live_models = [m["id"] for m in m_data.get("data", []) if "id" in m]
                    if live_models:
                        self.model_entry["values"] = live_models
                        self.log_message(f"Discovered {len(live_models)} live models from OmniRoute.", "info")
            except Exception:
                pass

    def _load_saved_config(self):
        base_url = os.getenv("OPENAI_API_BASE_URL", "")
        api_key = os.getenv("OPENAI_API_KEY", "")
        model_name = os.getenv("OPENAI_MODEL_NAME", "gemini-3.1-flash-lite")

        self.base_url_entry.delete(0, "end")
        self.base_url_entry.insert(0, base_url)

        self.api_key_entry.delete(0, "end")
        self.api_key_entry.insert(0, api_key)

        self.model_entry.delete(0, "end")
        self.model_entry.insert(0, model_name)

        self.log_message("Self-Operating Computer Studio ready.", "info")
        if base_url:
            self.log_message(f"Configured Base URL: {base_url}", "info")
        self.log_message(f"Active Model: {model_name}", "info")

    def _save_config_to_env(self):
        base_url = self.base_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        model_name = self.model_entry.get().strip()

        # Update current process environment
        if base_url:
            os.environ["OPENAI_API_BASE_URL"] = base_url
        elif "OPENAI_API_BASE_URL" in os.environ:
            del os.environ["OPENAI_API_BASE_URL"]

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

        if model_name:
            os.environ["OPENAI_MODEL_NAME"] = model_name

        # Save to .env
        env_lines = []
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    sline = line.strip()
                    if (
                        sline.startswith("OPENAI_API_BASE_URL=")
                        or sline.startswith("OPENAI_API_KEY=")
                        or sline.startswith("OPENAI_MODEL_NAME=")
                    ):
                        continue
                    env_lines.append(line)

        if base_url:
            env_lines.append(f"OPENAI_API_BASE_URL='{base_url}'\n")
        if api_key:
            env_lines.append(f"OPENAI_API_KEY='{api_key}'\n")
        if model_name:
            env_lines.append(f"OPENAI_MODEL_NAME='{model_name}'\n")

        with open(".env", "w", encoding="utf-8") as f:
            f.writelines(env_lines)

        self.log_message("Configuration saved to .env file.", "success")
        messagebox.showinfo("Saved", "Settings successfully saved to .env")

    def log_message(self, text, tag=None):
        self.log_console.insert("end", text + "\n", tag)
        if getattr(self, "_log_follow", True):
            self.log_console.see("end")

    # ------------------------------------------------------------------
    # Execution progress + screenshot thumbnail (called from app.py)
    # ------------------------------------------------------------------

    def update_progress(self, step, max_steps, status=None):
        """Advance the progress bar to ``step`` of ``max_steps``."""
        try:
            total = int(max_steps) if max_steps else 0
        except (TypeError, ValueError):
            total = 0
        try:
            cur = int(step) if step is not None else 0
        except (TypeError, ValueError):
            cur = 0
        frac = (cur / total) if total > 0 else 0.0
        label = f"Step {cur}/{total}" if total else "—"
        self.progress_bar.set_fraction(frac, label)
        if status:
            self.progress_status_label.config(text=str(status))

    def finish_progress(self, text="Completed"):
        """Fill the progress bar and mark the run as finished."""
        self.progress_bar.set_fraction(1.0, "✓ Done")
        if text:
            self.progress_status_label.config(text=str(text))

    def update_screenshot(self, image_path):
        """Refresh the thumbnail panel with the latest screenshot."""
        if not image_path:
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(image_path)
            img.thumbnail((290, 170))
            self._thumb_photo = ImageTk.PhotoImage(img)
            self.thumb_label.config(image=self._thumb_photo, text="")
        except Exception:
            # Keep the placeholder if the image cannot be loaded
            self.thumb_label.config(
                image="", text="📷\n\nNo capture yet\n\nUpdates each step"
            )

    def _toggle_log_follow(self):
        """Toggle auto-scroll (follow) mode for the console."""
        self._log_follow = not self._log_follow
        if self._log_follow:
            self.log_follow_btn.config(text="⌖ Auto-scroll", fg=self.c_accent)
            self.log_console.see("end")
        else:
            self.log_follow_btn.config(text="⌖ Paused", fg=self.c_text_muted)

    def _clear_log(self):
        """Clear the console."""
        self.log_console.delete("1.0", "end")

    def get_full_model_identifier(self):
        raw_model = self.model_entry.get().strip() or "gpt-4o"
        mode = self.mode_var.get()
        if "SoM" in mode:
            return f"{raw_model}-som"
        elif "Direct" in mode:
            return f"{raw_model}-direct"
        else:
            return f"{raw_model}-ocr"

    def _handle_start(self):
        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Prompt Missing", "Please enter an objective prompt.")
            return

        model = self.get_full_model_identifier()
        try:
            max_steps = int(self.steps_spin.get())
        except ValueError:
            max_steps = 10

        use_overlay = self.overlay_var.get()

        # Update environment values before start
        base_url = self.base_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        if base_url:
            os.environ["OPENAI_API_BASE_URL"] = base_url
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

        self.badge_status.config(text="Running", fg=THEME["running"], bg=THEME["running_bg"])
        self.start_btn.config(
            text="■ Stop",
            bg=self.c_danger,
            activebackground=self.c_danger_hover,
            command=self._handle_stop,
        )
        self.is_running = True

        self.log_message(f"\n--- Starting Objective ---", "info")
        self.log_message(f"Objective: {prompt}", "info")
        self.log_message(f"Model: {model} | Max Steps: {max_steps}", "info")

        if self.on_start_callback:
            self.on_start_callback(
                prompt=prompt,
                model=model,
                max_steps=max_steps,
                use_overlay=use_overlay,
            )

    def _handle_stop(self):
        if self.on_stop_callback:
            self.on_stop_callback()
        self.on_run_finished(summary="Stopped by user")

    def on_run_finished(self, summary=""):
        self.is_running = False
        self.badge_status.config(text="Ready", fg=THEME["success"], bg=THEME["success_bg"])
        self.start_btn.config(
            text="▶ Run Objective",
            bg=self.c_primary,
            activebackground=self.c_primary_hover,
            command=self._handle_start,
        )
        if summary:
            self.log_message(f"Result: {summary}", "success")
