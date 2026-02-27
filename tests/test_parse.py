"""Tests for parse.py — text extraction and chunking."""

from unittest.mock import patch

import pytest

from parse import (
    _estimate_tokens,
    _generate_doc_id,
    extract_text_from_pdf,
    extract_text_from_txt,
    split_into_chunks,
)


# =============================================================================
# _estimate_tokens
# =============================================================================

class TestEstimateTokens:
    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_short_text(self):
        result = _estimate_tokens("hello world")
        assert result == int(2 / 0.75)

    def test_paragraph(self):
        text = "word " * 100
        result = _estimate_tokens(text)
        assert result == int(100 / 0.75)


# =============================================================================
# _generate_doc_id
# =============================================================================

class TestGenerateDocId:
    def test_format(self):
        doc_id = _generate_doc_id("test.pdf")
        assert doc_id.startswith("doc_")
        assert len(doc_id) == 12  # "doc_" + 8 hex chars

    def test_deterministic(self):
        assert _generate_doc_id("test.pdf") == _generate_doc_id("test.pdf")

    def test_different_files_different_ids(self):
        assert _generate_doc_id("a.pdf") != _generate_doc_id("b.pdf")


# =============================================================================
# split_into_chunks
# =============================================================================

class TestSplitIntoChunks:
    def test_empty_pages(self):
        assert split_into_chunks([]) == []

    def test_short_text_skipped(self):
        """Pages with <50 chars are skipped."""
        pages = [{"page": 1, "text": "Short."}]
        assert split_into_chunks(pages, filename="test.pdf") == []

    def test_single_chunk(self, sample_pages):
        """With large CHUNK_TOKEN_SIZE, all text fits in one chunk."""
        with patch("parse.CHUNK_TOKEN_SIZE", 100000):
            chunks = split_into_chunks(sample_pages, filename="test.pdf")
        assert len(chunks) == 1
        assert chunks[0]["chunk_index"] == 0
        assert chunks[0]["total_chunks"] == 1

    def test_multi_chunk(self, sample_pages):
        """With small CHUNK_TOKEN_SIZE, text is split into multiple chunks."""
        with patch("parse.CHUNK_TOKEN_SIZE", 50):
            chunks = split_into_chunks(sample_pages, filename="test.pdf")
        assert len(chunks) > 1

    def test_metadata_fields(self, sample_pages):
        with patch("parse.CHUNK_TOKEN_SIZE", 100000):
            chunks = split_into_chunks(sample_pages, filename="test.pdf")
        chunk = chunks[0]
        assert "chunk_id" in chunk
        assert "doc_id" in chunk
        assert "filename" in chunk
        assert chunk["filename"] == "test.pdf"
        assert "page_start" in chunk
        assert "page_end" in chunk
        assert "chunk_index" in chunk
        assert "total_chunks" in chunk
        assert "char_count" in chunk
        assert "original_text" in chunk

    def test_overlap_sentences(self, sample_pages):
        """Chunks should have overlap from CHUNK_OVERLAP_SENTENCES."""
        with patch("parse.CHUNK_TOKEN_SIZE", 50), \
             patch("parse.CHUNK_OVERLAP_SENTENCES", 2):
            chunks = split_into_chunks(sample_pages, filename="test.pdf")
        if len(chunks) >= 2:
            # Overlap means some text from end of chunk 0 appears in chunk 1
            text0 = chunks[0]["original_text"]
            text1 = chunks[1]["original_text"]
            # Last sentences of chunk 0 should appear at start of chunk 1
            words0 = text0.split()[-5:]
            overlap_found = any(w in text1 for w in words0)
            assert overlap_found

    def test_unique_chunk_ids(self, sample_pages):
        with patch("parse.CHUNK_TOKEN_SIZE", 50):
            chunks = split_into_chunks(sample_pages, filename="test.pdf")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_sequential_indices(self, sample_pages):
        with patch("parse.CHUNK_TOKEN_SIZE", 50):
            chunks = split_into_chunks(sample_pages, filename="test.pdf")
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_total_chunks_backfilled(self, sample_pages):
        with patch("parse.CHUNK_TOKEN_SIZE", 50):
            chunks = split_into_chunks(sample_pages, filename="test.pdf")
        for chunk in chunks:
            assert chunk["total_chunks"] == len(chunks)

    def test_all_pages_empty(self):
        pages = [
            {"page": 1, "text": ""},
            {"page": 2, "text": "  "},
        ]
        assert split_into_chunks(pages, filename="test.pdf") == []


# =============================================================================
# extract_text_from_pdf (requires reportlab fixture)
# =============================================================================

class TestExtractTextFromPdf:
    def test_real_pdf(self, sample_pdf_path):
        pages = extract_text_from_pdf(sample_pdf_path)
        assert len(pages) == 2
        assert pages[0]["page"] == 1
        assert pages[1]["page"] == 2
        assert "first page" in pages[0]["text"].lower()

    def test_blank_page_handling(self, tmp_path):
        """Pages with <50 chars flagged as empty but still returned."""
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as pdf_canvas
        import io

        buf = io.BytesIO()
        c = pdf_canvas.Canvas(buf, pagesize=letter)
        c.drawString(72, 700, "Page one has enough text content for extraction testing purposes here.")
        c.showPage()
        c.showPage()  # Blank page
        c.save()

        pdf_path = tmp_path / "blank.pdf"
        pdf_path.write_bytes(buf.getvalue())

        pages = extract_text_from_pdf(pdf_path)
        assert len(pages) == 2
        assert len(pages[1]["text"].strip()) < 50


# =============================================================================
# extract_text_from_txt
# =============================================================================

class TestExtractTextFromTxt:
    def test_normal_file(self, sample_txt_path):
        text = extract_text_from_txt(sample_txt_path)
        assert "sample text file" in text

    def test_empty_file(self, tmp_path):
        empty_path = tmp_path / "empty.txt"
        empty_path.write_text("", encoding="utf-8")
        text = extract_text_from_txt(empty_path)
        assert text == ""
