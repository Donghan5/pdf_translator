import shutil
from pathlib import Path

from config import OUTPUT_DIR, PROCESSED_DIR
from parse import extract_text_from_pdf, extract_text_from_txt, split_into_chunks
from translate import translate_text


# =============================================================================
# File Processing
# =============================================================================
def process_txt(txt_path: Path) -> bool:
    try:
        text = extract_text_from_txt(txt_path)
        if not text.strip():
            print(f"   No text extracted from {txt_path.name}. Skipping.")
            return False

        # Wrap as single page for chunking
        pages = [{"page": 1, "text": text}]
        chunks = split_into_chunks(pages, filename=txt_path.name)
        if not chunks:
            print(f"   No chunks created from {txt_path.name}. Skipping.")
            return False

        print(f"\n   Translating {txt_path.name}...")
        translated_text = translate_text(chunks)

        output_filename = txt_path.stem + "_translated.txt"
        output_path = OUTPUT_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {txt_path.stem} - Translated\n\n")
            f.write(translated_text)

        print(f"   Saved: {output_path.name}")

        dest_path = PROCESSED_DIR / txt_path.name
        shutil.move(str(txt_path), str(dest_path))
        print(f"   Moved original to: processed/{txt_path.name}")

        return True

    except Exception as e:
        print(f"   Failed to process {txt_path.name}: {e}")
        return False


def process_pdf(pdf_path: Path) -> bool:
    """
    Process a single PDF: extract, chunk, translate, save, and move.
    Returns True on success, False on failure.
    """
    try:
        # Extract text per page
        pages = extract_text_from_pdf(pdf_path)
        total_chars = sum(len(p["text"]) for p in pages)
        if total_chars == 0:
            print(f"   No text extracted from {pdf_path.name}. Skipping.")
            return False

        # Smart chunking with metadata
        chunks = split_into_chunks(pages, filename=pdf_path.name)
        if not chunks:
            print(f"   No chunks created from {pdf_path.name}. Skipping.")
            return False

        # Translate
        print(f"\n   Translating {pdf_path.name}...")
        translated_text = translate_text(chunks)

        # Save output
        output_filename = pdf_path.stem + "_translated.txt"
        output_path = OUTPUT_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {pdf_path.stem} - Translated\n\n")
            f.write(translated_text)

        print(f"   Saved: {output_path.name}")

        # Move original to processed
        dest_path = PROCESSED_DIR / pdf_path.name
        shutil.move(str(pdf_path), str(dest_path))
        print(f"   Moved original to: processed/{pdf_path.name}")

        return True

    except Exception as e:
        print(f"\n   Failed to process {pdf_path.name}: {e}")
        return False
