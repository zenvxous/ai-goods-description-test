from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.core.dependencies import CardGeneratorDep
from app.schemas.products import ProductCardResponse, ProductInput
from app.services.markdown import render_markdown

router = APIRouter(prefix="/products", tags=["products"])

_ERROR_RESPONSES: dict[int | str, dict[str, str]] = {
    422: {"description": "Некорректный JSON или недостаточно данных о товаре"},
    502: {"description": "Ошибка LLM-провайдера или некорректный ответ модели"},
    504: {"description": "LLM не ответила вовремя"},
}


@router.post(
    "/card",
    response_model=ProductCardResponse,
    responses={
        **_ERROR_RESPONSES,
        200: {"content": {"text/markdown": {}}},
    },
    summary="Сгенерировать черновик карточки товара",
)
async def generate_card(
    product: ProductInput,
    generator: CardGeneratorDep,
    output_format: Literal["json", "markdown"] = Query(
        default="json", alias="format", description="Формат ответа"
    ),
) -> ProductCardResponse | PlainTextResponse:
    result = await generator.generate(product)
    if output_format == "markdown":
        return PlainTextResponse(render_markdown(result), media_type="text/markdown")
    return result
