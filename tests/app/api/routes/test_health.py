from unittest.mock import Mock

from fastapi.testclient import TestClient


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "X-Request-ID" in response.headers


def test_readiness_ok_when_llm_available(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["llm"]["status"] == "ok"


def test_readiness_503_when_llm_unavailable(client: TestClient, fake_llm_client: Mock) -> None:
    fake_llm_client.models.list.side_effect = RuntimeError("llm down")

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["llm"]["status"] == "error"


def test_readiness_503_when_model_missing(client: TestClient, fake_llm_client: Mock) -> None:
    fake_llm_client.models.list.return_value = Mock(data=[Mock(id="other-model")])

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert "not found" in response.json()["detail"]["checks"]["llm"]["detail"]
