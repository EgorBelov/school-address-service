import pytest

from app.services.address.normalize import normalize_locality, normalize_street_name


class TestNormalizeStreetName:
    @pytest.mark.parametrize("raw,expected", [
        ("ул. Ленина", "ленина"),
        ("Ленина", "ленина"),
        ("проспект Ленина", "ленина"),
        ("пр-кт Ленина", "ленина"),
        ("шоссе Энтузиастов", "энтузиастов"),
        ("ш Энтузиастов", "энтузиастов"),
        ("ш. Энтузиастов", "энтузиастов"),
        ("переулок Школьный", "школьный"),
        ("пер. Школьный", "школьный"),
        ("Школьная улица", "школьная"),
        ("бульвар Нестерова", "нестерова"),
        ("б-р Нестерова", "нестерова"),
        ("набережная Шуйская", "шуйская"),
        ("наб. Шуйская", "шуйская"),
        ("площадь Победы", "победы"),
        ("пл. Победы", "победы"),
        ("Маршала Рыбалко", "маршала рыбалко"),
        ("40 лет Победы", "40 лет победы"),
        ("9-15 линия", "9-15"),
    ])
    def test_strips_street_types(self, raw, expected):
        assert normalize_street_name(raw) == expected

    def test_none_returns_empty(self):
        assert normalize_street_name(None) == ""

    def test_empty_string(self):
        assert normalize_street_name("") == ""

    def test_does_not_break_word_school(self):
        """«школа № 5» не должен превратиться в «школа № 5» с обрезанной «ш»."""
        assert normalize_street_name("школа № 5") == "школа № 5"

    def test_does_not_break_word_pereval(self):
        """«Перевальная» не должно стать «евальная»."""
        result = normalize_street_name("Перевальная")
        assert "перевальная" in result


class TestNormalizeLocality:
    @pytest.mark.parametrize("raw,expected", [
        ("Балашиха", "балашиха"),
        ("г Балашиха", "балашиха"),
        ("г. Балашиха", "балашиха"),
        ("город Балашиха", "балашиха"),
        ("Городской округ Балашиха", "балашиха"),
        ("г.о. Балашиха", "балашиха"),
        ("Московская обл, г Балашиха", "балашиха"),
        ("Пермский край, г Пермь", "пермь"),
        ("Берёзники", "берёзники"),
        ("г Березники", "березники"),
        ("п Сосновка", "сосновка"),
        ("д Малиновка", "малиновка"),
        ("муниципальный район Пушкинский", "пушкинский"),
    ])
    def test_strips_locality_prefix(self, raw, expected):
        assert normalize_locality(raw) == expected

    def test_none_returns_empty(self):
        assert normalize_locality(None) == ""
