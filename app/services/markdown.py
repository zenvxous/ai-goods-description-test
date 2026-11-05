"""Render a product card as Markdown that a content manager can copy as is."""

from app.schemas.products import ProductCardResponse


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- —"


def render_markdown(response: ProductCardResponse) -> str:
    card = response.card
    specs = "\n".join(
        f"| {spec.name.replace('|', '/')} | {spec.value.replace('|', '/')} |"
        for spec in card.key_specs
    )
    sections = [
        f"# {card.seo_title}",
        f"## SEO-описание\n\n{card.seo_description}",
        f"## Характеристики\n\n| Характеристика | Значение |\n|---|---|\n{specs}",
        f"## Поисковые запросы\n\n{_bullets(card.search_queries)}",
        "## Для менеджера\n\n"
        f"**Кому подходит:**\n\n{_bullets(card.commercial.audience)}\n\n"
        f"**Какие задачи решает:**\n\n{_bullets(card.commercial.tasks)}",
        f"## Требует уточнения\n\n{_bullets(card.missing_data)}",
    ]
    if response.warnings:
        sections.append("## Замечания автоматической проверки\n\n" + _bullets(response.warnings))
    return "\n\n".join(sections) + "\n"
