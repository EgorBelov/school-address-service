import pytest

from app.services.parser.save_parsed_decree import sanitize_school_address


class TestSanitizeSchoolAddress:
    @pytest.mark.parametrize("address", [
        "г. Балашиха, ул. Ленина, д. 10",
        "ул. Пятилетки, д. 21",
        "г. Берёзники, ул. Пятилетки, д. 21, корп. 1",
        "ул. Школьная",
        "Москва, Тверская 7",
    ])
    def test_valid_addresses_kept(self, address):
        assert sanitize_school_address(address) is not None

    @pytest.mark.parametrize("garbage", [
        "ул. Объединения, 4, 6",  # 2 числа без д./г.
        "мкр. Балашиха-1: ул. Живописная; проспект Ленина, 10, 10а, 12",
        "проспект Ленина, 10, 10а, 12, 14",  # >2 чисел
        "ул. Мира; ул. Молодежная (кроме д.11)",  # точка с запятой
    ])
    def test_garbage_rejected(self, garbage):
        assert sanitize_school_address(garbage) is None

    def test_none_returns_none(self):
        assert sanitize_school_address(None) is None

    def test_empty_string_returns_none(self):
        assert sanitize_school_address("") is None

    def test_too_long_rejected(self):
        long_text = "ул. Очень Длинная " * 50
        assert sanitize_school_address(long_text) is None
