"""Local control for Midea 0xDB front-load washers, including programs."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .client import WasherClient
from .const import CONF_DEVICE_ID, CONF_KEY, CONF_MODEL, CONF_PROTOCOL, CONF_SERIAL, CONF_TOKEN

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type WasherConfigEntry = ConfigEntry[WasherClient]


async def async_setup_entry(hass: HomeAssistant, entry: WasherConfigEntry) -> bool:
    data = entry.data
    client = WasherClient(
        hass,
        device_id=data[CONF_DEVICE_ID],
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        token=data[CONF_TOKEN],
        key=data[CONF_KEY],
        protocol=data[CONF_PROTOCOL],
        model=data[CONF_MODEL],
        serial=data.get(CONF_SERIAL),
    )
    client.name = entry.title
    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    client.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WasherConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await hass.async_add_executor_job(entry.runtime_data.stop)
    return unloaded
