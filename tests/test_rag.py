"""Tests for rag.py — RAG QA functionality."""

from unittest.mock import MagicMock, patch

import pytest

import rag
from rag import ask_question, rag_loop


# =============================================================================
# ask_question
# =============================================================================

class TestAskQuestion:
    def test_success(self, mock_cpp_client, mock_groq_response):
        response = mock_groq_response("The answer is 42.", 200, 100)
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = response

        with patch("rag._get_client", return_value=mock_groq):
            answer, pages = ask_question("What?", "d1", mock_cpp_client)
        assert answer == "The answer is 42."
        assert 1 in pages
        assert 2 in pages

    def test_no_results(self):
        client = MagicMock()
        client.search.return_value = []

        answer, pages = ask_question("What?", "d1", client)
        assert "No relevant content" in answer
        assert pages == []

    def test_uses_translated_text(self, mock_groq_response):
        """When metadata has translated_text, it should be used as context."""
        client = MagicMock()
        client.search.return_value = [
            {
                "chunk_id": "c1",
                "score": 0.9,
                "text": "Original English text",
                "metadata": {
                    "translated_text": "Translated Korean text",
                    "page_start": 1,
                    "page_end": 1,
                },
            }
        ]
        response = mock_groq_response("Answer based on Korean", 100, 50)
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = response

        with patch("rag._get_client", return_value=mock_groq):
            answer, _ = ask_question("Q?", "d1", client)

        # Check that the prompt sent to Groq contains translated text
        call_args = mock_groq.chat.completions.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        assert "Translated Korean text" in prompt_content

    def test_page_collection(self, mock_groq_response):
        client = MagicMock()
        client.search.return_value = [
            {"chunk_id": "c1", "text": "t1", "metadata": {"page_start": 1, "page_end": 3}},
            {"chunk_id": "c2", "text": "t2", "metadata": {"page_start": 2, "page_end": 5}},
        ]
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = mock_groq_response("A", 50, 25)

        with patch("rag._get_client", return_value=mock_groq):
            _, pages = ask_question("Q?", "d1", client)
        assert pages == [1, 2, 3, 5]

    def test_api_error(self, api_error):
        client = MagicMock()
        client.search.return_value = [
            {"chunk_id": "c1", "text": "t1", "metadata": {}},
        ]
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.side_effect = api_error()

        with patch("rag._get_client", return_value=mock_groq):
            answer, _ = ask_question("Q?", "d1", client)
        assert "API error" in answer

    def test_missing_pages_metadata(self, mock_groq_response):
        """Results without page metadata should not crash."""
        client = MagicMock()
        client.search.return_value = [
            {"chunk_id": "c1", "text": "t1", "metadata": {}},
        ]
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = mock_groq_response("A", 50, 25)

        with patch("rag._get_client", return_value=mock_groq):
            answer, pages = ask_question("Q?", "d1", client)
        assert pages == []


# =============================================================================
# rag_loop
# =============================================================================

class TestRagLoop:
    def test_quit_immediately(self, mock_cpp_client):
        with patch("builtins.input", return_value="q"):
            rag_loop("d1", "test.pdf", mock_cpp_client)

    def test_empty_then_quit(self, mock_cpp_client):
        with patch("builtins.input", side_effect=["", "quit"]):
            rag_loop("d1", "test.pdf", mock_cpp_client)

    def test_asks_then_quits(self, mock_cpp_client, mock_groq_response):
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = mock_groq_response("Answer", 50, 25)

        with patch("builtins.input", side_effect=["What is this?", "q"]), \
             patch("rag._get_client", return_value=mock_groq):
            rag_loop("d1", "test.pdf", mock_cpp_client)

    def test_eof_exits(self, mock_cpp_client):
        with patch("builtins.input", side_effect=EOFError):
            rag_loop("d1", "test.pdf", mock_cpp_client)

    def test_keyboard_interrupt_exits(self, mock_cpp_client):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            rag_loop("d1", "test.pdf", mock_cpp_client)
