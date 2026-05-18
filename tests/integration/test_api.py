"""API-тесты через FastAPI TestClient (с моками DaData/GigaChat)."""
import json
from unittest.mock import patch


class TestPublicAPI:
    def test_index_returns_form(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "Поиск" in r.text or "Найти" in r.text or "школ" in r.text.lower()

    def test_search_empty_address_returns_friendly_error(self, client):
        # locality+street есть, дом нет → friendly error
        r = client.post("/search", data={"address": "г Москва"})
        assert r.status_code == 200
        assert "распознан не полностью" in r.text or "не найдена" in r.text

    def test_suggest_returns_json(self, client):
        # DaData замокана как пустой список → отдаём пустой JSON
        r = client.get("/api/address/suggest?q=Ленина")
        assert r.status_code == 200
        assert r.json() == []


class TestAdminPages:
    def test_upload_page(self, client):
        r = client.get("/admin/upload")
        assert r.status_code == 200

    def test_rules_page_empty_db(self, client):
        r = client.get("/admin/rules")
        assert r.status_code == 200

    def test_validation_page_empty_db(self, client):
        r = client.get("/admin/validation")
        assert r.status_code == 200


class TestSaveParsedAPI:
    def test_save_parsed_via_post(self, client):
        parsed = {
            "decree": {"number": "TEST-1", "date": "01.01.2025", "municipality": "TestCity"},
            "schools": [{
                "name": "ТестШкола",
                "address": "ул. Тест, д. 1",
                "rules": [{"street": "Тест", "house_rule_raw": "1-5", "parity": "all"}],
            }],
        }
        r = client.post(
            "/admin/save-parsed",
            data={"parsed_json": json.dumps(parsed)},
        )
        assert r.status_code == 200
        assert "TestCity" in r.text or "1 школ" in r.text or "1" in r.text


class TestSearchEndToEnd:
    def test_search_with_seeded_data(self, client, db):
        """Сохраняем правило → ищем через UI → должна найтись."""
        from app.services.parser.save_parsed_decree import save_parsed_decree

        # `db` и `client` шарят общую in-memory БД через db_session_factory
        save_parsed_decree(db, {
            "decree": {"municipality": "TestCity"},
            "schools": [{
                "name": "Test School",
                "rules": [{
                    "street": "Ленина",
                    "house_rule_raw": "1-10",
                    "house_from": 1, "house_to": 10,
                    "parity": "all", "rule_type": "range",
                }],
            }],
        })

        # Подменим clean_address чтобы вернуть локальные результаты
        with patch(
            "app.main.clean_address",
            return_value={
                "city": "TestCity", "street": "Ленина", "house": "5",
                "result": "TestCity, Ленина, 5",
            },
        ):
            r = client.post("/search", data={"address": "TestCity, Ленина, 5"})

        assert r.status_code == 200
        assert "Test School" in r.text

    def test_search_unknown_address(self, client):
        with patch(
            "app.main.clean_address",
            return_value={
                "city": "Vanity", "street": "Несуществующая", "house": "1",
                "result": "...",
            },
        ):
            r = client.post("/search", data={"address": "Vanity, Несуществующая, 1"})
        assert r.status_code == 200
        assert "не найдена" in r.text
