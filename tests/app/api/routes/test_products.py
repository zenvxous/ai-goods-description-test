from unittest.mock import Mock

import httpx2 as httpx
import openai
from fastapi.testclient import TestClient

from app.schemas.products import PRODUCT_EXAMPLE, ProductCard
from tests.helpers.llm import make_completion

URL = "/api/v1/products/card"


def test_returns_json_card(
    client: TestClient, fake_llm_client: Mock, valid_card: ProductCard
) -> None:
    fake_llm_client.chat.completions.create.return_value = make_completion(
        valid_card.model_dump_json()
    )

    response = client.post(URL, json=PRODUCT_EXAMPLE)

    assert response.status_code == 200
    body = response.json()
    assert body["card"]["seo_title"] == valid_card.seo_title
    assert body["warnings"] == []


def test_returns_markdown_card(
    client: TestClient, fake_llm_client: Mock, valid_card: ProductCard
) -> None:
    fake_llm_client.chat.completions.create.return_value = make_completion(
        valid_card.model_dump_json()
    )

    response = client.post(URL, params={"format": "markdown"}, json=PRODUCT_EXAMPLE)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text.startswith(f"# {valid_card.seo_title}")


def test_malformed_json_returns_422(client: TestClient) -> None:
    response = client.post(
        URL, content=b'{"name": "Manometer",', headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


def test_insufficient_data_returns_422(client: TestClient, fake_llm_client: Mock) -> None:
    response = client.post(URL, json={"name": "Манометр"})

    assert response.status_code == 422
    assert response.json()["missing_fields"] == ["производитель", "характеристики", "описание"]
    fake_llm_client.chat.completions.create.assert_not_awaited()


def test_llm_unavailable_returns_502(client: TestClient, fake_llm_client: Mock) -> None:
    request = httpx.Request("POST", "https://llm.test")
    fake_llm_client.chat.completions.create.side_effect = openai.APIConnectionError(request=request)

    response = client.post(URL, json=PRODUCT_EXAMPLE)

    assert response.status_code == 502
    assert response.json()["detail"] == "Не удалось подключиться к LLM"


def test_llm_timeout_returns_504(client: TestClient, fake_llm_client: Mock) -> None:
    request = httpx.Request("POST", "https://llm.test")
    fake_llm_client.chat.completions.create.side_effect = openai.APITimeoutError(request=request)

    response = client.post(URL, json=PRODUCT_EXAMPLE)

    assert response.status_code == 504
