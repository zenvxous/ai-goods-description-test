from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_llm_client
from app.main import app


@pytest.fixture
def fake_llm_client() -> Mock:
    client = Mock()
    client.models.retrieve = AsyncMock()
    return client


@pytest.fixture
def client(fake_llm_client: Mock) -> Iterator[TestClient]:
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
