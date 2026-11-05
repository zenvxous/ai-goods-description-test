from app.schemas.products import ProductCard, ProductCardResponse, SpecItem
from app.services.markdown import render_markdown


def test_render_markdown(valid_card: ProductCard) -> None:
    valid_card.key_specs.append(SpecItem(name="Выход", value="4|20"))

    text = render_markdown(ProductCardResponse(card=valid_card, warnings=["проверьте"]))

    assert text.startswith(f"# {valid_card.seo_title}\n")
    assert "| Диапазон измерений | 0–1,6 МПа |" in text
    assert "| Выход | 4/20 |" in text
    assert "- манометр DM 02" in text
    assert "## Замечания автоматической проверки\n\n- проверьте" in text


def test_render_markdown_without_warnings(valid_card: ProductCard) -> None:
    text = render_markdown(ProductCardResponse(card=valid_card))

    assert "Замечания" not in text
