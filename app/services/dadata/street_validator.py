from functools import lru_cache

from app.services.address.normalize import normalize_street_name
from app.services.dadata.client import suggest_address


@lru_cache(maxsize=2048)
def _cached_suggest(query: str) -> tuple:
    """
    Кэшируем DaData по нормализованному запросу. У постановления
    типичный набор ~50–500 уникальных улиц, и одна улица часто
    привязана к нескольким школам. Без кэша — сотни лишних HTTP-вызовов
    и риск таймаута на сохранении.
    Возвращаем кортеж (для иммутабельности lru_cache), а не dict.
    """
    suggestions = suggest_address(query) or []
    if not suggestions:
        return tuple()

    best = suggestions[0]
    data = best.get("data") or {}
    return (
        best.get("value"),
        data.get("street") or data.get("street_with_type"),
    )


def validate_street_with_dadata(
    locality: str | None,
    street: str,
) -> dict:
    query_parts = []
    if locality:
        query_parts.append(locality)
    query_parts.append(street)
    query = ", ".join(query_parts).strip()

    cached = _cached_suggest(query)

    if not cached:
        return {
            "status": "needs_review",
            "normalized_street": normalize_street_name(street),
            "dadata_value": None,
            "confidence": "low",
            "comment": "DaData не нашла подходящую улицу",
        }

    dadata_value, dadata_street = cached

    if not dadata_street:
        return {
            "status": "needs_review",
            "normalized_street": normalize_street_name(street),
            "dadata_value": dadata_value,
            "confidence": "low",
            "comment": "DaData нашла адрес, но не вернула улицу",
        }

    source_norm = normalize_street_name(street)
    dadata_norm = normalize_street_name(dadata_street)

    if source_norm == dadata_norm:
        return {
            "status": "verified",
            "normalized_street": dadata_norm,
            "dadata_value": dadata_value,
            "confidence": "high",
            "comment": "Улица подтверждена через DaData",
        }

    return {
        "status": "needs_review",
        "normalized_street": dadata_norm,
        "dadata_value": dadata_value,
        "confidence": "medium",
        "comment": f"DaData предлагает другое написание: {dadata_street}",
    }
