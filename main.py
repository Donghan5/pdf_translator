"""
Easy PDF Translator - Zero-Cost Version
Translates PDFs using Google Gemini 1.5 Flash API (Free Tier)
"""

from config import ensure_directories, get_api_key, INPUT_DIR, OUTPUT_DIR
from process import process_pdf

# =============================================================================
# Main Application
# =============================================================================
def main():
    print("=" * 60)
    print("   Easy PDF Translator - Zero Cost Version")
    print("   Using Google Gemini 1.5 Flash (Free Tier)")
    print("=" * 60)

    # Setup
    ensure_directories()
    api_key = get_api_key()

    # Scan for PDFs
    pdf_files = list(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"\n📂 No PDF files found in '{INPUT_DIR.name}/' folder.")
        print("   Please drop your PDF files there and run again.")
        input("\nPress Enter to exit...")
        return

    print(f"\n📚 Found {len(pdf_files)} PDF file(s) to process:")
    for pdf in pdf_files:
        print(f"   - {pdf.name}")

    # Process each PDF
    success_count = 0
    fail_count = 0

    for pdf_path in pdf_files:
        print("\n" + "-" * 60)
        if process_pdf(pdf_path, api_key):
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