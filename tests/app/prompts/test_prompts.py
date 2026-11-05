from app.core.constants import NO_DATA
from app.prompts.product_card import SYSTEM_PROMPT, build_repair_prompt, build_user_prompt
from app.schemas.products import ProductInput


def test_system_prompt_mentions_no_data_marker() -> None:
    assert NO_DATA in SYSTEM_PROMPT


def test_user_prompt_contains_product_data(product: ProductInput) -> None:
    prompt = build_user_prompt(product)

    assert "Манометр показывающий DM 02" in prompt
    assert '"класс точности": "1,5"' in prompt
    assert "Не заполнено во входных данных: нет." in prompt


def test_user_prompt_lists_missing_fields() -> None:
    prompt = build_user_prompt(ProductInput(name="Манометр"))

    assert "Не заполнено во входных данных: производитель, характеристики, описание." in prompt


def test_repair_prompt_lists_issues() -> None:
    prompt = build_repair_prompt(["seo_title длиной 90 символов", "key_specs пустой"])

    assert "- seo_title длиной 90 символов\n- key_specs пустой" in prompt
