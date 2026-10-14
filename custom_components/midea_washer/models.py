"""Per-model program tables, generated from the app plugin's model JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
# Option keys as they appear in entity states (temperature 1 -> "cold").
TEMPERATURE_KEYS = {1: "cold", 2: "20", 3: "30", 4: "40", 5: "60", 6: "95", 7: "70", 8: "90", 9: "50"}
SPIN_KEYS = {0: "0", 1: "400", 2: "600", 3: "800", 4: "1000", 5: "1200", 6: "1400", 7: "1600", 8: "1300"}
WATER_KEYS = {1: "1", 2: "2", 3: "3", 4: "4", 5: "auto"}
VALUE_KEYS = {"temperature": TEMPERATURE_KEYS, "spin_speed": SPIN_KEYS, "water_level": WATER_KEYS}
SELECT_OPTIONS = tuple(VALUE_KEYS)
SWITCH_OPTIONS = ("pre_wash", "extra_rinse", "turbo", "silent")


@dataclass(frozen=True, slots=True)
class OptionSpec:
    values: tuple[int, ...]
    default: int


@dataclass(frozen=True, slots=True)
class Program:
    value: int
    slug: str
    default_minutes: int
    options: dict[str, OptionSpec]


@dataclass(frozen=True, slots=True)
class WasherModel:
    subtype: int
    model_name: str
    programs: tuple[Program, ...]
    locked_while_running: frozenset[str]
    requires_remote_control: bool

    def by_value(self, value: int) -> Program | None:
        return next((p for p in self.programs if p.value == value), None)

    def by_slug(self, slug: str) -> Program | None:
        return next((p for p in self.programs if p.slug == slug), None)


def available_subtypes() -> list[int]:
    return sorted(int(p.stem) for p in MODELS_DIR.glob("*.json"))


@cache
def load_model(subtype: int) -> WasherModel | None:
    """Blocking file read; call from an executor."""
    path = MODELS_DIR / f"{subtype}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return WasherModel(
        subtype=raw["subtype"],
        model_name=raw["model_name"],
        programs=tuple(
            Program(
                value=p["value"],
                slug=p["slug"],
                default_minutes=p["default_minutes"],
                options={
                    k: OptionSpec(tuple(o["values"]), o["default"])
                    for k, o in p["options"].items()
                },
            )
            for p in raw["programs"]
        ),
        locked_while_running=frozenset(raw["locked_while_running"]),
        requires_remote_control=raw["requires_remote_control"],
    )
