from dadata import Dadata

from app.core.config import settings


def suggest_address(query: str):
    """Подсказки адресов. При недоступности DaData — пустой список."""
    if not settings.dadata_token:
        return []

    try:
        with Dadata(settings.dadata_token, settings.dadata_secret) as dadata:
            return dadata.suggest("address", query) or []
    except Exception as e:
        print(f"[dadata] suggest failed: {e}")
        return []


def clean_address(address: str):
    """
    Нормализация и разбор адреса через DaData.
    Возвращает dict в формате DaData либо None — тогда вызывающий
    должен сделать локальный fallback-парсинг (см. parse_address_locally).
    """
    if not settings.dadata_token:
        return None

    try:
        with Dadata(settings.dadata_token, settings.dadata_secret) as dadata:
            return dadata.clean("address", address)
    except Exception as e:
        print(f"[dadata] clean failed: {e}")
        return None
