"""
Easy PDF Translator - Local Model Version
Translates PDFs using NLLB-200 model (Offline, Multilingual)
"""

from config import (
    ensure_directories, INPUT_DIR, OUTPUT_DIR, MODEL_NAME,
    SUPPORTED_LANGUAGES, set_languages, print_supported_languages,
    DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG
)
from process import process_pdf

# =============================================================================
# Language Selection
# =============================================================================
def select_language(prompt: str, default: str) -> str:
    """Prompt user to select a language."""
    while True:
        user_input = input(prompt).strip().lower()
        if not user_input:
            return default
        if user_input in SUPPORTED_LANGUAGES:
            return user_input
        print(f"   ❌ Invalid language code: '{user_input}'. Try again.")


def configure_languages():
    """Interactive language configuration."""
    print_supported_languages()
    
    print(f"\n🌐 Current default: {DEFAULT_SOURCE_LANG} → {DEFAULT_TARGET_LANG}")
    print("   Press Enter to use defaults, or type language codes.\n")
    
    source = select_language(
        f"   Source language [{DEFAULT_SOURCE_LANG}]: ", 
        DEFAULT_SOURCE_LANG
    )
    target = select_language(
        f"   Target language [{DEFAULT_TARGET_LANG}]: ", 
        DEFAULT_TARGET_LANG
    )
    
    if source == target:
        print("   ⚠ Source and target languages are the same!")
        return False
    
    set_languages(source, target)
    return True


# =============================================================================
# Main Application
# =============================================================================
def main():
    print("=" * 60)
    print("   Easy PDF + TXT Translator - Local Model Version")
    print(f"   Model: {MODEL_NAME}")
    print("   Multilingual Support Enabled")
    print("=" * 60)

    # Setup directories
    ensure_directories()
    
    # Configure languages
    if not configure_languages():
        input("\nPress Enter to exit...")
        return

    # Scan for PDFs
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    txt_files = list(INPUT_DIR.glob("*.txt"))
    all_files = pdf_files + txt_files

    if not all_files:
        print(f"\n📂 No PDF or TXT files found in '{INPUT_DIR.name}/' folder.")
        print("   Please drop your PDF or TXT files there and run again.")
        input("\nPress Enter to exit...")
        return

    print(f"\n📚 Found {len(all_files)} file(s) to process:")
    for file in all_files:
        print(f"   - {file.name}")

    # Process each PDF
    success_count = 0
    fail_count = 0

    for file_path in all_files:
        print("\n" + "-" * 60)
        if file_path.suffix == ".pdf":
            if process_pdf(file_path):
                success_count += 1
            else:
                fail_count += 1
        elif file_path.suffix == ".txt":
            if process_txt(file_path):
                success_count += 1
            else:
                fail_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("   📊 TRANSLATION COMPLETE")
    print(f"   ✓ Successful: {success_count}")
    print(f"   ✗ Failed: {fail_count}")
    print(f"   📁 Output folder: {OUTPUT_DIR}")
    print("=" * 60)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()