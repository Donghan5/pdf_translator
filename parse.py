import hashlib

import pdfplumber
from pathlib import Path

import nltk
from nltk.tokenize import sent_tokenize

from config import CHUNK_TOKEN_SIZE, CHUNK_OVERLAP_SENTENCES

# Ensure NLTK sentence tokenizer data is available
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)


# =============================================================================
# PDF Text Extraction
# =============================================================================
def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Extract text from PDF page by page using pdfplumber.
    Returns list of {"page": int, "text": str} dicts for page tracking.
    """
    print(f"\n   Extracting text from: {pdf_path.name}")
    pages = []
    pages_with_images = []
    empty_pages = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            pages.append({"page": i, "text": text})

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

    total_chars = sum(len(p["text"]) for p in pages)
    print(f"   Total characters extracted: {total_chars:,}")
    return pages


def extract_text_from_txt(txt_path: Path) -> str:
    """Read text from a .txt file."""
    print(f"\n   Reading text from: {txt_path.name}")
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()
    print(f"   Total characters read: {len(text):,}")
    return text


# =============================================================================
# Helpers
# =============================================================================
def _estimate_tokens(text: str) -> int:
    """Estimate token count using word-count heuristic (~1 token per 0.75 words)."""
    return int(len(text.split()) / 0.75)


def _generate_doc_id(filename: str) -> str:
    """Generate a short doc ID from filename."""
    return "doc_" + hashlib.md5(filename.encode()).hexdigest()[:8]


# =============================================================================
# Smart Chunking (Sentence-Boundary Aware)
# =============================================================================
def split_into_chunks(
    pages: list[dict],
    filename: str = "",
) -> list[dict]:
    """
    Split pages into sentence-boundary-aware chunks with metadata.

    Algorithm:
      1. Collect all sentences from non-empty pages, tagged with page numbers
      2. Accumulate sentences until target token count (~1500 tokens)
      3. Save chunk with metadata, carry 1-2 overlap sentences to next chunk
      4. Never split mid-sentence

    Args:
        pages: List of {"page": int, "text": str} dicts.
        filename: Source filename for metadata.

    Returns:
        List of chunk metadata dicts per claude.md Section 4.
    """
    # 1. Collect sentences tagged with page numbers
    tagged_sentences = []
    for page_info in pages:
        page_num = page_info["page"]
        page_text = page_info["text"]

        # Skip empty/image pages (< 50 chars)
        if len(page_text.strip()) < 50:
            continue

        # Paragraph-first splitting, then sentence detection
        paragraphs = page_text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            sentences = sent_tokenize(para)
            for sent in sentences:
                sent = sent.strip()
                if sent:
                    tagged_sentences.append((sent, page_num))

    if not tagged_sentences:
        print("   No text to chunk.")
        return []

    # 2. Build chunks from sentences
    doc_id = _generate_doc_id(filename)
    chunks = []
    current = []        # [(sentence, page_num), ...]
    current_tokens = 0

    i = 0
    while i < len(tagged_sentences):
        sent_text, page_num = tagged_sentences[i]
        sent_tokens = _estimate_tokens(sent_text)

        # If adding this sentence would exceed the target and we have content
        if current_tokens + sent_tokens > CHUNK_TOKEN_SIZE and current:
            # Save current chunk
            chunk_text = " ".join(s for s, _ in current)
            page_nums = [p for _, p in current]
            chunks.append({
                "chunk_id": f"{doc_id}_chunk_{len(chunks):04d}",
                "doc_id": doc_id,
                "filename": filename,
                "page_start": min(page_nums),
                "page_end": max(page_nums),
                "chunk_index": len(chunks),
                "total_chunks": 0,  # Updated after all chunks created
                "char_count": len(chunk_text),
                "original_text": chunk_text,
            })

            # Carry overlap sentences to next chunk
            overlap_count = min(CHUNK_OVERLAP_SENTENCES, len(current))
            overlap = current[-overlap_count:]
            current = list(overlap)
            current_tokens = sum(_estimate_tokens(s) for s, _ in current)
            continue  # Re-check sentence i with fresh chunk

        # Add sentence to current chunk (also handles single huge sentences)
        current.append((sent_text, page_num))
        current_tokens += sent_tokens
        i += 1

    # 3. Final chunk
    if current:
        chunk_text = " ".join(s for s, _ in current)
        page_nums = [p for _, p in current]
        chunks.append({
            "chunk_id": f"{doc_id}_chunk_{len(chunks):04d}",
            "doc_id": doc_id,
            "filename": filename,
            "page_start": min(page_nums),
            "page_end": max(page_nums),
            "chunk_index": len(chunks),
            "total_chunks": 0,
            "char_count": len(chunk_text),
            "original_text": chunk_text,
        })

    # 4. Backfill total_chunks
    total = len(chunks)
    for chunk in chunks:
        chunk["total_chunks"] = total

    print(f"   Split into {total} chunks (sentence-boundary aware)")
    return chunks
