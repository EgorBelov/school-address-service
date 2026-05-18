import pytest

from app.services.parser.rule_normalizer import detect_parity, normalize_rule_fields


class TestDetectParity:
    @pytest.mark.parametrize("raw,expected", [
        ("четные дома", "even"),
        ("чётные", "even"),
        ("нечетные дома", "odd"),
        ("нечётные", "odd"),
        ("45 – 85 (нечетные)", "odd"),
        ("четные и нечетные до дома 18", "all"),
        ("1-17", None),
        ("", None),
        ("просто текст", None),
    ])
    def test_parity(self, raw, expected):
        assert detect_parity(raw) == expected

    def test_chet_inside_nechet_is_odd(self):
        """«нечет» содержит «чет» как подстроку — не должно дать «all»."""
        assert detect_parity("нечетные") == "odd"


class TestNormalizeRuleFields:
    def test_range(self):
        r = normalize_rule_fields({"house_rule_raw": "1-17"})
        assert r["rule_type"] == "range"
        assert r["house_from"] == 1
        assert r["house_to"] == 17

    def test_range_with_long_dash(self):
        r = normalize_rule_fields({"house_rule_raw": "45 – 85"})
        assert r["rule_type"] == "range"
        assert r["house_from"] == 45
        assert r["house_to"] == 85

    def test_range_with_parity(self):
        r = normalize_rule_fields({"house_rule_raw": "45 – 85 (нечетные)"})
        assert r["rule_type"] == "range"
        assert r["house_from"] == 45
        assert r["house_to"] == 85
        assert r["parity"] == "odd"

    def test_from_to_end(self):
        r = normalize_rule_fields({"house_rule_raw": "начиная с дома 36"})
        assert r["rule_type"] == "from_to_end"
        assert r["house_from"] == 36
        assert r["house_to"] is None

    def test_up_to(self):
        r = normalize_rule_fields({"house_rule_raw": "до дома 18"})
        assert r["rule_type"] == "up_to"
        assert r["house_to"] == 18
        assert r["house_from"] is None

    def test_exact_list(self):
        r = normalize_rule_fields({"house_rule_raw": "10, 10а, 12, 14"})
        assert r["rule_type"] == "exact_list"
        assert "10" in r["house_numbers"]
        assert "10а" in r["house_numbers"]

    def test_all_except(self):
        r = normalize_rule_fields({"house_rule_raw": "кроме д.11"})
        assert r["rule_type"] == "all_except"
        assert "11" in r["exceptions"]

    def test_empty_is_all(self):
        r = normalize_rule_fields({"house_rule_raw": ""})
        assert r["rule_type"] == "all"

    def test_vse_is_all(self):
        r = normalize_rule_fields({"house_rule_raw": "все"})
        assert r["rule_type"] == "all"

    def test_does_not_override_existing_parity(self):
        """Если LLM явно дал parity — не перетираем."""
        r = normalize_rule_fields({
            "house_rule_raw": "1-17",  # parity недетектится из raw
            "parity": "even",
        })
        assert r["parity"] == "even"
