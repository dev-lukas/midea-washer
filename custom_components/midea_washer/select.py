"""Program and per-program option selects, plus the run_program service."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WasherConfigEntry
from .client import WasherClient
from .const import DOMAIN
from .entity import WasherEntity
from .models import SELECT_OPTIONS, SWITCH_OPTIONS, VALUE_KEYS

SERVICE_RUN_PROGRAM = "run_program"
ALL_PROGRAM_SLUGS = (
    "cotton", "mix", "synthetic", "jeans", "cold_20", "allergy_care", "steam_care",
    "spin_only", "rinse_spin", "wool", "bulky", "eco_40_60", "rapid_45", "quick_15",
    "drum_clean",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasherConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = entry.runtime_data
    async_add_entities(
        [ProgramSelect(client)] + [OptionSelect(client, key) for key in SELECT_OPTIONS]
    )
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RUN_PROGRAM,
        {
            vol.Required("program"): vol.In(ALL_PROGRAM_SLUGS),
            vol.Optional("temperature"): vol.In(list(VALUE_KEYS["temperature"].values())),
            vol.Optional("spin_speed"): vol.In(list(VALUE_KEYS["spin_speed"].values())),
            vol.Optional("water_level"): vol.In(list(VALUE_KEYS["water_level"].values())),
            **{vol.Optional(key): cv.boolean for key in SWITCH_OPTIONS},
            vol.Optional("delay", default=0): vol.All(vol.Coerce(int), vol.Range(0, 1440)),
        },
        "async_run_program",
    )


class _RunProgram(WasherEntity):
    """run_program service, callable on any of the washer's selects."""

    async def async_run_program(self, program: str, delay: int = 0, **options: object) -> None:
        model = self.client.model
        target = model.by_slug(program) if model else None
        if target is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="option_not_supported",
                translation_placeholders={"option": program},
            )
        raw: dict[str, int | bool] = {}
        for key, value in options.items():
            if key not in target.options:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="option_not_supported",
                    translation_placeholders={"option": key},
                )
            if key in VALUE_KEYS:
                code = next(c for c, k in VALUE_KEYS[key].items() if k == value)
                if code not in target.options[key].values:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="value_not_supported",
                        translation_placeholders={"option": key, "value": str(value)},
                    )
                raw[key] = code
            else:
                raw[key] = bool(value)
        await self.client.async_run_program(target.value, raw, delay)


class ProgramSelect(_RunProgram, SelectEntity):
    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "program")

    @property
    def available(self) -> bool:
        return super().available and self.client.model is not None

    @property
    def options(self) -> list[str]:
        if self.client.model is None:
            return []
        return [p.slug for p in self.client.model.programs]

    @property
    def current_option(self) -> str | None:
        program = self.program
        return program.slug if program else None

    async def async_select_option(self, option: str) -> None:
        assert self.client.model is not None
        program = self.client.model.by_slug(option)
        assert program is not None
        await self.client.async_select_program(program.value)


class OptionSelect(_RunProgram, SelectEntity):
    """Temperature / spin speed / water level; choices follow the current program."""

    def __init__(self, client: WasherClient, key: str) -> None:
        super().__init__(client, key)
        self._key = key
        self._keys = VALUE_KEYS[key]

    @property
    def available(self) -> bool:
        program = self.program
        return super().available and program is not None and self._key in program.options

    @property
    def options(self) -> list[str]:
        program = self.program
        if program is None or self._key not in program.options:
            return []
        return [self._keys[v] for v in program.options[self._key].values]

    @property
    def current_option(self) -> str | None:
        return self._keys.get(getattr(self.status, self._key))

    async def async_select_option(self, option: str) -> None:
        code = next(c for c, k in self._keys.items() if k == option)
        await self.client.async_set_options(**{self._key: code})
