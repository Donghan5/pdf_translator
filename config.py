from pathlib import Path
import sys


# =============================================================================
# Configuration & Constants
# =============================================================================
CHUNK_SIZE = 2000  # Characters per chunk (reduced for NLLB model)
MODEL_NAME = "facebook/nllb-200-distilled-600M"
LOCAL_MODEL_PATH = None  # Set to local path if model is downloaded elsewhere

# =============================================================================
# NLLB-200 Supported Languages
# Full list: https://github.com/facebookresearch/flores/blob/main/flores200/README.md
# =============================================================================
SUPPORTED_LANGUAGES = {
    "en": ("eng_Latn", "English"),
    "ko": ("kor_Hang", "Korean / 한국어"),
    "ja": ("jpn_Jpan", "Japanese / 日本語"),
    "zh": ("zho_Hans", "Chinese (Simplified) / 简体中文"),
    "zh-tw": ("zho_Hant", "Chinese (Traditional) / 繁體中文"),
    "es": ("spa_Latn", "Spanish / Español"),
    "fr": ("fra_Latn", "French / Français"),
    "de": ("deu_Latn", "German / Deutsch"),
    "it": ("ita_Latn", "Italian / Italiano"),
    "pt": ("por_Latn", "Portuguese / Português"),
    "ru": ("rus_Cyrl", "Russian / Русский"),
    "ar": ("arb_Arab", "Arabic / العربية"),
    "hi": ("hin_Deva", "Hindi / हिन्दी"),
    "th": ("tha_Thai", "Thai / ไทย"),
    "vi": ("vie_Latn", "Vietnamese / Tiếng Việt"),
    "id": ("ind_Latn", "Indonesian / Bahasa Indonesia"),
    "nl": ("nld_Latn", "Dutch / Nederlands"),
    "pl": ("pol_Latn", "Polish / Polski"),
    "tr": ("tur_Latn", "Turkish / Türkçe"),
    "uk": ("ukr_Cyrl", "Ukrainian / Українська"),
}

# Default language settings
DEFAULT_SOURCE_LANG = "en"
DEFAULT_TARGET_LANG = "ko"

# Current language settings (can be changed at runtime)
SOURCE_LANG = SUPPORTED_LANGUAGES[DEFAULT_SOURCE_LANG][0]
TARGET_LANG = SUPPORTED_LANGUAGES[DEFAULT_TARGET_LANG][0]


def get_base_path() -> Path:
    """
    Returns the base path for the application.
    When running as a PyInstaller .exe, this is the directory containing the executable.
    When running as a script, this is the script's directory.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


BASE_PATH = get_base_path()
INPUT_DIR = BASE_PATH / "input"
OUTPUT_DIR = BASE_PATH / "output"
PROCESSED_DIR = BASE_PATH / "processed"
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
# Language Selection
# =============================================================================
def get_nllb_code(lang_key: str) -> str:
    """Get NLLB language code from short key."""
    if lang_key in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[lang_key][0]
    raise ValueError(f"Unsupported language: {lang_key}")


def get_language_name(lang_key: str) -> str:
    """Get human-readable language name from short key."""
    if lang_key in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[lang_key][1]
    return lang_key


def set_languages(source: str, target: str):
    """Set source and target languages for translation."""
    global SOURCE_LANG, TARGET_LANG
    SOURCE_LANG = get_nllb_code(source)
    TARGET_LANG = get_nllb_code(target)
    print(f"✓ Languages set: {get_language_name(source)} → {get_language_name(target)}")


def print_supported_languages():
    """Print all supported languages."""
    print("\n📋 Supported Languages:")
    print("-" * 40)
    for key, (code, name) in SUPPORTED_LANGUAGES.items():
        print(f"   {key:6} : {name}")
    print("-" * 40)
