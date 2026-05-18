from app.services.parser.territory_regex_fallback import (
    extract_rules_from_territory_text,
    merge_llm_with_fallback,
)


class TestExtractRulesFromTerritoryText:
    def test_simple_street_list(self):
        text = "ул. Белякова; ул. Восточная; ул. Комсомольская"
        rules = extract_rules_from_territory_text(text)
        streets = [r["street"] for r in rules]
        assert "Белякова" in streets
        assert "Восточная" in streets
        assert "Комсомольская" in streets

    def test_street_with_houses(self):
        text = "проспект Ленина, 72, 74, 76"
        rules = extract_rules_from_territory_text(text)
        assert len(rules) == 1
        assert rules[0]["street"] == "Ленина"
        assert "72, 74, 76" in rules[0]["house_rule_raw"]

    def test_skips_mkr_prefix(self):
        """«мкр. Балашиха-3: ул. Х» — мкр-префикс не должен оторвать улицу."""
        text = "мкр. Балашиха-3: ул. Белякова; ул. Восточная"
        rules = extract_rules_from_territory_text(text)
        streets = [r["street"] for r in rules]
        assert "Белякова" in streets
        assert "Восточная" in streets

    def test_multiple_streets_with_houses(self):
        text = (
            "ул. Карла Маркса, 11, 11а, 13, 15; "
            "ул. Крупской, 8, 10, 12; "
            "шоссе Энтузиастов, 45 – 85 (нечетные)"
        )
        rules = extract_rules_from_territory_text(text)
        streets = [r["street"] for r in rules]
        assert "Карла Маркса" in streets
        assert "Крупской" in streets
        assert "Энтузиастов" in streets

    def test_empty(self):
        assert extract_rules_from_territory_text("") == []
        assert extract_rules_from_territory_text(None) == []


class TestMergeLLMWithFallback:
    def test_adds_missing_streets(self):
        llm = [{"street": "Ленина", "house_rule_raw": "1-10"}]
        fb = [
            {"street": "Ленина", "house_rule_raw": "1-10"},  # дубль
            {"street": "Пушкина", "house_rule_raw": "5"},     # новая
        ]
        merged = merge_llm_with_fallback(llm, fb)
        streets = [r["street"] for r in merged]
        assert streets.count("Ленина") == 1
        assert "Пушкина" in streets

    def test_normalizes_yo(self):
        """«Берёзовая» в LLM и «Березовая» в fallback — один город."""
        llm = [{"street": "Берёзовая", "house_rule_raw": ""}]
        fb = [{"street": "Березовая", "house_rule_raw": ""}]
        merged = merge_llm_with_fallback(llm, fb)
        assert len(merged) == 1

    def test_empty_lists(self):
        assert merge_llm_with_fallback([], []) == []
        assert len(merge_llm_with_fallback([{"street": "X"}], [])) == 1
