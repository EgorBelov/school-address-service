import pytest

from app.services.address.local_parser import parse_address_locally


class TestParseAddressLocally:
    @pytest.mark.parametrize("address,city,street,house", [
        ("Московская обл, г Балашиха, ул Ленина, д 42", "Балашиха", "Ленина", "42"),
        ("г Пермь, ул Монастырская, д 96", "Пермь", "Монастырская", "96"),
        ("г Пермь, Монастырская 96", "Пермь", "Монастырская", "96"),
        ("Пермский край, г Пермь, шоссе Космонавтов, 96", "Пермь", "Космонавтов", "96"),
        ("г Берёзники, ул Пятилетки, 22", "Берёзники", "Пятилетки", "22"),
        ("Москва, Тверская, 7", "Москва", "Тверская", "7"),
    ])
    def test_simple_addresses(self, address, city, street, house):
        p = parse_address_locally(address)
        assert p["city"] == city
        assert p["street"] == street
        assert p["house"] == house

    @pytest.mark.parametrize("address,street", [
        # Микрорайон НЕ должен попасть в street, должен пропуститься
        ("Московская обл, г Балашиха, мкр Железнодорожный, ул Маяковского, д 3", "Маяковского"),
        ("Московская обл, г Балашиха, мкр Балашиха-1, проспект Ленина, д 10", "Ленина"),
        ("г Пермь, мкр Камский, ул Маршала Рыбалко, 30", "Маршала Рыбалко"),
        ("Балашиха, квартал Лесной, ул Сосновая, 12", "Сосновая"),
    ])
    def test_skips_district_for_street(self, address, street):
        p = parse_address_locally(address)
        assert p["street"] == street, f"For {address!r} got street={p['street']!r}"

    def test_empty_returns_empty(self):
        assert parse_address_locally("") == {}

    def test_fallback_when_no_locality_marker(self):
        """«мкр X, Y 3» — мкр пропускается, Y 3 → улица + дом."""
        p = parse_address_locally("мкр Железнодорожный, Маяковского 3")
        assert p["street"] == "Маяковского"
        assert p["house"] == "3"

    def test_house_with_corp(self):
        p = parse_address_locally("г Пермь, ул Ленина, д 42к1")
        assert p["house"] == "42к1"
