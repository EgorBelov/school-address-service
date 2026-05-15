"""
Pydantic-модели ответов GigaChat. Используются для:
1) Принудительной типовой коэрсии (LLM возвращает "23" вместо 23 — приведём).
2) Отсева мусорных полей (extra="ignore").
3) Понятной ошибки, если ответ совсем не похож на ожидаемую структуру.
"""
import json as _json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Parity = Literal["all", "even", "odd", "mixed", "unknown"]


class RuleModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    locality: str = ""
    street: str = ""
    house_rule_raw: str = ""
    parity: Parity = "unknown"
    house_from: int | None = None
    house_to: int | None = None
    house_number: str | None = None
    comment: str = ""

    @field_validator(
        "locality", "street", "house_rule_raw", "comment",
        mode="before",
    )
    @classmethod
    def _coerce_str(cls, value):
        if value is None:
            return ""
        return str(value)

    @field_validator("parity", mode="before")
    @classmethod
    def _normalize_parity(cls, value):
        if value in ("all", "even", "odd", "mixed", "unknown"):
            return value
        return "unknown"

    @field_validator("house_from", "house_to", mode="before")
    @classmethod
    def _coerce_int(cls, value):
        if value is None or value == "" or value == "null":
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            value = value.strip()
            if value.isdigit():
                return int(value)
        return None

    @field_validator("house_number", mode="before")
    @classmethod
    def _coerce_house_number(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            joined = ",".join(str(x) for x in value if x is not None and str(x).strip())
            return joined or None
        if isinstance(value, dict):
            return _json.dumps(value, ensure_ascii=False)
        text = str(value).strip()
        return text or None


class SchoolModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = ""
    address: str = ""
    rules: list[RuleModel] = Field(default_factory=list)

    @field_validator("name", "address", mode="before")
    @classmethod
    def _coerce_str(cls, value):
        if value is None:
            return ""
        return str(value)

    @field_validator("rules", mode="before")
    @classmethod
    def _coerce_rules(cls, value):
        if value is None:
            return []
        return value


class DecreeMetaModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    number: str = ""
    date: str = ""
    municipality: str = ""

    @field_validator("number", "date", "municipality", mode="before")
    @classmethod
    def _coerce_str(cls, value):
        if value is None:
            return ""
        return str(value)


class DecreeResponseModel(BaseModel):
    """Полный ответ парсера всего постановления."""
    model_config = ConfigDict(extra="ignore")

    decree: DecreeMetaModel = Field(default_factory=DecreeMetaModel)
    schools: list[SchoolModel] = Field(default_factory=list)

    @field_validator("schools", mode="before")
    @classmethod
    def _coerce_schools(cls, value):
        if value is None:
            return []
        return value


class TerritoryResponseModel(BaseModel):
    """Ответ парсера для одной школы — только список её правил."""
    model_config = ConfigDict(extra="ignore")

    rules: list[RuleModel] = Field(default_factory=list)

    @field_validator("rules", mode="before")
    @classmethod
    def _coerce_rules(cls, value):
        if value is None:
            return []
        return value
