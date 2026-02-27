"""Tests for translate.py — UsageTracker and Groq translation."""

from unittest.mock import patch, MagicMock

import pytest

import translate
from translate import UsageTracker, translate_chunk, translate_text


# =============================================================================
# UsageTracker
# =============================================================================

class TestUsageTracker:
    def test_initial_state(self):
        tracker = UsageTracker()
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.translations == 0
        assert tracker.skipped == 0

    def test_add(self):
        tracker = UsageTracker()
        tracker.add(100, 50)
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50
        assert tracker.translations == 1

    def test_add_multiple(self):
        tracker = UsageTracker()
        tracker.add(100, 50)
        tracker.add(200, 80)
        assert tracker.total_input_tokens == 300
        assert tracker.total_output_tokens == 130
        assert tracker.translations == 2

    def test_add_skip(self):
        tracker = UsageTracker()
        tracker.add_skip()
        tracker.add_skip()
        assert tracker.skipped == 2

    def test_print_summary(self, capsys):
        tracker = UsageTracker()
        tracker.add(100, 50)
        tracker.print_summary()
        output = capsys.readouterr().out
        assert "100" in output
        assert "50" in output


# =============================================================================
# _get_client
# =============================================================================

class TestGetClient:
    def test_missing_key_raises(self):
        with patch("config.GROQ_API_KEY", ""):
            translate._client = None
            with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
                translate._get_client()

    def test_creates_client(self):
        with patch("config.GROQ_API_KEY", "test-key"), \
             patch("translate.Groq") as mock_groq:
            translate._client = None
            client = translate._get_client()
            mock_groq.assert_called_once_with(api_key="test-key")
            assert client is mock_groq.return_value

    def test_caches_client(self):
        with patch("config.GROQ_API_KEY", "test-key"), \
             patch("translate.Groq") as mock_groq:
            translate._client = None
            client1 = translate._get_client()
            client2 = translate._get_client()
            assert client1 is client2
            mock_groq.assert_called_once()


# =============================================================================
# translate_chunk
# =============================================================================

class TestTranslateChunk:
    def test_success(self, mock_groq_response):
        response = mock_groq_response("Translated!", 100, 50)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        with patch("translate._get_client", return_value=mock_client):
            text, in_tok, out_tok = translate_chunk("Hello", 1, 1)
        assert text == "Translated!"
        assert in_tok == 100
        assert out_tok == 50

    def test_rate_limit_retry(self, mock_groq_response, rate_limit_error):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            rate_limit_error(),
            mock_groq_response("Recovered", 80, 40),
        ]

        with patch("translate._get_client", return_value=mock_client), \
             patch("time.sleep"):
            text, in_tok, out_tok = translate_chunk("Hello", 1, 1)
        assert text == "Recovered"

    def test_api_error_retry(self, mock_groq_response, api_error):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            api_error(),
            mock_groq_response("Recovered", 80, 40),
        ]

        with patch("translate._get_client", return_value=mock_client), \
             patch("time.sleep"):
            text, in_tok, out_tok = translate_chunk("Hello", 1, 1)
        assert text == "Recovered"

    def test_all_retries_fail(self, rate_limit_error):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = rate_limit_error()

        with patch("translate._get_client", return_value=mock_client), \
             patch("time.sleep"):
            text, in_tok, out_tok = translate_chunk("Hello", 1, 1)
        assert text is None
        assert in_tok == 0
        assert out_tok == 0

    def test_max_tokens_floor(self, mock_groq_response):
        """Even for very short text, max_tokens >= 256."""
        response = mock_groq_response("OK", 10, 5)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        with patch("translate._get_client", return_value=mock_client):
            translate_chunk("Hi", 1, 1)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] >= 256


# =============================================================================
# translate_text
# =============================================================================

class TestTranslateText:
    def test_empty_list(self):
        assert translate_text([]) == []

    def test_all_succeed(self, sample_chunks, mock_groq_response):
        response = mock_groq_response("Translated", 100, 50)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        with patch("translate._get_client", return_value=mock_client), \
             patch("time.sleep"):
            results = translate_text(sample_chunks)
        assert len(results) == 2
        for chunk, text in results:
            assert text == "Translated"

    def test_some_fail(self, sample_chunks, mock_groq_response, rate_limit_error):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            mock_groq_response("First", 100, 50),
            rate_limit_error(),
            rate_limit_error(),
            rate_limit_error(),
        ]

        with patch("translate._get_client", return_value=mock_client), \
             patch("time.sleep"):
            results = translate_text(sample_chunks)
        assert len(results) == 1
        assert results[0][1] == "First"

    def test_rate_delay_between_chunks(self, sample_chunks, mock_groq_response):
        response = mock_groq_response("OK", 50, 25)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        with patch("translate._get_client", return_value=mock_client), \
             patch("time.sleep") as mock_sleep:
            translate_text(sample_chunks)
        # Sleep called once between chunks (not before first)
        sleep_calls = [c for c in mock_sleep.call_args_list
                       if c.args[0] == translate.REQUEST_DELAY]
        assert len(sleep_calls) == 1

    def test_progress_callback(self, sample_chunks, mock_groq_response):
        response = mock_groq_response("OK", 50, 25)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response
        callback = MagicMock()

        with patch("translate._get_client", return_value=mock_client), \
             patch("time.sleep"):
            translate_text(sample_chunks, on_progress=callback)
        assert callback.call_count == 2
        callback.assert_any_call(1, 2, 0)
        callback.assert_any_call(2, 2, 0)
