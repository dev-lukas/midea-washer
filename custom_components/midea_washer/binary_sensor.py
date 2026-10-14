"""Remote control enabled on the washer panel."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
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
    async_add_entities([RemoteControlSensor(entry.runtime_data)])


class RemoteControlSensor(WasherEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "remote_control")

    @property
    def is_on(self) -> bool:
        return self.status.remote_control
