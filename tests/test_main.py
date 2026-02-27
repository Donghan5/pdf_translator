"""Tests for main.py — CLI helpers and formatters."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from main import ok, err, warn, format_time, discover_files, select_language, configure_languages


# =============================================================================
# ANSI formatting
# =============================================================================

class TestAnsiFormatting:
    def test_ok(self):
        result = ok("done")
        assert "\033[92m" in result
        assert "\u2713" in result
        assert "done" in result

    def test_err(self):
        result = err("fail")
        assert "\033[91m" in result
        assert "\u2717" in result
        assert "fail" in result

    def test_warn(self):
        result = warn("caution")
        assert "\033[93m" in result
        assert "!" in result
        assert "caution" in result


# =============================================================================
# format_time
# =============================================================================

class TestFormatTime:
    def test_seconds(self):
        assert format_time(30) == "30s"

    def test_zero(self):
        assert format_time(0) == "0s"

    def test_minutes_and_seconds(self):
        assert format_time(90) == "1m 30s"

    def test_exact_minute(self):
        assert format_time(60) == "1m 00s"

    def test_large_value(self):
        assert format_time(3661) == "61m 01s"


# =============================================================================
# discover_files
# =============================================================================

class TestDiscoverFiles:
    def test_no_files(self, tmp_path):
        with patch("main.INPUT_DIR", tmp_path):
            result = discover_files()
        assert result == []

    def test_pdf_files(self, tmp_path):
        (tmp_path / "doc.pdf").write_bytes(b"fake")
        with patch("main.INPUT_DIR", tmp_path), \
             patch("main.get_pdf_page_count", return_value=5):
            result = discover_files()
        assert len(result) == 1
        assert result[0].name == "doc.pdf"

    def test_txt_files(self, tmp_path):
        (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
        with patch("main.INPUT_DIR", tmp_path):
            result = discover_files()
        assert len(result) == 1
        assert result[0].name == "notes.txt"

    def test_mixed_files(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"fake")
        (tmp_path / "b.txt").write_text("hello", encoding="utf-8")
        with patch("main.INPUT_DIR", tmp_path), \
             patch("main.get_pdf_page_count", return_value=3):
            result = discover_files()
        assert len(result) == 2

    def test_ignores_other_extensions(self, tmp_path):
        (tmp_path / "image.png").write_bytes(b"fake")
        (tmp_path / "data.csv").write_text("a,b", encoding="utf-8")
        with patch("main.INPUT_DIR", tmp_path):
            result = discover_files()
        assert result == []


# =============================================================================
# select_language
# =============================================================================

class TestSelectLanguage:
    def test_default(self):
        with patch("builtins.input", return_value=""):
            result = select_language("Source: ", "en")
        assert result == "en"

    def test_valid_input(self):
        with patch("builtins.input", return_value="ko"):
            result = select_language("Source: ", "en")
        assert result == "ko"

    def test_invalid_then_valid(self):
        with patch("builtins.input", side_effect=["xx", "fr"]):
            result = select_language("Source: ", "en")
        assert result == "fr"


# =============================================================================
# configure_languages
# =============================================================================

class TestConfigureLanguages:
    def test_same_language_returns_false(self):
        with patch("builtins.input", side_effect=["en", "en"]):
            result = configure_languages()
        assert result is False

    def test_different_languages_returns_true(self):
        with patch("builtins.input", side_effect=["en", "ko"]):
            result = configure_languages()
        assert result is True
