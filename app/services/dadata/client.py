from dadata import Dadata

from app.core.config import settings


def suggest_address(query: str):
    if not settings.dadata_token:
        return []

    with Dadata(settings.dadata_token, settings.dadata_secret) as dadata:
        return dadata.suggest("address", query)


def clean_address(address: str):
    if not settings.dadata_token:
        return None

    with Dadata(settings.dadata_token, settings.dadata_secret) as dadata:
        result = dadata.clean("address", address)
        return result