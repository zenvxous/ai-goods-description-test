"""Generate product cards for every JSON file in examples/input.

Usage: uv run python -m scripts.generate_examples [input_dir] [output_dir]
Results are written as <name>.json and <name>.md into the output directory.
"""

import asyncio
import json
import sys
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.core.dependencies import settings
from app.exceptions.llm import LLMError
from app.exceptions.products import InsufficientProductDataError
from app.logging_config import configure_logging
from app.schemas.products import ProductCardResponse, ProductInput
from app.services.generation import ProductCardGenerator
from app.services.markdown import render_markdown

ROOT = Path(__file__).resolve().parent.parent

type Result = ProductCardResponse | Exception


async def generate_all(inputs: dict[str, str]) -> dict[str, Result]:
    client = AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value() or "not-set",
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )
    generator = ProductCardGenerator(client, settings)
    results: dict[str, Result] = {}
    try:
        for name, raw in inputs.items():
            try:
                product = ProductInput.model_validate_json(raw)
                results[name] = await generator.generate(product)
            except (ValidationError, InsufficientProductDataError, LLMError) as e:
                results[name] = e
    finally:
        await client.close()
    return results


def main(input_dir: Path, output_dir: Path) -> int:
    configure_logging()
    inputs = {
        path.stem: path.read_text(encoding="utf-8") for path in sorted(input_dir.glob("*.json"))
    }
    results = asyncio.run(generate_all(inputs))

    output_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, result in results.items():
        if isinstance(result, Exception):
            failed += 1
            print(f"✗ {name}: {result}", file=sys.stderr)
            continue
        payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
        (output_dir / f"{name}.json").write_text(payload + "\n", encoding="utf-8")
        (output_dir / f"{name}.md").write_text(render_markdown(result), encoding="utf-8")
        print(f"✓ {name}: warnings={len(result.warnings)}")

    return 1 if failed else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    input_dir = Path(args[0]) if args else ROOT / "examples" / "input"
    output_dir = Path(args[1]) if len(args) > 1 else ROOT / "examples" / "output"
    sys.exit(main(input_dir, output_dir))
