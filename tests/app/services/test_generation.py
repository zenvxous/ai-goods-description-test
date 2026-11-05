from unittest.mock import Mock

import httpx2 as httpx
import openai
import pytest

from app.core.config import Settings
from app.exceptions.llm import LLMResponseError, LLMTimeoutError, LLMUnavailableError
from app.exceptions.products import InsufficientProductDataError
from app.schemas.products import ProductCard, ProductInput, SpecItem
from app.services.generation import (
    CARD_JSON_SCHEMA,
    ProductCardGenerator,
    merge_missing_fields,
    parse_card,
)
from tests.helpers.llm import make_completion

_REQUEST = httpx.Request("POST", "https://llm.test/v1/chat/completions")


def _generator(client: Mock, **overrides: object) -> ProductCardGenerator:
    settings = Settings(_env_file=None).model_copy(update=overrides)
    return ProductCardGenerator(client, settings)


def test_schema_is_strict() -> None:
    assert CARD_JSON_SCHEMA["additionalProperties"] is False
    assert set(CARD_JSON_SCHEMA["required"]) == set(ProductCard.model_fields)
    for definition in CARD_JSON_SCHEMA["$defs"].values():
        assert definition["additionalProperties"] is False


def test_parse_card_strips_code_fence(valid_card: ProductCard) -> None:
    content = f"```json\n{valid_card.model_dump_json()}\n```"

    assert parse_card(content) == valid_card


def test_merge_missing_fields_puts_input_gaps_first_without_dupes(
    valid_card: ProductCard,
) -> None:
    product = ProductInput(name="Манометр", specs={"диапазон": "0–1 МПа"})
    valid_card.missing_data = [
        "Масса прибора",
        " масса  прибора.",
        "Не указано: описание",
        "Производитель",
    ]

    merge_missing_fields(valid_card, product)

    assert valid_card.missing_data == [
        "Не указано: производитель",
        "Не указано: описание",
        "Масса прибора",
    ]


async def test_returns_card_without_warnings(
    fake_llm_client: Mock, product: ProductInput, valid_card: ProductCard
) -> None:
    fake_llm_client.chat.completions.create.return_value = make_completion(
        valid_card.model_dump_json()
    )

    result = await _generator(fake_llm_client).generate(product)

    assert result.card == valid_card
    assert result.warnings == []
    assert fake_llm_client.chat.completions.create.await_count == 1
    kwargs = fake_llm_client.chat.completions.create.await_args.kwargs
    assert kwargs["response_format"]["type"] == "json_schema"


async def test_repairs_card_with_invented_value(
    fake_llm_client: Mock, product: ProductInput, valid_card: ProductCard
) -> None:
    bad_card = valid_card.model_copy(deep=True)
    bad_card.key_specs.append(SpecItem(name="Степень защиты", value="IP65"))
    fake_llm_client.chat.completions.create.side_effect = [
        make_completion(bad_card.model_dump_json()),
        make_completion(valid_card.model_dump_json()),
    ]

    result = await _generator(fake_llm_client).generate(product)

    assert result.card == valid_card
    assert result.warnings == []
    repair_messages = fake_llm_client.chat.completions.create.await_args.kwargs["messages"]
    assert repair_messages[-2]["role"] == "assistant"
    assert "Степень защиты" in repair_messages[-1]["content"]


async def test_returns_warnings_when_repair_fails(
    fake_llm_client: Mock, product: ProductInput, valid_card: ProductCard
) -> None:
    valid_card.key_specs.append(SpecItem(name="Степень защиты", value="IP65"))
    fake_llm_client.chat.completions.create.return_value = make_completion(
        valid_card.model_dump_json()
    )

    result = await _generator(fake_llm_client).generate(product)

    assert fake_llm_client.chat.completions.create.await_count == 2
    assert len(result.warnings) == 1
    assert "Степень защиты" in result.warnings[0]


async def test_invalid_json_is_retried_then_fails(
    fake_llm_client: Mock, product: ProductInput
) -> None:
    fake_llm_client.chat.completions.create.return_value = make_completion("не JSON")

    with pytest.raises(LLMResponseError):
        await _generator(fake_llm_client).generate(product)

    assert fake_llm_client.chat.completions.create.await_count == 2


async def test_json_object_mode_puts_schema_into_prompt(
    fake_llm_client: Mock, product: ProductInput, valid_card: ProductCard
) -> None:
    fake_llm_client.chat.completions.create.return_value = make_completion(
        valid_card.model_dump_json()
    )

    await _generator(fake_llm_client, llm_response_format="json_object").generate(product)

    kwargs = fake_llm_client.chat.completions.create.await_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "seo_description" in kwargs["messages"][0]["content"]


async def test_insufficient_data_is_rejected(fake_llm_client: Mock) -> None:
    with pytest.raises(InsufficientProductDataError) as exc_info:
        await _generator(fake_llm_client).generate(ProductInput(name="Манометр"))

    assert exc_info.value.missing_fields == ["производитель", "характеристики", "описание"]
    fake_llm_client.chat.completions.create.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (openai.APITimeoutError(request=_REQUEST), LLMTimeoutError),
        (openai.APIConnectionError(request=_REQUEST), LLMUnavailableError),
        (
            openai.AuthenticationError(
                "bad key", response=httpx.Response(401, request=_REQUEST), body=None
            ),
            LLMUnavailableError,
        ),
    ],
)
async def test_api_errors_are_wrapped(
    fake_llm_client: Mock, product: ProductInput, error: Exception, expected: type[Exception]
) -> None:
    fake_llm_client.chat.completions.create.side_effect = error

    with pytest.raises(expected):
        await _generator(fake_llm_client).generate(product)


@pytest.mark.parametrize(
    ("content", "finish_reason"),
    [(None, "stop"), ('{"seo_title": "Мано', "length")],
)
async def test_empty_or_truncated_response_fails(
    fake_llm_client: Mock, product: ProductInput, content: str | None, finish_reason: str
) -> None:
    fake_llm_client.chat.completions.create.return_value = make_completion(content, finish_reason)

    with pytest.raises(LLMResponseError):
        await _generator(fake_llm_client).generate(product)
