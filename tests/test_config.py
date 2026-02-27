"""Tests for config.py — language helpers and directory setup."""

from unittest.mock import patch

import config


class TestGetLanguageName:
    def test_valid_code_english(self):
        assert config.get_language_name("en") == "English"

    def test_valid_code_korean(self):
        assert config.get_language_name("ko") == "Korean"

    def test_valid_code_chinese_simplified(self):
        assert config.get_language_name("zh") == "Chinese (Simplified)"

    def test_unknown_code_returns_key(self):
        assert config.get_language_name("xx") == "xx"

    def test_empty_code_returns_empty(self):
        assert config.get_language_name("") == ""

    def test_all_supported_languages_resolve(self):
        for code, name in config.SUPPORTED_LANGUAGES.items():
            assert config.get_language_name(code) == name

    def test_supported_languages_has_20_entries(self):
        assert len(config.SUPPORTED_LANGUAGES) == 20


class TestSetLanguages:
    def test_sets_globals(self):
        config.set_languages("fr", "de")
        assert config.SOURCE_LANG == "fr"
        assert config.TARGET_LANG == "de"

    def test_multiple_calls_overwrite(self):
        config.set_languages("en", "ko")
        config.set_languages("ja", "zh")
        assert config.SOURCE_LANG == "ja"
        assert config.TARGET_LANG == "zh"


class TestEnsureDirectories:
    def test_creates_directories(self, tmp_path):
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        processed_dir = tmp_path / "processed"

        with patch("config.INPUT_DIR", input_dir), \
             patch("config.OUTPUT_DIR", output_dir), \
             patch("config.PROCESSED_DIR", processed_dir):
            config.ensure_directories()

        assert input_dir.is_dir()
        assert output_dir.is_dir()
        assert processed_dir.is_dir()

    def test_existing_directories_no_error(self, tmp_path):
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        processed_dir = tmp_path / "processed"
        input_dir.mkdir()
        output_dir.mkdir()
        processed_dir.mkdir()

        with patch("config.INPUT_DIR", input_dir), \
             patch("config.OUTPUT_DIR", output_dir), \
             patch("config.PROCESSED_DIR", processed_dir):
            config.ensure_directories()  # Should not raise
