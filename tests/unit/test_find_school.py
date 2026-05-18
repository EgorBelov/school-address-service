from dataclasses import dataclass

import pytest

from app.services.search.find_school import (
    _locality_match,
    is_house_matches,
    is_locality_matches,
)


@dataclass
class FakeRule:
    """Минимальный «дубль» AddressRule для unit-тестов."""
    house_rule_raw: str = ""
    rule_type: str = "unknown"
    parity: str = "all"
    house_from: int | None = None
    house_to: int | None = None
    house_number: str | None = None
    house_numbers: str | None = None
    exceptions: str | None = None
    locality: str | None = None
    school = None


class TestLocalityMatch:
    @pytest.mark.parametrize("a,b", [
        ("Пермь", "Перми"),
        ("Берёзники", "Березников"),
        ("Берёзники", "Березники"),
        ("Балашиха", "Балашихи"),
        ("Москва", "Москвы"),
        ("Электросталь", "Электростали"),
    ])
    def test_padezhi_match(self, a, b):
        assert _locality_match(a, b) is True

    @pytest.mark.parametrize("a,b", [
        ("Балашиха", "Балахна"),
        ("Пермь", "Тверь"),
        ("Москва", "Минск"),
    ])
    def test_different_cities_no_match(self, a, b):
        assert _locality_match(a, b) is False

    def test_empty_no_match(self):
        assert _locality_match("", "Пермь") is False
        assert _locality_match("Пермь", "") is False


class TestIsHouseMatches:
    def test_exact_list_match(self):
        rule = FakeRule(house_numbers="10,12,14")
        assert is_house_matches(rule, "12") is True
        assert is_house_matches(rule, "11") is False

    def test_exact_list_with_letter(self):
        rule = FakeRule(house_numbers="10а,12,14")
        assert is_house_matches(rule, "10а") is True

    def test_range_even(self):
        rule = FakeRule(rule_type="range", parity="even", house_from=22, house_to=48)
        assert is_house_matches(rule, "22") is True
        assert is_house_matches(rule, "48") is True
        assert is_house_matches(rule, "30") is True
        assert is_house_matches(rule, "21") is False  # нечётный
        assert is_house_matches(rule, "50") is False  # за диапазоном

    def test_range_odd(self):
        rule = FakeRule(rule_type="range", parity="odd", house_from=19, house_to=39)
        assert is_house_matches(rule, "19") is True
        assert is_house_matches(rule, "39") is True
        assert is_house_matches(rule, "20") is False
        assert is_house_matches(rule, "41") is False

    def test_all_houses(self):
        rule = FakeRule(rule_type="all", house_rule_raw="все")
        assert is_house_matches(rule, "1") is True
        assert is_house_matches(rule, "999") is True

    def test_exceptions(self):
        rule = FakeRule(
            rule_type="all",
            house_rule_raw="все",
            exceptions="11,15",
        )
        assert is_house_matches(rule, "11") is False
        assert is_house_matches(rule, "10") is True

    def test_up_to(self):
        rule = FakeRule(rule_type="up_to", house_to=18)
        assert is_house_matches(rule, "10") is True
        assert is_house_matches(rule, "18") is True
        assert is_house_matches(rule, "20") is False

    def test_from_to_end(self):
        rule = FakeRule(rule_type="from_to_end", house_from=36)
        assert is_house_matches(rule, "36") is True
        assert is_house_matches(rule, "100") is True
        assert is_house_matches(rule, "35") is False

    def test_no_house_no_match(self):
        rule = FakeRule(rule_type="range", house_from=10, house_to=20)
        assert is_house_matches(rule, None) is False

    def test_house_with_slash(self):
        """«12/3» → берём 12 как номер дома."""
        rule = FakeRule(rule_type="range", parity="even", house_from=10, house_to=20)
        assert is_house_matches(rule, "12/3") is True


class TestIsLocalityMatches:
    def test_no_target_passes_filter(self):
        rule = FakeRule(locality="Пермь")
        assert is_locality_matches(rule, "") is True

    def test_match_by_rule_locality(self):
        rule = FakeRule(locality="г. Пермь")
        assert is_locality_matches(rule, "Пермь") is True
        assert is_locality_matches(rule, "Москва") is False

    def test_match_by_municipality(self):
        class FakeMuni:
            name = "Перми"

        class FakeSchool:
            municipality = FakeMuni()

        rule = FakeRule(locality=None)
        rule.school = FakeSchool()
        assert is_locality_matches(rule, "Пермь") is True
        assert is_locality_matches(rule, "Балашиха") is False

    def test_no_candidates_passes(self):
        rule = FakeRule(locality=None)
        # school = None, нет данных → best effort, пропускаем фильтр
        assert is_locality_matches(rule, "Пермь") is True
