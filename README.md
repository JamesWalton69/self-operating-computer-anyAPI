<h1 align="center">⚡ Self-Operating Computer (anyAPI + Studio GUI)</h1>

<p align="center">
  <strong>An autonomous framework enabling multimodal AI models to operate computers with human-like vision and actions.</strong>
</p>

<p align="center">
  Using the same inputs and outputs as a human operator, the AI views your screen, thinks through the visual layout, and executes native mouse and keyboard actions to achieve your objective.
</p>

<div align="center">
  <img src="https://github.com/OthersideAI/self-operating-computer/blob/main/readme/self-operating-computer.png" width="750" style="margin: 10px; border-radius: 8px;" />
</div>

---

## 🌟 Key Highlights & Modern Features

- 🖥️ **Desktop Studio GUI**: Comprehensive dark-themed dashboard to select providers, models, visual grounding modes, prompts, and view live colored action logs.
- 💊 **Floating Mini Overlay**: Borderless, semi-transparent status pill that stays on top during execution, showing real-time thoughts, current step progress, and an emergency **Stop** button.
- 🌐 **Universal Custom AnyAPI Support**: Connect **any** OpenAI-compatible API endpoint (OmniRoute, OpenRouter, vLLM, Ollama, LM Studio, Groq, Together AI, DeepSeek, Claude, Google Gemini, Qwen).
- 🔑 **Google Code Assist OAuth**: Browser-based OAuth 2.0 authentication powered by Google's Code Assist service for seamless multimodal Gemini execution.
- ⚡ **Multi-Action Operating System Engine**: Supports left click, double click, right click, middle click, fast typing, clipboard pasting, smooth mouse dragging, mouse wheel scrolling, explicit waiting, and application launching (`launch notepad`).
- 🛡️ **Automatic 503 & Rate Limit Recovery**: Built-in exponential backoff retry engine with jitter that automatically recovers from server busy (`503`) and rate limit (`429`) errors.
- 🎯 **Flexible Grounding Modes**:
  - **Direct Vision Coordinates** (`-direct`): Native multimodal pixel estimation for fast response times.
  - **EasyOCR Element Targeting** (`-ocr`): Automatically maps text on screen to exact pixel coordinates.
  - **Set-of-Mark Prompting** (`-som`): YOLOv8-powered bounding box tagging.

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install requirements in your Python environment:

```bash
git clone https://github.com/JamesWalton69/self-operating-computer-anyAPI.git
cd self-operating-computer-anyAPI

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Launch the Desktop Studio GUI

Run the GUI with any of the following methods:

**On Windows:**
Double-click `run_studio.bat`, or run:
```bash
operate --gui
# or directly:
operate-gui
```

**Via Python module:**
```bash
python -m operate.gui.app
```

---

## 💻 Terminal CLI Usage

You can also run directly from the command line:

```bash
# Interactive mode (prompts for objective)
operate

# Direct prompt execution
operate --prompt "Open Notepad and type Hello World"

# Specific model
operate -m agy/gemini-3.7-flash-low-direct --prompt "Search for AI news on Google Chrome"
```

---

## ⚙️ Configuration & Custom Providers (`.env`)

Configure your environment variables in `.env` or set them directly in the Studio GUI:

### Local OmniRoute AI Gateway (`localhost:20128`)
```ini
OPENAI_API_BASE_URL="http://127.0.0.1:20128/v1"
OPENAI_API_KEY="sk-b6fe217dd1fbeeda-18f222-7107776b"
OPENAI_MODEL_NAME="agy/gemini-3.7-flash-low"
```
Run with:
```bash
operate -m agy/gemini-3.7-flash-low-direct
```

### OpenRouter
```ini
OPENAI_API_BASE_URL="https://openrouter.ai/api/v1"
OPENAI_API_KEY="sk-or-v1-your-openrouter-key"
OPENAI_MODEL_NAME="anthropic/claude-3.5-sonnet"
```

### Local Ollama / LM Studio / vLLM
```ini
# Ollama
OPENAI_API_BASE_URL="http://localhost:11434/v1"
OPENAI_API_KEY="ollama"
OPENAI_MODEL_NAME="llava"

# LM Studio
OPENAI_API_BASE_URL="http://localhost:1234/v1"
OPENAI_API_KEY="lm-studio"
```

### Google Gemini (Direct API & OAuth)
```ini
GOOGLE_API_KEY="your-google-ai-studio-key"
# Or activate Google Code Assist OAuth:
GEMINI_OAUTH="1"
```

---

## 🎯 Grounding Mode Suffixes

Add a suffix to any model identifier to control how coordinates are derived:

| Suffix | Mode | Description |
| :--- | :--- | :--- |
| `*-direct` | **Direct Coordinates** *(Recommended)* | The model outputs normalized screen percentages directly. Fastest and lowest token footprint. |
| `*-ocr` | **OCR Text Grounding** | The model identifies text to click; EasyOCR resolves the bounding box on screen. |
| `*-som` | **Set-of-Mark (YOLOv8)** | YOLOv8 visually overlays bounding boxes and numbered markers on the screenshot. |

---

## 🛡️ Robust Retry Engine

All model requests automatically route through an exponential backoff retry handler to prevent failed jobs during provider surges:

- **Handled Statuses**: `503 Service Unavailable` / `Model Overloaded`, `429 Too Many Requests`, `502 Bad Gateway`, `504 Gateway Timeout`.
- **Configurable Settings** in `.env`:
  ```ini
  OPERATE_MAX_RETRIES=5
  OPERATE_RETRY_BASE_DELAY=2.0
  OPERATE_RETRY_MAX_DELAY=60.0
  ```

---

## 🎙️ Optional Voice Mode (`--voice`)

Control your computer with your voice using Whisper:

```bash
pip install -r requirements-audio.txt
operate --voice
```

*Note: Requires `portaudio` on macOS (`brew install portaudio`) or Ubuntu/Debian (`sudo apt install portaudio19-dev python3-pyaudio`).*

---

## 🖥️ Platform Compatibility

- **Windows 10 / 11**: Fully supported (mss-accelerated screen capture, native Windows mouse/keyboard automation, `run_studio.bat`).
- **macOS**: Supported (requires Accessibility and Screen Recording permissions in System Preferences).
- **Linux**: Supported (X11 environment with `scrot` and `xdotool`).

---

## 🤝 Contributing & Community

Contributions, issues, and feature requests are welcomed!
- See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
- Original project inspired by [OthersideAI/self-operating-computer](https://github.com/OthersideAI/self-operating-computer).

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
