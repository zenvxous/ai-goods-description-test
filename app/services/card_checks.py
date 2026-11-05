"""Deterministic checks of an LLM-generated card against the input data.

The prompt asks the model not to invent anything, but the final guarantee comes
from here: every number in generated texts and every spec value must be traceable
to the input.
"""

import re

from app.core.constants import (
    NO_DATA,
    SEARCH_QUERIES_MAX,
    SEARCH_QUERIES_MIN,
    SEO_DESCRIPTION_MAX_LEN,
    SEO_DESCRIPTION_MIN_LEN,
    SEO_TITLE_MAX_LEN,
)
from app.schemas.products import ProductCard, ProductInput

_CHAR_MAP = str.maketrans(
    {
        "–": "-",
        "—": "-",
        "−": "-",
        "‑": "-",
        " ": " ",
        "ё": "е",
    }
)
_DECIMAL_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")
_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# Word stems that usually mark claims the model made up rather than took from the input.
# They are flagged only when absent from the input, so a real "надёжность" passes.
UNSUPPORTED_CLAIM_STEMS = (
    "надежн",
    "гарант",
    "долговеч",
    "герметичн",
    "вибрац",
    "широк",
    "уникальн",
    "лучш",
    "идеальн",
    "высочайш",
    "воздейств",
    "соответству",
    "нормам",
)
INDUSTRY_STEMS = (
    "нефтегаз",
    "нефтехим",
    "энергетик",
    "пищев",
    "химическ",
    "металлург",
    "фармацевт",
    "горнодобыв",
    "жкх",
    "судострое",
    "машинострое",
    "сельскохоз",
)


def normalize(text: str) -> str:
    text = text.lower().translate(_CHAR_MAP)
    text = _DECIMAL_COMMA_RE.sub(".", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(normalize(text)))


def source_text(product: ProductInput) -> str:
    parts = [product.name, product.manufacturer or "", product.description or ""]
    for name, value in product.specs.items():
        parts.append(f"{name}: {value or ''}")
    return "\n".join(parts)


# Device types: the model must not swap "манометр" for "датчик давления" in queries
DEVICE_TYPE_STEMS = (
    "манометр",
    "вакуумметр",
    "мановакуумметр",
    "датчик",
    "преобразовател",
    "термометр",
    "термопар",
    "термосопротивл",
    "расходомер",
    "счетчик",
    "уровнемер",
    "сигнализатор",
    "реле",
    "регулятор",
    "газоанализатор",
)


_WORD_RE = re.compile(r"[^\W\d_]+")


def word_stems(text: str) -> set[str]:
    """Crude Russian stemming: drop the ending so "шкала" and "шкале" match."""
    return {
        word[: max(3, min(6, len(word) - 2))]
        for word in _WORD_RE.findall(normalize(text))
        if len(word) >= 4
    }


def find_unsupported_words(text: str, source: str, stems: tuple[str, ...]) -> list[str]:
    """Words in text that start with one of the stems absent from the source."""
    found: list[str] = []
    normalized = normalize(text)
    for stem in stems:
        if stem in source:
            continue
        for word in re.findall(rf"\w*{stem}\w*", normalized):
            if word not in found:
                found.append(word)
    return found


def _is_no_data(value: str) -> bool:
    return normalize(value) == normalize(NO_DATA)


def check_card(card: ProductCard, product: ProductInput) -> list[str]:
    """Return a list of human-readable issues; empty list means the card passed."""
    issues: list[str] = []
    source = normalize(source_text(product))
    source_numbers = extract_numbers(source)
    source_stems = word_stems(source)

    title_len = len(card.seo_title)
    if not card.seo_title.strip():
        issues.append("seo_title пустой")
    elif title_len > SEO_TITLE_MAX_LEN:
        issues.append(f"seo_title длиной {title_len} символов, максимум {SEO_TITLE_MAX_LEN}")

    desc_len = len(card.seo_description)
    if not SEO_DESCRIPTION_MIN_LEN <= desc_len <= SEO_DESCRIPTION_MAX_LEN:
        issues.append(
            f"seo_description длиной {desc_len} символов, нужно "
            f"{SEO_DESCRIPTION_MIN_LEN}–{SEO_DESCRIPTION_MAX_LEN}"
        )

    queries = [q for q in card.search_queries if q.strip()]
    if not SEARCH_QUERIES_MIN <= len(queries) <= SEARCH_QUERIES_MAX:
        issues.append(
            f"search_queries содержит {len(queries)} запросов, нужно "
            f"{SEARCH_QUERIES_MIN}–{SEARCH_QUERIES_MAX}"
        )

    if not card.key_specs:
        issues.append("key_specs пустой")

    for spec in card.key_specs:
        if _is_no_data(spec.value):
            continue
        value_numbers = extract_numbers(spec.value)
        if value_numbers:
            unknown = sorted(value_numbers - source_numbers)
            if unknown:
                issues.append(
                    f"характеристика «{spec.name}»: числа {', '.join(unknown)} "
                    "отсутствуют во входных данных"
                )
        elif normalize(spec.value) not in source and not word_stems(spec.value) <= source_stems:
            issues.append(
                f"характеристика «{spec.name}»: значение «{spec.value}» "
                "не найдено во входных данных"
            )

    texts = {
        "seo_title": card.seo_title,
        "seo_description": card.seo_description,
        "search_queries": " ".join(card.search_queries),
        "commercial": " ".join([*card.commercial.audience, *card.commercial.tasks]),
    }
    for field, text in texts.items():
        unknown = sorted(extract_numbers(text) - source_numbers)
        if unknown:
            issues.append(f"{field}: числа {', '.join(unknown)} отсутствуют во входных данных")

    claim_texts = {
        "seo_description": card.seo_description,
        "commercial.tasks": " ".join(card.commercial.tasks),
    }
    for field, text in claim_texts.items():
        if words := find_unsupported_words(text, source, UNSUPPORTED_CLAIM_STEMS):
            issues.append(
                f"{field}: формулировки «{'», «'.join(words)}» не подтверждаются входными данными"
            )
    type_texts = {
        "seo_title": card.seo_title,
        "search_queries": " ".join(card.search_queries),
    }
    for field, text in type_texts.items():
        if words := find_unsupported_words(text, source, DEVICE_TYPE_STEMS):
            issues.append(
                f"{field}: тип прибора «{'», «'.join(words)}» не соответствует входным данным"
            )

    industry_texts = {
        "seo_description": card.seo_description,
        "commercial": " ".join([*card.commercial.audience, *card.commercial.tasks]),
    }
    for field, text in industry_texts.items():
        if words := find_unsupported_words(text, source, INDUSTRY_STEMS):
            issues.append(
                f"{field}: отрасли «{'», «'.join(words)}» не упоминаются во входных данных"
            )

    return issues
