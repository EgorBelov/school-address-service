"""Тесты Pydantic-валидации ответов LLM."""
from app.services.ai.gigachat.schemas import (
    DecreeResponseModel,
    RuleModel,
    TerritoryResponseModel,
)


class TestRuleModel:
    def test_coerces_string_int(self):
        r = RuleModel.model_validate({"house_from": "19", "house_to": "39"})
        assert r.house_from == 19
        assert r.house_to == 39

    def test_coerces_list_to_csv(self):
        r = RuleModel.model_validate({"house_number": ["21", "23", "25"]})
        assert r.house_number == "21,23,25"

    def test_null_to_default(self):
        r = RuleModel.model_validate({
            "street": "Ленина",
            "house_rule_raw": None,
            "comment": None,
            "house_from": None,
        })
        assert r.house_rule_raw == ""
        assert r.comment == ""
        assert r.house_from is None

    def test_invalid_parity_falls_back_to_unknown(self):
        r = RuleModel.model_validate({"parity": "weird"})
        assert r.parity == "unknown"

    def test_invalid_int_string(self):
        r = RuleModel.model_validate({"house_from": "abc"})
        assert r.house_from is None

    def test_ignores_extra_fields(self):
        r = RuleModel.model_validate({"street": "X", "weird_field": 123})
        assert r.street == "X"
        # weird_field не сохраняется


class TestDecreeResponseModel:
    def test_full_roundtrip(self):
        raw = {
            "decree": {"number": "01", "date": "06.03.2025", "municipality": "Балашиха"},
            "schools": [
                {
                    "name": "Школа № 1",
                    "address": "ул. Ленина 1",
                    "rules": [
                        {"street": "Ленина", "house_from": "1", "house_to": "10", "parity": "all"},
                    ],
                }
            ],
        }
        m = DecreeResponseModel.model_validate(raw)
        assert m.decree.number == "01"
        assert m.schools[0].rules[0].house_from == 1

    def test_null_schools(self):
        m = DecreeResponseModel.model_validate({"schools": None})
        assert m.schools == []

    def test_null_address(self):
        m = DecreeResponseModel.model_validate({
            "schools": [{"name": "X", "address": None}]
        })
        assert m.schools[0].address == ""


class TestTerritoryResponseModel:
    def test_empty_rules(self):
        m = TerritoryResponseModel.model_validate({"rules": []})
        assert m.rules == []

    def test_null_rules(self):
        m = TerritoryResponseModel.model_validate({"rules": None})
        assert m.rules == []

    def test_full(self):
        m = TerritoryResponseModel.model_validate({
            "rules": [{"street": "X", "house_from": "1"}]
        })
        assert m.rules[0].house_from == 1
