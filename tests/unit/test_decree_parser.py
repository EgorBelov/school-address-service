"""Тесты на чистые функции LLM-парсера (без реальных вызовов GigaChat)."""
import pytest

from app.services.ai.gigachat.decree_parser import (
    clean_json_text,
    merge_parsed_results,
    parse_json_or_error,
)
from app.services.ai.gigachat.retry import is_transient_error


class TestCleanJsonText:
    def test_strips_markdown_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert "```" not in clean_json_text(text)

    def test_strips_trailing_comma_in_object(self):
        result = clean_json_text('{"a": 1,}')
        assert result == '{"a": 1}'

    def test_strips_trailing_comma_in_array(self):
        result = clean_json_text('{"a": [1, 2,]}')
        assert result == '{"a": [1, 2]}'

    def test_extracts_json_from_noise(self):
        text = 'Вот ответ: {"a": 1} спасибо!'
        assert clean_json_text(text) == '{"a": 1}'

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="JSON не найден"):
            clean_json_text("просто текст без JSON")


class TestParseJsonOrError:
    def test_valid_json(self):
        result = parse_json_or_error('{"decree": {"number": "01"}, "schools": []}')
        assert result["decree"]["number"] == "01"

    def test_invalid_json_raises(self):
        # Битый JSON, который СОДЕРЖИТ {...} но не парсится
        with pytest.raises(ValueError, match="Ошибка JSON"):
            parse_json_or_error('{"a": invalid_token}')

    def test_no_json_at_all_raises(self):
        with pytest.raises(ValueError, match="JSON не найден"):
            parse_json_or_error("просто текст")


class TestMergeParsedResults:
    def test_concatenates_schools(self):
        results = [
            {"decree": {"number": "1"}, "schools": [{"name": "A"}]},
            {"decree": {}, "schools": [{"name": "B"}]},
        ]
        merged = merge_parsed_results(results)
        assert len(merged["schools"]) == 2
        assert merged["decree"]["number"] == "1"

    def test_first_non_empty_wins(self):
        results = [
            {"decree": {"number": ""}, "schools": []},
            {"decree": {"number": "01-02"}, "schools": []},
        ]
        merged = merge_parsed_results(results)
        assert merged["decree"]["number"] == "01-02"

    def test_empty_results(self):
        merged = merge_parsed_results([])
        assert merged["decree"] == {"number": "", "date": "", "municipality": ""}
        assert merged["schools"] == []


class TestIsTransientError:
    @pytest.mark.parametrize("msg", [
        "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred",
        "SSL handshake operation timed out",
        "429 Too Many Requests",
        "500 Internal Server Error",
        "Connection reset by peer",
        "Server disconnected",
        "Read timed out",
    ])
    def test_transient(self, msg):
        assert is_transient_error(Exception(msg)) is True

    @pytest.mark.parametrize("msg", [
        "Invalid JSON",
        "ValidationError: street must be string",
        "Not found",
    ])
    def test_not_transient(self, msg):
        assert is_transient_error(Exception(msg)) is False
