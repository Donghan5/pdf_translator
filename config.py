import os
from pathlib import Path
import sys
from dotenv import load_dotenv, set_key
from tkinter import Tk
from tkinter import simpledialog, messagebox


# =============================================================================
# Configuration & Constants
# =============================================================================
CHUNK_SIZE = 2500  # Characters per chunk (2000-3000 range)
MODEL_NAME = "gemini-2.0-flash"
MAX_RETRIES = 5
INITIAL_BACKOFF = 20  # seconds


def get_base_path() -> Path:
    """
    Returns the base path for the application.
    When running as a PyInstaller .exe, this is the directory containing the executable.
    When running as a script, this is the script's directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


BASE_PATH = get_base_path()
INPUT_DIR = BASE_PATH / "input"
OUTPUT_DIR = BASE_PATH / "output"
PROCESSED_DIR = BASE_PATH / "processed"
ENV_FILE = BASE_PATH / ".env"
SHOW_USAGE_STATS = True

# =============================================================================
# Directory Setup
# =============================================================================
def ensure_directories():
    """Create required directories if they don't exist."""
    for directory in [INPUT_DIR, OUTPUT_DIR, PROCESSED_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory ready: {directory.name}/")


# =============================================================================
# API Key Management
# =============================================================================
def get_api_key() -> str:
    """
    Load API key from .env file.
    If not found, prompt user via tkinter dialog and save it.
    """
    load_dotenv(ENV_FILE)
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("⚠ API Key not found. Launching configuration window...")
        api_key = prompt_for_api_key()

        if api_key:
            # Create .env file if it doesn't exist
            ENV_FILE.touch(exist_ok=True)
            set_key(str(ENV_FILE), "GOOGLE_API_KEY", api_key)
            print("✓ API Key saved to .env file.")
        else:
            messagebox.showerror("Error", "API Key is required to run the application.")
            sys.exit(1)

    return api_key


def prompt_for_api_key() -> str:
    """Display a tkinter dialog to get API key from user."""
    root = Tk()
    root.withdraw()  # Hide main window

    api_key = simpledialog.askstring(
        "Google Gemini API Key Required",
        "Please paste your Google Gemini API Key:\n\n"
        "(Get one free at: https://aistudio.google.com/app/apikey)",
        show='*'  # Mask input like a password
    )

    root.destroy()
    return api_key.strip() if api_key else None
