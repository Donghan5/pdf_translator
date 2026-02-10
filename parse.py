import pdfplumber
from pathlib import Path
from config import CHUNK_SIZE

# =============================================================================
# PDF Text Extraction
# =============================================================================
def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF page by page using pdfplumber.
    Memory efficient: processes one page at a time.
    """
    print(f"\n📄 Extracting text from: {pdf_path.name}")
    full_text = []
    pages_with_images = []
    empty_pages = []

    """
    Skipping all images
    """
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            full_text.append(text)
            
            # check images
            images = page.images if hasattr(page, "images") else []
            if images:
                pages_with_images.append(i)
            
            if len(text.strip()) < 50:
                empty_pages.append(i)
            
            print(f"   Page {i}/{total_pages} extracted")

    if pages_with_images:
        print(f"\n   Pages with images: {pages_with_images} (skipped, text only!)")
    if empty_pages:
        print(f"\n   Empty pages: {empty_pages} (may be image-based or scanned)")

    combined_text = "\n\n".join(full_text)
    print(f"   Total characters extracted: {len(combined_text):,}")
    return combined_text

def extract_text_from_txt(txt_path: Path) -> str:
    print(f"\nReading text from: {txt_path.name}")
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()
    print(f" Total characters read: {len(text):,}")
    return text


# =============================================================================
# Text Chunking
# =============================================================================
def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """
    Split text into manageable chunks for API calls.
    Tries to split at paragraph boundaries when possible.
    """
    if not text:
        return []

    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph would exceed limit, save current chunk
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        current_chunk += para + "\n\n"

        # If single paragraph exceeds limit, force split
        while len(current_chunk) > chunk_size:
            chunks.append(current_chunk[:chunk_size].strip())
            current_chunk = current_chunk[chunk_size:]

    # Add remaining text
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    print(f"   Split into {len(chunks)} chunks for translation")
    return chunks
