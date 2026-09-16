import os

# Ensure matplotlib uses a local writable directory for font cache to avoid permission errors
os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", ".matplotlib"),
)
