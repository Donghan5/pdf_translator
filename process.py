"""
Pipeline integration — Flow 1: Parse → Store → Translate → Update VectorDB → Save.
Milestone 5: Wire together all components with non-blocking error handling.
"""

import shutil
import time
from pathlib import Path

from client import CppClient
from config import OUTPUT_DIR, PROCESSED_DIR
from parse import extract_text_from_pdf, extract_text_from_txt, split_into_chunks
from translate import translate_text


# =============================================================================
# Per-file stats
# =============================================================================
class FileStats:
    def __init__(self, filename: str):
        self.filename = filename
        self.chunks_total = 0
        self.chunks_translated = 0
        self.chunks_skipped = 0
        self.chunks_stored = 0
        self.chunks_store_failed = 0
        self.start_time = time.time()

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def print_summary(self):
        print(f"\n   --- {self.filename} Stats ---")
        print(f"      Chunks total:        {self.chunks_total}")
        print(f"      Stored in VectorDB:  {self.chunks_stored}")
        if self.chunks_store_failed:
            print(f"      Store failures:      {self.chunks_store_failed}")
        print(f"      Translated:          {self.chunks_translated}")
        if self.chunks_skipped:
            print(f"      Skipped:             {self.chunks_skipped}")
        print(f"      Elapsed:             {self.elapsed:.1f}s")


# =============================================================================
# VectorDB helpers (non-blocking)
# =============================================================================
def _store_chunks(client: CppClient | None, chunks: list[dict], stats: FileStats):
    """Store original chunks in VectorDB. Failures are logged and skipped."""
    if client is None:
        return

    for chunk in chunks:
        try:
            client.store_chunk(
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                text=chunk["original_text"],
                metadata={
                    "filename": chunk["filename"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    "char_count": chunk["char_count"],
                },
            )
            stats.chunks_stored += 1
        except Exception as e:
            stats.chunks_store_failed += 1
            print(f"   [WARN] Failed to store chunk {chunk['chunk_id']}: {e}")


def _update_translated(client: CppClient | None, results: list[tuple[dict, str]]):
    """Re-store chunks with translated text added to metadata."""
    if client is None:
        return

    for chunk, translated in results:
        try:
            client.store_chunk(
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                text=chunk["original_text"],
                metadata={
                    "filename": chunk["filename"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    "char_count": chunk["char_count"],
                    "translated_text": translated,
                },
            )
        except Exception as e:
            print(f"   [WARN] Failed to update translated chunk {chunk['chunk_id']}: {e}")


# =============================================================================
# Core pipeline
# =============================================================================
def _run_pipeline(
    pages: list[dict],
    filename: str,
    file_path: Path,
    client: CppClient | None,
    on_progress=None,
) -> bool:
    """Shared pipeline: chunk → store → translate → update → save → move."""
    stats = FileStats(filename)

    # Check for empty content
    total_chars = sum(len(p["text"]) for p in pages)
    if total_chars == 0:
        print(f"   No text extracted from {filename}. Skipping.")
        return False

    # 1. Chunk
    chunks = split_into_chunks(pages, filename=filename)
    if not chunks:
        print(f"   No chunks created from {filename}. Skipping.")
        return False
    stats.chunks_total = len(chunks)

    # 2. Store originals in VectorDB
    _store_chunks(client, chunks, stats)

    # 3. Translate
    results = translate_text(chunks, on_progress=on_progress)
    stats.chunks_translated = len(results)
    stats.chunks_skipped = stats.chunks_total - len(results)

    if not results:
        print(f"   No chunks translated for {filename}. Skipping save.")
        stats.print_summary()
        return False

    # 4. Update VectorDB with translated text
    _update_translated(client, results)

    # 5. Save output file
    translated_text = "\n\n".join(text for _, text in results)
    output_filename = file_path.stem + "_translated.txt"
    output_path = OUTPUT_DIR / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {file_path.stem} - Translated\n\n")
        f.write(translated_text)

    print(f"\n   Saved: {output_path.name}")

    # Move original to processed
    dest_path = PROCESSED_DIR / file_path.name
    shutil.move(str(file_path), str(dest_path))
    print(f"   Moved original to: processed/{file_path.name}")

    stats.print_summary()
    return True


# =============================================================================
# Public API
# =============================================================================
def process_pdf(
    pdf_path: Path,
    client: CppClient | None = None,
    on_progress=None,
) -> bool:
    """Process a single PDF: extract → chunk → store → translate → update → save."""
    try:
        pages = extract_text_from_pdf(pdf_path)
        return _run_pipeline(pages, pdf_path.name, pdf_path, client, on_progress)
    except Exception as e:
        print(f"\n   Failed to process {pdf_path.name}: {e}")
        return False


def process_txt(
    txt_path: Path,
    client: CppClient | None = None,
    on_progress=None,
) -> bool:
    """Process a single TXT: read → chunk → store → translate → update → save."""
    try:
        text = extract_text_from_txt(txt_path)
        if not text.strip():
            print(f"   No text extracted from {txt_path.name}. Skipping.")
            return False
        pages = [{"page": 1, "text": text}]
        return _run_pipeline(pages, txt_path.name, txt_path, client, on_progress)
    except Exception as e:
        print(f"   Failed to process {txt_path.name}: {e}")
        return False
