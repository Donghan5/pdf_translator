import shutil
from pathlib import Path

from config import OUTPUT_DIR, PROCESSED_DIR
from parse import extract_text_from_pdf, extract_text_from_txt
from translate import translate_text

# =============================================================================
# File Processing
# =============================================================================
def process_txt(txt_path: Path) -> bool:
    try:
        text = extract_text_from_txt(txt_path)
        if not text.strip():
            print(f"   ⚠ No text extracted from {txt_path.name}. Skipping.")
            return False
        print(f"\nTranslating {txt_path.name}...")
        translated_text = translate_text(text)

        output_filename = txt_path.stem + "_translated.txt"
        output_path = OUTPUT_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {txt_path.stem} - Translated\n\n")
            f.write(translated_text)
        
        print(f"   💾 Saved: {output_path.name}")

        dest_path = PROCESSED_DIR / txt_path.name
        shutil.move(str(txt_path), str(dest_path))
        print(f"   📁 Moved original to: processed/{txt_path.name}")

        return True

    except Exception as e:
        print(f"   ❌ Failed to process {txt_path.name}: {e}")
        return False

def process_pdf(pdf_path: Path) -> bool:
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

        # Translate (no api_key needed - using local model)
        print(f"\n🌐 Translating {pdf_path.name}...")
        translated_text = translate_text(text)

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
