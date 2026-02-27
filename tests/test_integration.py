"""Integration tests — end-to-end pipeline with mocked external services."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from process import process_pdf, process_txt
from rag import ask_question


class TestFullPdfPipeline:
    """Parse real PDF + mock Groq + mock VectorDB."""

    def test_pdf_pipeline(self, sample_pdf_path, tmp_dirs, mock_groq_response, mock_cpp_client):
        dest = tmp_dirs["input"] / "sample.pdf"
        shutil.copy(str(sample_pdf_path), str(dest))

        response = mock_groq_response("Translated content", 100, 50)
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = response

        with patch("translate._get_client", return_value=mock_groq), \
             patch("time.sleep"):
            result = process_pdf(dest, client=mock_cpp_client)

        assert result is True
        output_files = list(tmp_dirs["output"].glob("*_translated.txt"))
        assert len(output_files) == 1
        assert not dest.exists()
        assert (tmp_dirs["processed"] / "sample.pdf").exists()


class TestFullTxtPipeline:
    def test_txt_pipeline(self, tmp_dirs, mock_groq_response, mock_cpp_client):
        txt_file = tmp_dirs["input"] / "notes.txt"
        txt_file.write_text(
            "This is a long text document that should be processed through the pipeline. "
            "It contains multiple sentences and enough content to form at least one chunk. "
            "The translation system will process this text and produce translated output.",
            encoding="utf-8",
        )

        response = mock_groq_response("Translated notes", 80, 40)
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = response

        with patch("translate._get_client", return_value=mock_groq), \
             patch("time.sleep"):
            result = process_txt(txt_file, client=mock_cpp_client)

        assert result is True
        output_files = list(tmp_dirs["output"].glob("*_translated.txt"))
        assert len(output_files) == 1


class TestPipelineWithoutVectorDB:
    def test_no_client(self, sample_pdf_path, tmp_dirs, mock_groq_response):
        dest = tmp_dirs["input"] / "sample.pdf"
        shutil.copy(str(sample_pdf_path), str(dest))

        response = mock_groq_response("Translated", 100, 50)
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = response

        with patch("translate._get_client", return_value=mock_groq), \
             patch("time.sleep"):
            result = process_pdf(dest, client=None)

        assert result is True
        output_files = list(tmp_dirs["output"].glob("*_translated.txt"))
        assert len(output_files) == 1


class TestPartialTranslationFailure:
    def test_some_chunks_skip(self, sample_pdf_path, tmp_dirs, sample_chunks):
        """When some chunks fail translation, pipeline still succeeds with partial results."""
        dest = tmp_dirs["input"] / "sample.pdf"
        shutil.copy(str(sample_pdf_path), str(dest))

        # Only the first chunk gets translated; second is skipped
        translated_results = [(sample_chunks[0], "Translated first chunk")]

        with patch("process.split_into_chunks", return_value=sample_chunks), \
             patch("process.translate_text", return_value=translated_results):
            result = process_pdf(dest, client=None)

        assert result is True
        output_files = list(tmp_dirs["output"].glob("*_translated.txt"))
        assert len(output_files) == 1
        content = output_files[0].read_text(encoding="utf-8")
        assert "Translated first chunk" in content


class TestRagFlow:
    def test_search_and_answer(self, mock_cpp_client, mock_groq_response):
        response = mock_groq_response("The document discusses AI translation.", 200, 80)
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = response

        with patch("rag._get_client", return_value=mock_groq):
            answer, pages = ask_question(
                "What does the document discuss?",
                "doc_abc12345",
                mock_cpp_client,
            )

        assert "AI translation" in answer
        assert len(pages) > 0
        mock_cpp_client.search.assert_called_once()
