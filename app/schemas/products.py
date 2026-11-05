from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import (
    MAX_DESCRIPTION_LEN,
    MAX_FIELD_LEN,
    MAX_SPECS,
    NO_DATA,
    SEARCH_QUERIES_MAX,
    SEARCH_QUERIES_MIN,
    SEO_DESCRIPTION_MAX_LEN,
    SEO_DESCRIPTION_MIN_LEN,
    SEO_TITLE_MAX_LEN,
)

PRODUCT_EXAMPLE: dict[str, Any] = {
    "name": "Манометр показывающий DM 02",
    "manufacturer": "Манотомь",
    "specs": {
        "диапазон измерений": "0–1,6 МПа",
        "класс точности": "1,5",
        "присоединение": "G1/2",
        "диаметр корпуса": "100 мм",
    },
    "description": "Прибор предназначен для измерения избыточного давления...",
}


class ProductInput(BaseModel):
    """Raw product data provided by a content manager."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={"examples": [PRODUCT_EXAMPLE]},
    )

    name: str = Field(min_length=1, max_length=MAX_FIELD_LEN, description="Название товара")
    manufacturer: str | None = Field(
        default=None, max_length=MAX_FIELD_LEN, description="Производитель"
    )
    specs: dict[str, str | None] = Field(
        default_factory=dict,
        max_length=MAX_SPECS,
        description="Характеристики: название → значение",
    )
    description: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_LEN,
        description="Описание или фрагмент технического паспорта",
    )

    @field_validator("manufacturer", "description", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("specs", mode="before")
    @classmethod
    def _normalize_specs(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            return value  # let pydantic report the type error

        normalized: dict[str, str | None] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            if not key:
                raise ValueError("название характеристики не может быть пустым")
            if raw_value is None:
                normalized[key] = None
            elif isinstance(raw_value, bool):
                normalized[key] = "да" if raw_value else "нет"
            elif isinstance(raw_value, int | float):
                normalized[key] = str(raw_value)
            elif isinstance(raw_value, str):
                normalized[key] = raw_value.strip() or None
            else:
                raise ValueError(f"значение характеристики «{key}» должно быть строкой или числом")
        return normalized

    def missing_fields(self) -> list[str]:
        """Human-readable list of fields that are absent in the input."""
        missing: list[str] = []
        if self.manufacturer is None:
            missing.append("производитель")
        if not self.specs:
            missing.append("характеристики")
        missing.extend(
            f"значение характеристики «{name}»"
            for name, value in self.specs.items()
            if value is None
        )
        if self.description is None:
            missing.append("описание")
        return missing


class SpecItem(BaseModel):
    name: str = Field(description="Название характеристики")
    value: str = Field(
        description=f"Значение дословно из входных данных или «{NO_DATA}», если его нет"
    )


class CommercialBlock(BaseModel):
    audience: list[str] = Field(description="Кому подходит прибор (2–4 пункта)")
    tasks: list[str] = Field(description="Какие задачи решает прибор (2–4 пункта)")


class ProductCard(BaseModel):
    """Draft product card. Shape is also used as the LLM response schema."""

    seo_title: str = Field(description=f"SEO-заголовок до {SEO_TITLE_MAX_LEN} символов")
    seo_description: str = Field(
        description=(f"SEO-описание {SEO_DESCRIPTION_MIN_LEN}–{SEO_DESCRIPTION_MAX_LEN} символов")
    )
    key_specs: list[SpecItem] = Field(description="Структурированный список характеристик")
    search_queries: list[str] = Field(
        description=f"{SEARCH_QUERIES_MIN}–{SEARCH_QUERIES_MAX} поисковых запросов"
    )
    commercial: CommercialBlock = Field(description="Краткий блок для менеджера")
    missing_data: list[str] = Field(description="Данные, которые отсутствуют или требуют уточнения")


class ProductCardResponse(BaseModel):
    card: ProductCard
    warnings: list[str] = Field(
        default_factory=list,
        description="Замечания автоматической проверки, которые стоит проверить вручную",
    )
