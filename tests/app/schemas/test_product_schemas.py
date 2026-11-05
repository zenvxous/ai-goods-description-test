import pytest
from pydantic import ValidationError

from app.schemas.products import PRODUCT_EXAMPLE, ProductInput


def test_example_is_valid() -> None:
    product = ProductInput.model_validate(PRODUCT_EXAMPLE)

    assert product.missing_fields() == []


def test_only_name_is_required() -> None:
    product = ProductInput.model_validate({"name": "Манометр"})

    assert product.missing_fields() == ["производитель", "характеристики", "описание"]


@pytest.mark.parametrize("name", ["", "   ", None])
def test_empty_name_is_rejected(name: str | None) -> None:
    with pytest.raises(ValidationError):
        ProductInput.model_validate({"name": name})


def test_blank_strings_become_none() -> None:
    product = ProductInput.model_validate(
        {"name": " Манометр ", "manufacturer": "  ", "description": ""}
    )

    assert product.name == "Манометр"
    assert product.manufacturer is None
    assert product.description is None


def test_specs_are_normalized() -> None:
    product = ProductInput.model_validate(
        {
            "name": "Датчик",
            "specs": {
                " класс точности ": 0.5,
                "выход": " 4–20 мА ",
                "индикатор": True,
                "корпус": "",
                "питание": None,
            },
        }
    )

    assert product.specs == {
        "класс точности": "0.5",
        "выход": "4–20 мА",
        "индикатор": "да",
        "корпус": None,
        "питание": None,
    }
    assert product.missing_fields() == [
        "производитель",
        "значение характеристики «корпус»",
        "значение характеристики «питание»",
        "описание",
    ]


@pytest.mark.parametrize(
    "specs",
    [
        {"": "1"},
        {"диапазон": ["0", "1"]},
        {"диапазон": {"min": 0}},
        ["диапазон", "0–1"],
        "диапазон 0–1",
    ],
)
def test_invalid_specs_are_rejected(specs: object) -> None:
    with pytest.raises(ValidationError):
        ProductInput.model_validate({"name": "Датчик", "specs": specs})


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductInput.model_validate({"name": "Датчик", "price": 100})
