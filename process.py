import shutil
from pathlib import Path

from config import OUTPUT_DIR, PROCESSED_DIR
from parse import extract_text_from_pdf
from translate import translate_text

# =============================================================================
# File Processing
# =============================================================================
def process_pdf(pdf_path: Path, api_key: str) -> bool:
    """
    Process a single PDF: extract, translate, save, and move.
    Returns True on success, False on failure.
    """
    try:
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            print(f"   ⚠ No text extracted from {pdf_path.name}. Skipping.")
            return False

        # Translate
        print(f"\n🌐 Translating {pdf_path.name}...")
        translated_text = translate_text(api_key, text)

        # Save output
        output_filename = pdf_path.stem + "_translated.txt"
        output_path = OUTPUT_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {pdf_path.stem} - Translated\n\n")
            f.write(translated_text)

        print(f"   💾 Saved: {output_path.name}")

        # Move original to processed
        dest_path = PROCESSED_DIR / pdf_path.name
        shutil.move(str(pdf_path), str(dest_path))
        print(f"   📁 Moved original to: processed/{pdf_path.name}")

        return True

    except Exception as e:
        print(f"\n   ❌ Failed to process {pdf_path.name}: {e}")
        return False
