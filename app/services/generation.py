"""Product card generation via an OpenAI-compatible LLM."""

import json
import re
from dataclasses import dataclass, field
from typing import Any

import openai
import structlog
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.core.config import Settings
from app.exceptions.llm import LLMResponseError, LLMTimeoutError, LLMUnavailableError
from app.exceptions.products import InsufficientProductDataError
from app.prompts.product_card import SYSTEM_PROMPT, build_repair_prompt, build_user_prompt
from app.schemas.products import ProductCard, ProductCardResponse, ProductInput
from app.services.card_checks import check_card, normalize

log = structlog.get_logger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a pydantic JSON schema compatible with OpenAI strict structured output."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        schema["required"] = list(schema.get("properties", {}))
    for value in schema.values():
        if isinstance(value, dict):
            _strict_schema(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _strict_schema(item)
    return schema


CARD_JSON_SCHEMA = _strict_schema(ProductCard.model_json_schema())


@dataclass
class _Attempt:
    card: ProductCard | None = None
    issues: list[str] = field(default_factory=list)


def parse_card(content: str) -> ProductCard:
    text = content.strip()
    if match := _CODE_FENCE_RE.match(text):
        text = match.group(1)
    return ProductCard.model_validate_json(text)


def merge_missing_fields(card: ProductCard, product: ProductInput) -> None:
    """Put fields missing in the input first, then the model's extra items, without dupes.

    The input gaps are known for sure, so they are not left to the model.
    """
    merged: list[str] = []
    seen: list[str] = []
    items = [f"Не указано: {missing}" for missing in product.missing_fields()]
    for item in [*items, *card.missing_data]:
        key = normalize(item).strip(" .;")
        # "Класс точности" from the model duplicates "...характеристики «класс точности»"
        if key and not any(key in other or other in key for other in seen):
            seen.append(key)
            merged.append(item.strip())
    card.missing_data = merged


class ProductCardGenerator:
    def __init__(self, client: AsyncOpenAI, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def generate(self, product: ProductInput) -> ProductCardResponse:
        if not product.specs and product.description is None:
            raise InsufficientProductDataError(product.missing_fields())

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": build_user_prompt(product)},
        ]

        best = _Attempt()
        for attempt in range(self._settings.llm_repair_attempts + 1):
            content = await self._complete(messages)
            current = self._evaluate(content, product)
            log.info(
                "card_attempt_finished",
                product=product.name,
                attempt=attempt,
                parsed=current.card is not None,
                issues=current.issues,
            )

            if current.card is not None and (
                best.card is None or len(current.issues) <= len(best.issues)
            ):
                best = current
            if current.card is not None and not current.issues:
                break

            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": build_repair_prompt(current.issues)})

        if best.card is None:
            raise LLMResponseError("Модель вернула ответ, который не удалось разобрать")

        merge_missing_fields(best.card, product)
        return ProductCardResponse(card=best.card, warnings=best.issues)

    def _system_prompt(self) -> str:
        if self._settings.llm_response_format == "json_schema":
            return SYSTEM_PROMPT
        schema = json.dumps(CARD_JSON_SCHEMA, ensure_ascii=False)
        return (
            f"{SYSTEM_PROMPT}\nОтветь одним JSON-объектом строго по этой JSON-схеме, "
            f"без пояснений и markdown:\n{schema}"
        )

    def _evaluate(self, content: str, product: ProductInput) -> _Attempt:
        try:
            card = parse_card(content)
        except ValidationError as e:
            issues = [
                f"{'.'.join(map(str, err['loc'])) or 'ответ'}: {err['msg']}" for err in e.errors()
            ]
            return _Attempt(issues=["ответ не соответствует JSON-схеме", *issues[:10]])
        return _Attempt(card=card, issues=check_card(card, product))

    async def _complete(self, messages: list[ChatCompletionMessageParam]) -> str:
        response_format: Any
        if self._settings.llm_response_format == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "product_card",
                    "strict": True,
                    "schema": CARD_JSON_SCHEMA,
                },
            }
        else:
            response_format = {"type": "json_object"}

        try:
            response = await self._client.chat.completions.create(
                model=self._settings.llm_model,
                messages=messages,
                temperature=self._settings.llm_temperature,
                max_tokens=self._settings.llm_max_tokens,
                response_format=response_format,
                extra_body=self._settings.llm_extra_body or None,
            )
        except openai.APITimeoutError as e:
            log.error("llm_timeout", model=self._settings.llm_model)
            raise LLMTimeoutError("LLM не ответила вовремя") from e
        except openai.APIConnectionError as e:
            log.error("llm_connection_failed", detail=str(e))
            raise LLMUnavailableError("Не удалось подключиться к LLM") from e
        except openai.APIStatusError as e:
            log.error("llm_request_failed", status_code=e.status_code, detail=e.message)
            raise LLMUnavailableError(f"LLM вернула ошибку {e.status_code}: {e.message}") from e

        if usage := response.usage:
            details = usage.completion_tokens_details
            log.info(
                "llm_usage",
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                reasoning_tokens=details.reasoning_tokens if details else None,
            )

        if not response.choices:
            raise LLMResponseError("LLM вернула пустой ответ")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise LLMResponseError("Ответ LLM обрезан: увеличьте LLM_MAX_TOKENS")
        if choice.message.refusal:
            raise LLMResponseError(f"LLM отказалась отвечать: {choice.message.refusal}")
        if not choice.message.content:
            raise LLMResponseError("LLM вернула пустой ответ")
        return choice.message.content
