import pytest

from app.services.parser.metadata_extractor import (
    extract_decree_date,
    extract_decree_metadata,
    extract_decree_number,
    extract_municipality,
)


class TestExtractDecreeNumber:
    @pytest.mark.parametrize("text,expected", [
        ("ПОСТАНОВЛЕНИЕ от 06.03.2025 № 01-02-252", "01-02-252"),
        ("постановление № 458-п", "458-п"),
        ("№ 135", "135"),
        ("№ 171-ПА", "171-ПА"),
    ])
    def test_extracts_number(self, text, expected):
        assert extract_decree_number(text) == expected

    def test_ignores_federal_law(self):
        """№ 273-ФЗ — это федеральный закон, а не наш номер."""
        text = "Федерального Закона от 29.12.2012 № 273-ФЗ Об образовании"
        assert extract_decree_number(text) == ""

    def test_ignores_overruled(self):
        text = (
            "Признать утратившим силу постановление Администрации "
            "Городского округа Балашиха от 05.03.2022 № 171-ПА"
        )
        assert extract_decree_number(text) == ""


class TestExtractDecreeDate:
    @pytest.mark.parametrize("text,expected", [
        ("от 06.03.2025", "06.03.2025"),
        ("от 6.3.2025", "06.03.2025"),
        ("от 06/03/25", "06.03.2025"),
        ("от 15 апреля 2024 года", "15.04.2024"),
        ("от 1 сентября 2023 г.", "01.09.2023"),
    ])
    def test_extracts_date(self, text, expected):
        assert extract_decree_date(text) == expected

    def test_ignores_federal_law_date(self):
        """Дата в ссылке на ФЗ не должна попасть."""
        text = "Закона от 29.12.2012 № 273-ФЗ"
        assert extract_decree_date(text) == ""


class TestExtractMunicipality:
    @pytest.mark.parametrize("text,expected", [
        ("Городского округа Балашиха", "Балашиха"),
        ("городского округа Электросталь от 15", "Электросталь"),
        ("города Перми", "Перми"),
        ("муниципального района Пушкинский", "Пушкинский"),
        ("муниципальный округ Электросталь", "Электросталь"),
    ])
    def test_extracts_municipality(self, text, expected):
        assert extract_municipality(text) == expected

    def test_does_not_grab_stop_words(self):
        """«Балашиха за» — «за» с маленькой буквы не должно попасть."""
        text = "О закреплении территории Городского округа Балашиха за муниципальными"
        assert extract_municipality(text) == "Балашиха"


class TestExtractDecreeMetadata:
    def test_full_metadata(self):
        text = (
            "Постановление администрации городского округа Балашиха "
            "от 06.03.2025 № 01-02-252 О закреплении территорий"
        )
        m = extract_decree_metadata(text)
        assert m["number"] == "01-02-252"
        assert m["date"] == "06.03.2025"
        assert m["municipality"] == "Балашиха"

    def test_partial(self):
        text = "город Пермь — какой-то текст"
        m = extract_decree_metadata(text)
        assert m["municipality"] == "Пермь"
        assert m["number"] == ""
