"""Each module in `MODULES` has its places, and none is left of a module that's gone
(docs/modules/README.md). The checks container mounts the repository's files this reads."""

import re
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi import APIRouter
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import ModuleSettings
from app.core.modules import Module
from app.modules import MODULES

# The repository's root: the backend's parent here, `/` in the checks container, which mounts
# the files at the same places relative to the backend's code.
ROOT = Path(__file__).resolve().parents[3]


def variables(cls: type[BaseSettings]) -> list[str]:
    """The environment variables a settings class reads."""
    prefix = cls.model_config["env_prefix"]
    return [f"{prefix}{field}".upper() for field in cls.model_fields]


def missing_places(root: Path, module: Module) -> list[str]:
    """What the module lacks, each place named as the recipe names it."""
    name = module.name
    compose = (root / "compose.yaml").read_text()
    env = (root / ".env.example").read_text()
    missing = [
        place
        for place in (
            f"compose/modules/{name}.yaml",
            f"scripts/modules/{name}/",
            f".github/workflows/{name}.yml",
            f"docs/modules/{name}.md",
        )
        if not (root / place).exists()
    ]
    if f"  - compose/modules/{name}.yaml\n" not in compose:
        missing.append(f"compose.yaml: its line under include:, - compose/modules/{name}.yaml")
    if not re.search(rf"^# --- The {name} module ---$", env, re.M | re.I):
        missing.append(f".env.example: its section, # --- The {name} module ---")
    for cls in (module.settings, *module.more_settings):
        for variable in variables(cls):
            if not re.search(rf"^\s+{variable}:", compose, re.M):
                missing.append(f"compose.yaml: {variable} among the backend's settings")
            if not re.search(rf"^(# )?{variable}=", env, re.M):
                missing.append(f".env.example: a line for {variable}")
    return missing


def leftovers(root: Path, modules: Sequence[Module]) -> list[str]:
    """Places of modules that aren't in the list: what a removal left behind."""
    names = {module.name for module in modules}
    found = [
        f"compose/modules/{path.name}"
        for path in (root / "compose" / "modules").glob("*.yaml")
        if path.stem not in names
    ]
    found += [
        f"docs/modules/{path.name}"
        for path in (root / "docs" / "modules").glob("*.md")
        if path.stem not in names and path.name != "README.md"
    ]
    found += [
        f"scripts/modules/{path.name}/"
        for path in (root / "scripts" / "modules").iterdir()
        if path.is_dir() and path.name not in names and not path.name.startswith("_")
    ]
    sections = re.findall(
        r"^# --- The (\w+) module ---$", (root / ".env.example").read_text(), re.M
    )
    found += [
        f".env.example: # --- The {section} module ---"
        for section in sections
        if section.lower() not in names
    ]
    return sorted(found)


def test_the_repository_s_files_are_there() -> None:
    assert (ROOT / "compose.yaml").exists(), (
        "This test reads the repository's files: run it with docker compose run --rm "
        "backend-checks, which mounts them."
    )


@pytest.mark.parametrize("module", MODULES, ids=[module.name for module in MODULES])
def test_each_module_has_its_places(module: Module) -> None:
    assert missing_places(ROOT, module) == []


def test_no_place_is_left_of_a_module_that_s_gone() -> None:
    assert leftovers(ROOT, MODULES) == []


class EchoSettings(ModuleSettings):
    model_config = SettingsConfigDict(env_prefix="ECHO_")

    word: str = "hello"


ECHO = Module(name="echo", router=APIRouter(), settings=EchoSettings)


def repository(root: Path, *, env: str, compose: str) -> Path:
    """A repository with the echo module's places, and the given `.env.example` and
    `compose.yaml`."""
    for place in (
        "compose/modules/echo.yaml",
        ".github/workflows/echo.yml",
        "docs/modules/echo.md",
    ):
        (root / place).parent.mkdir(parents=True, exist_ok=True)
        (root / place).write_text("")
    (root / "scripts" / "modules" / "echo").mkdir(parents=True)
    (root / ".env.example").write_text(env)
    (root / "compose.yaml").write_text(compose)
    return root


COMPOSE = "include:\n  - compose/modules/echo.yaml\n  ECHO_ENABLED:\n  ECHO_WORD:\n"
ENV = "# --- The echo module ---\nECHO_ENABLED=1\n# ECHO_WORD=hello\n"


def test_a_complete_module_lacks_nothing(tmp_path: Path) -> None:
    root = repository(tmp_path, env=ENV, compose=COMPOSE)

    assert missing_places(root, ECHO) == []
    assert leftovers(root, [ECHO]) == []


def test_each_place_missing_is_named(tmp_path: Path) -> None:
    root = repository(tmp_path, env="ECHO_ENABLED=1\n", compose="  ECHO_ENABLED:\n")
    (root / "docs" / "modules" / "echo.md").unlink()

    assert missing_places(root, ECHO) == [
        "docs/modules/echo.md",
        "compose.yaml: its line under include:, - compose/modules/echo.yaml",
        ".env.example: its section, # --- The echo module ---",
        "compose.yaml: ECHO_WORD among the backend's settings",
        ".env.example: a line for ECHO_WORD",
    ]


def test_a_removed_module_s_places_are_named_as_left_behind(tmp_path: Path) -> None:
    root = repository(tmp_path, env=ENV, compose=COMPOSE)

    assert leftovers(root, []) == [
        ".env.example: # --- The echo module ---",
        "compose/modules/echo.yaml",
        "docs/modules/echo.md",
        "scripts/modules/echo/",
    ]
