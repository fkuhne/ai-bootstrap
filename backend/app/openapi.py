"""Write the API's OpenAPI schema, which the web UI's TypeScript types are generated from
(docs/foundations.md#the-web-ui). Run both after changing an endpoint, or a model the API takes
or returns:

    docker compose run --rm backend-checks python -m app.openapi
    docker compose run --rm frontend-checks npm run api:types

A unit test fails while the committed schema differs from the app's.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from app.core.config import AppSettings
from app.main import create_app
from app.modules import MODULES

# Where the web UI keeps the schema, next to the types generated from it. The checks
# container mounts that folder at the same place relative to the backend's code.
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"


def schema() -> dict[str, Any]:
    """The app's OpenAPI schema, from its routes and models alone: the settings' defaults and
    every module, whatever the environment says, so the file is the same on every machine."""
    return create_app(AppSettings.model_construct(), modules=MODULES).openapi()


def render(document: dict[str, Any]) -> str:
    """The schema as the committed file holds it: indented, with one trailing newline."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write the API's OpenAPI schema.")
    parser.add_argument("output", nargs="?", type=Path, default=SCHEMA_FILE)
    args = parser.parse_args(argv)
    args.output.write_text(render(schema()), encoding="utf-8")


if __name__ == "__main__":
    main()
