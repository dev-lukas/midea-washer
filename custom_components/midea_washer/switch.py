"""Power, child lock and per-program option switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WasherConfigEntry
from .client import WasherClient
from .entity import WasherEntity
from .models import SWITCH_OPTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasherConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = entry.runtime_data
    async_add_entities(
        [PowerSwitch(client), ChildLockSwitch(client)]
        + [OptionSwitch(client, key) for key in SWITCH_OPTIONS]
    )


class PowerSwitch(WasherEntity, SwitchEntity):
    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "power")

    @property
    def available(self) -> bool:
        # The washer drops off Wi-Fi when switched off, so unreachable means off.
        return True

    @property
    def is_on(self) -> bool:
        return super().available and self.status.power

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.client.async_set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.async_set_power(False)


class ChildLockSwitch(WasherEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "child_lock")

    @property
    def is_on(self) -> bool:
        return self.status.option("lock")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.client.async_set_lock(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.async_set_lock(False)


class OptionSwitch(WasherEntity, SwitchEntity):
    """Pre-wash / extra rinse / turbo / silent, when the program offers it."""

    def __init__(self, client: WasherClient, key: str) -> None:
        super().__init__(client, key)
        self._key = key

    @property
    def available(self) -> bool:
        program = self.program
        return super().available and program is not None and self._key in program.options

    @property
    def is_on(self) -> bool:
        return self.status.option(self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.client.async_set_options(**{self._key: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.async_set_options(**{self._key: False})
