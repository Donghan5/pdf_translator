import os
from pathlib import Path
import sys

from dotenv import load_dotenv

# =============================================================================
# Load Environment Variables
# =============================================================================
load_dotenv()

# =============================================================================
# Groq API Configuration
# =============================================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL_TRANSLATE = os.getenv("GROQ_MODEL_TRANSLATE", "llama-3.1-8b-instant")
GROQ_MODEL_QA = os.getenv("GROQ_MODEL_QA", "llama-3.3-70b-versatile")

# =============================================================================
# C++ Server Configuration
# =============================================================================
CPP_SERVER_HOST = os.getenv("CPP_SERVER_HOST", "localhost")
CPP_SERVER_PORT = int(os.getenv("CPP_SERVER_PORT", "50051"))

# =============================================================================
# Chunking Configuration
# =============================================================================
CHUNK_TOKEN_SIZE = int(os.getenv("CHUNK_TOKEN_SIZE", "1500"))
CHUNK_OVERLAP_SENTENCES = int(os.getenv("CHUNK_OVERLAP_SENTENCES", "2"))

# =============================================================================
# Supported Languages
# =============================================================================
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ko": "Korean",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "uk": "Ukrainian",
}

# =============================================================================
# Language Settings
# =============================================================================
DEFAULT_SOURCE_LANG = os.getenv("DEFAULT_SOURCE_LANG", "en")
DEFAULT_TARGET_LANG = os.getenv("DEFAULT_TARGET_LANG", "ko")

SOURCE_LANG = DEFAULT_SOURCE_LANG
TARGET_LANG = DEFAULT_TARGET_LANG

# =============================================================================
# Paths
# =============================================================================

def get_base_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


BASE_PATH = get_base_path()
INPUT_DIR = BASE_PATH / "input"
OUTPUT_DIR = BASE_PATH / "output"
PROCESSED_DIR = BASE_PATH / "processed"

# =============================================================================
# Directory Setup
# =============================================================================

def ensure_directories():
    for directory in [INPUT_DIR, OUTPUT_DIR, PROCESSED_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"  Directory ready: {directory.name}/")

# =============================================================================
# Language Helpers
# =============================================================================

def get_language_name(lang_key: str) -> str:
    return SUPPORTED_LANGUAGES.get(lang_key, lang_key)


def set_languages(source: str, target: str):
    global SOURCE_LANG, TARGET_LANG
    SOURCE_LANG = source
    TARGET_LANG = target
    print(f"  Languages set: {get_language_name(source)} -> {get_language_name(target)}")


def print_supported_languages():
    print("\n  Supported Languages:")
    print("-" * 40)
    for key, name in SUPPORTED_LANGUAGES.items():
        print(f"   {key:6} : {name}")
    print("-" * 40)
