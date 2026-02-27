"""Shared fixtures for pdf_translator tests."""

import io
import struct
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# =============================================================================
# Sample data fixtures
# =============================================================================

@pytest.fixture
def sample_pages():
    """3-page text dicts mimicking extract_text_from_pdf() output."""
    return [
        {
            "page": 1,
            "text": (
                "This is the first page of the document. It contains important "
                "information about the project. The project aims to translate "
                "PDF documents from one language to another using AI."
            ),
        },
        {
            "page": 2,
            "text": (
                "The second page continues with more details. Machine translation "
                "has improved significantly in recent years. Neural networks can "
                "now produce high-quality translations for many language pairs."
            ),
        },
        {
            "page": 3,
            "text": (
                "The final page contains conclusions and references. The system "
                "supports multiple languages including English, Korean, Japanese, "
                "and Chinese. Future work includes image-based text extraction."
            ),
        },
    ]


@pytest.fixture
def sample_chunks():
    """Pre-built chunk metadata dicts."""
    return [
        {
            "chunk_id": "doc_abc12345_chunk_0000",
            "doc_id": "doc_abc12345",
            "filename": "test.pdf",
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 0,
            "total_chunks": 2,
            "char_count": 120,
            "original_text": "This is the first chunk of text from the document.",
        },
        {
            "chunk_id": "doc_abc12345_chunk_0001",
            "doc_id": "doc_abc12345",
            "filename": "test.pdf",
            "page_start": 2,
            "page_end": 3,
            "chunk_index": 1,
            "total_chunks": 2,
            "char_count": 150,
            "original_text": "This is the second chunk containing more content.",
        },
    ]


# =============================================================================
# Groq API mocks
# =============================================================================

@pytest.fixture
def mock_groq_response():
    """Factory returning mock Groq API response objects."""
    def _make(translated_text="Translated text", input_tokens=100, output_tokens=50):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = translated_text
        response.usage.prompt_tokens = input_tokens
        response.usage.completion_tokens = output_tokens
        return response
    return _make


@pytest.fixture
def mock_groq_client(mock_groq_response):
    """MagicMock replacing groq.Groq() with a working chat completions mock."""
    client = MagicMock()
    client.chat.completions.create.return_value = mock_groq_response()
    return client


# =============================================================================
# CppClient mock
# =============================================================================

@pytest.fixture
def mock_cpp_client():
    """MagicMock replacing CppClient with store/search methods."""
    client = MagicMock()
    client.store_chunk.return_value = {"status": "ok"}
    client.search.return_value = [
        {
            "chunk_id": "doc_abc12345_chunk_0000",
            "score": 0.95,
            "text": "Original text of the chunk.",
            "metadata": {
                "translated_text": "Translated text of the chunk.",
                "page_start": 1,
                "page_end": 2,
                "filename": "test.pdf",
            },
        }
    ]
    return client


# =============================================================================
# Filesystem fixtures
# =============================================================================

@pytest.fixture
def tmp_dirs(tmp_path):
    """Temp input/output/processed dirs, patches config.*_DIR."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    output_dir.mkdir()
    processed_dir.mkdir()

    with patch("config.INPUT_DIR", input_dir), \
         patch("config.OUTPUT_DIR", output_dir), \
         patch("config.PROCESSED_DIR", processed_dir), \
         patch("process.OUTPUT_DIR", output_dir), \
         patch("process.PROCESSED_DIR", processed_dir):
        yield {
            "input": input_dir,
            "output": output_dir,
            "processed": processed_dir,
        }


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Real 2-page PDF created via reportlab."""
    pdf_path = tmp_path / "sample.pdf"
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    # Page 1
    c.drawString(72, 700, "This is the first page of the sample PDF document.")
    c.drawString(72, 680, "It contains enough text to be considered non-empty by the parser.")
    c.showPage()

    # Page 2
    c.drawString(72, 700, "This is the second page with additional content for testing.")
    c.drawString(72, 680, "The document has multiple pages to test page-based extraction.")
    c.showPage()

    c.save()
    pdf_path.write_bytes(buf.getvalue())
    return pdf_path


@pytest.fixture
def sample_txt_path(tmp_path):
    """Text file in tmp_path."""
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text(
        "This is a sample text file with enough content for testing. "
        "It contains multiple sentences that can be split into chunks. "
        "The text should be long enough to pass the minimum character threshold.",
        encoding="utf-8",
    )
    return txt_path


# =============================================================================
# Error factories
# =============================================================================

@pytest.fixture
def rate_limit_error():
    """Groq RateLimitError factory."""
    from groq import RateLimitError

    def _make(message="Rate limit exceeded"):
        response = httpx.Response(
            status_code=429,
            request=httpx.Request("POST", "https://api.groq.com/v1/chat/completions"),
        )
        return RateLimitError(message, response=response, body=None)
    return _make


@pytest.fixture
def api_error():
    """Groq APIError factory."""
    from groq import APIError

    def _make(message="Internal server error"):
        return APIError(
            message,
            request=httpx.Request("POST", "https://api.groq.com/v1/chat/completions"),
            body=None,
        )
    return _make


# =============================================================================
# Module-level global resets (autouse)
# =============================================================================

@pytest.fixture(autouse=True)
def reset_translate_globals():
    """Reset translate._client and usage_tracker before each test."""
    import translate
    translate._client = None
    translate.usage_tracker = translate.UsageTracker()
    yield
    translate._client = None


@pytest.fixture(autouse=True)
def reset_rag_globals():
    """Reset rag._client before each test."""
    import rag
    rag._client = None
    yield
    rag._client = None
