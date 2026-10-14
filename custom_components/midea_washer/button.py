"""Start / pause buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    client = entry.runtime_data
    async_add_entities([StartButton(client), PauseButton(client)])


class StartButton(WasherEntity, ButtonEntity):
    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "start")

    async def async_press(self) -> None:
        await self.client.async_start(self.client.delay_minutes)


class PauseButton(WasherEntity, ButtonEntity):
    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "pause")

    async def async_press(self) -> None:
        await self.client.async_pause()
