"""Delayed start, applied when the start button is pressed."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WasherConfigEntry
from .client import WasherClient
from .entity import WasherEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasherConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([DelayStartNumber(entry.runtime_data)])


class DelayStartNumber(WasherEntity, RestoreNumber):
    """Local setting only; nothing is sent until start."""

    _attr_native_min_value = 0
    _attr_native_max_value = 24
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.BOX

    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "delay_start")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) and last.native_value is not None:
            self.client.delay_minutes = round(last.native_value * 60)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.client.delay_minutes / 60

    async def async_set_native_value(self, value: float) -> None:
        self.client.delay_minutes = round(value * 60)
        self.async_write_ha_state()
