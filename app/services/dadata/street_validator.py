from app.services.dadata.client import suggest_address
from app.services.address.normalize import normalize_street_name


def validate_street_with_dadata(
    locality: str | None,
    street: str
) -> dict:
    query_parts = []

    if locality:
        query_parts.append(locality)

    query_parts.append(street)

    query = ", ".join(query_parts)

    suggestions = suggest_address(query)

    if not suggestions:
        return {
            "status": "needs_review",
            "normalized_street": normalize_street_name(street),
            "dadata_value": None,
            "confidence": "low",
            "comment": "DaData не нашла подходящую улицу"
        }

    best = suggestions[0]
    data = best.get("data", {})

    dadata_street = data.get("street") or data.get("street_with_type")

    if not dadata_street:
        return {
            "status": "needs_review",
            "normalized_street": normalize_street_name(street),
            "dadata_value": best.get("value"),
            "confidence": "low",
            "comment": "DaData нашла адрес, но не вернула улицу"
        }

    source_norm = normalize_street_name(street)
    dadata_norm = normalize_street_name(dadata_street)

    if source_norm == dadata_norm:
        return {
            "status": "verified",
            "normalized_street": dadata_norm,
            "dadata_value": best.get("value"),
            "confidence": "high",
            "comment": "Улица подтверждена через DaData"
        }

    return {
        "status": "needs_review",
        "normalized_street": dadata_norm,
        "dadata_value": best.get("value"),
        "confidence": "medium",
        "comment": f"DaData предлагает другое написание: {dadata_street}"
    }