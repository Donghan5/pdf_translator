"""Tests for process.py — pipeline integration."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from process import FileStats, _store_chunks, _run_pipeline, process_pdf, process_txt


# =============================================================================
# FileStats
# =============================================================================

class TestFileStats:
    def test_initial_state(self):
        stats = FileStats("test.pdf")
        assert stats.filename == "test.pdf"
        assert stats.chunks_total == 0
        assert stats.chunks_translated == 0
        assert stats.chunks_skipped == 0
        assert stats.chunks_stored == 0
        assert stats.chunks_store_failed == 0

    def test_elapsed(self):
        stats = FileStats("test.pdf")
        time.sleep(0.05)
        assert stats.elapsed >= 0.04


# =============================================================================
# _store_chunks
# =============================================================================

class TestStoreChunks:
    def test_none_client(self, sample_chunks):
        stats = FileStats("test.pdf")
        _store_chunks(None, sample_chunks, stats)
        assert stats.chunks_stored == 0

    def test_success(self, sample_chunks, mock_cpp_client):
        stats = FileStats("test.pdf")
        _store_chunks(mock_cpp_client, sample_chunks, stats)
        assert stats.chunks_stored == 2
        assert mock_cpp_client.store_chunk.call_count == 2

    def test_partial_failure(self, sample_chunks):
        client = MagicMock()
        client.store_chunk.side_effect = [
            {"status": "ok"},
            RuntimeError("connection lost"),
        ]
        stats = FileStats("test.pdf")
        _store_chunks(client, sample_chunks, stats)
        assert stats.chunks_stored == 1
        assert stats.chunks_store_failed == 1


# =============================================================================
# _run_pipeline
# =============================================================================

class TestRunPipeline:
    def test_empty_content(self, tmp_dirs):
        pages = [{"page": 1, "text": ""}]
        result = _run_pipeline(pages, "test.pdf", Path("test.pdf"), None)
        assert result is False

    def test_no_chunks(self, tmp_dirs, sample_pages):
        """When all pages are too short, no chunks are created."""
        short_pages = [{"page": 1, "text": "Short."}]
        result = _run_pipeline(short_pages, "test.pdf", Path("test.pdf"), None)
        assert result is False

    def test_no_translations(self, tmp_dirs, sample_pages):
        with patch("process.split_into_chunks", return_value=[{
                "chunk_id": "c1", "doc_id": "d1", "filename": "test.pdf",
                "page_start": 1, "page_end": 1, "chunk_index": 0,
                "total_chunks": 1, "char_count": 50, "original_text": "Hello",
            }]), \
             patch("process.translate_text", return_value=[]):
            result = _run_pipeline(sample_pages, "test.pdf", Path("test.pdf"), None)
        assert result is False

    def test_success(self, tmp_dirs, sample_pages):
        chunk = {
            "chunk_id": "c1", "doc_id": "d1", "filename": "test.pdf",
            "page_start": 1, "page_end": 1, "chunk_index": 0,
            "total_chunks": 1, "char_count": 50, "original_text": "Hello",
        }
        translated_chunk = dict(chunk, translated_text="Bonjour")

        # Create the source file so shutil.move works
        src_file = tmp_dirs["input"] / "test.pdf"
        src_file.write_text("fake pdf")

        with patch("process.split_into_chunks", return_value=[chunk]), \
             patch("process.translate_text", return_value=[(translated_chunk, "Bonjour")]):
            result = _run_pipeline(sample_pages, "test.pdf", src_file, None)
        assert result is True

    def test_output_content(self, tmp_dirs, sample_pages):
        chunk = {
            "chunk_id": "c1", "doc_id": "d1", "filename": "test.pdf",
            "page_start": 1, "page_end": 1, "chunk_index": 0,
            "total_chunks": 1, "char_count": 50, "original_text": "Hello",
        }
        src_file = tmp_dirs["input"] / "test.pdf"
        src_file.write_text("fake pdf")

        with patch("process.split_into_chunks", return_value=[chunk]), \
             patch("process.translate_text", return_value=[(chunk, "Bonjour")]):
            _run_pipeline(sample_pages, "test.pdf", src_file, None)

        output_file = tmp_dirs["output"] / "test_translated.txt"
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "Bonjour" in content

    def test_file_move(self, tmp_dirs, sample_pages):
        chunk = {
            "chunk_id": "c1", "doc_id": "d1", "filename": "test.pdf",
            "page_start": 1, "page_end": 1, "chunk_index": 0,
            "total_chunks": 1, "char_count": 50, "original_text": "Hello",
        }
        src_file = tmp_dirs["input"] / "test.pdf"
        src_file.write_text("fake pdf")

        with patch("process.split_into_chunks", return_value=[chunk]), \
             patch("process.translate_text", return_value=[(chunk, "Bonjour")]):
            _run_pipeline(sample_pages, "test.pdf", src_file, None)

        assert not src_file.exists()
        assert (tmp_dirs["processed"] / "test.pdf").exists()

    def test_null_client_skips_store(self, tmp_dirs, sample_pages):
        chunk = {
            "chunk_id": "c1", "doc_id": "d1", "filename": "test.pdf",
            "page_start": 1, "page_end": 1, "chunk_index": 0,
            "total_chunks": 1, "char_count": 50, "original_text": "Hello",
        }
        src_file = tmp_dirs["input"] / "test.pdf"
        src_file.write_text("fake pdf")

        with patch("process.split_into_chunks", return_value=[chunk]), \
             patch("process.translate_text", return_value=[(chunk, "OK")]), \
             patch("process._store_chunks") as mock_store, \
             patch("process._update_translated") as mock_update:
            _run_pipeline(sample_pages, "test.pdf", src_file, None)
        mock_store.assert_called_once_with(None, [chunk], pytest.approx(mock_store.call_args.args[2], abs=1))

    def test_progress_forwarding(self, tmp_dirs, sample_pages):
        chunk = {
            "chunk_id": "c1", "doc_id": "d1", "filename": "test.pdf",
            "page_start": 1, "page_end": 1, "chunk_index": 0,
            "total_chunks": 1, "char_count": 50, "original_text": "Hello",
        }
        src_file = tmp_dirs["input"] / "test.pdf"
        src_file.write_text("fake pdf")
        callback = MagicMock()

        with patch("process.split_into_chunks", return_value=[chunk]), \
             patch("process.translate_text", return_value=[(chunk, "OK")]) as mock_translate:
            _run_pipeline(sample_pages, "test.pdf", src_file, None, on_progress=callback)
        # Verify on_progress was passed through to translate_text
        mock_translate.assert_called_once()
        assert mock_translate.call_args.kwargs.get("on_progress") is callback


# =============================================================================
# process_pdf
# =============================================================================

class TestProcessPdf:
    def test_success(self, sample_pdf_path, tmp_dirs):
        # Move pdf to input dir
        import shutil
        dest = tmp_dirs["input"] / "sample.pdf"
        shutil.copy(str(sample_pdf_path), str(dest))

        chunk = {
            "chunk_id": "c1", "doc_id": "d1", "filename": "sample.pdf",
            "page_start": 1, "page_end": 1, "chunk_index": 0,
            "total_chunks": 1, "char_count": 50, "original_text": "Hello",
        }

        with patch("process.split_into_chunks", return_value=[chunk]), \
             patch("process.translate_text", return_value=[(chunk, "Translated")]):
            result = process_pdf(dest)
        assert result is True

    def test_exception_handling(self):
        with patch("process.extract_text_from_pdf", side_effect=Exception("corrupt")):
            result = process_pdf(Path("bad.pdf"))
        assert result is False


# =============================================================================
# process_txt
# =============================================================================

class TestProcessTxt:
    def test_success(self, tmp_dirs):
        txt_file = tmp_dirs["input"] / "sample.txt"
        txt_file.write_text(
            "This is a sample text file with enough content for testing. "
            "It has multiple sentences to be chunked properly for translation.",
            encoding="utf-8",
        )
        chunk = {
            "chunk_id": "c1", "doc_id": "d1", "filename": "sample.txt",
            "page_start": 1, "page_end": 1, "chunk_index": 0,
            "total_chunks": 1, "char_count": 50, "original_text": "Hello",
        }

        with patch("process.split_into_chunks", return_value=[chunk]), \
             patch("process.translate_text", return_value=[(chunk, "Translated")]):
            result = process_txt(txt_file)
        assert result is True

    def test_empty_text(self, tmp_dirs):
        txt_file = tmp_dirs["input"] / "empty.txt"
        txt_file.write_text("", encoding="utf-8")
        result = process_txt(txt_file)
        assert result is False

    def test_exception_handling(self):
        with patch("process.extract_text_from_txt", side_effect=Exception("read error")):
            result = process_txt(Path("bad.txt"))
        assert result is False
