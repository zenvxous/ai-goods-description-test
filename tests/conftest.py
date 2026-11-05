from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.core.constants import NO_DATA
from app.core.dependencies import get_llm_client, settings
from app.main import app
from app.schemas.products import (
    PRODUCT_EXAMPLE,
    CommercialBlock,
    ProductCard,
    ProductInput,
    SpecItem,
)


@pytest.fixture
def fake_llm_client() -> Mock:
    client = Mock()
    client.models.list = AsyncMock(return_value=Mock(data=[Mock(id=settings.llm_model)]))
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def client(fake_llm_client: Mock) -> Iterator[TestClient]:
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def product() -> ProductInput:
    return ProductInput.model_validate(PRODUCT_EXAMPLE)


@pytest.fixture
def valid_card() -> ProductCard:
    description = (
        "Манометр показывающий DM 02 производства Манотомь предназначен для измерения "
        "избыточного давления. Диапазон измерений 0–1,6 МПа, класс точности 1,5, "
        "присоединение G1/2, диаметр корпуса 100 мм. "
    )
    description = (description * 6)[:1000]
    return ProductCard(
        seo_title="Манометр показывающий DM 02 Манотомь 0–1,6 МПа",
        seo_description=description,
        key_specs=[
            SpecItem(name="Диапазон измерений", value="0–1,6 МПа"),
            SpecItem(name="Класс точности", value="1,5"),
            SpecItem(name="Присоединение", value="G1/2"),
            SpecItem(name="Диаметр корпуса", value="100 мм"),
            SpecItem(name="Рабочая температура", value=NO_DATA),
        ],
        search_queries=[
            "манометр DM 02",
            "манометр 0-1.6 МПа",
            "манометр Манотомь купить",
        ],
        commercial=CommercialBlock(
            audience=["Службы КИПиА промышленных предприятий"],
            tasks=["Контроль избыточного давления"],
        ),
        missing_data=["рабочая температура"],
    )
