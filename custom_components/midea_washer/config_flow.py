"""Config flow: find the washer by IP, then token/key manually or once from the cloud."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from midealocal.cloud import get_midea_cloud
from midealocal.const import ProtocolVersion
from midealocal.devices.db import MideaDBDevice
from midealocal.discover import discover

from .const import (
    CONF_DEVICE_ID,
    CONF_KEY,
    CONF_MODEL,
    CONF_PROTOCOL,
    CONF_SERIAL,
    CONF_TOKEN,
    DEVICE_TYPE_DB,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
CLOUD_NAME = "SmartHome"


def _discover(host: str) -> dict[str, Any] | None:
    found = discover(ip_address=host)  # type: ignore[arg-type]
    return next(iter(found.values()), None)


def _can_connect(info: dict[str, Any], token: str, key: str) -> bool:
    device = MideaDBDevice(
        name="probe",
        device_id=info["device_id"],
        ip_address=info["ip_address"],
        port=info["port"],
        token=token,
        key=key,
        device_protocol=ProtocolVersion(info["protocol"]),
        model=info["model"],
        subtype=0,
        customize="",
    )
    try:
        return device.connect()
    finally:
        device.close_socket()


class MideaWasherConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._info: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            info = await self.hass.async_add_executor_job(_discover, user_input[CONF_HOST])
            if info is None:
                errors["base"] = "not_found"
            elif info["type"] != DEVICE_TYPE_DB:
                return self.async_abort(reason="not_a_washer")
            else:
                await self.async_set_unique_id(str(info["device_id"]))
                self._abort_if_unique_id_configured(updates={CONF_HOST: info["ip_address"]})
                self._info = info
                if info["protocol"] != ProtocolVersion.V3:
                    return await self._async_finish("", "")
                return await self.async_step_auth()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_auth(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="auth", menu_options=["cloud", "manual"])

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token, key = user_input[CONF_TOKEN].strip().lower(), user_input[CONF_KEY].strip().lower()
            if await self.hass.async_add_executor_job(_can_connect, self._info, token, key):
                return await self._async_finish(token, key)
            errors["base"] = "invalid_auth"
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str, vol.Required(CONF_KEY): str}),
            errors=errors,
        )

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Fetch token/key once; the credentials are not stored."""
        errors: dict[str, str] = {}
        if user_input is not None:
            cloud = get_midea_cloud(
                CLOUD_NAME,
                async_get_clientsession(self.hass),
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                if not await cloud.login():
                    errors["base"] = "cloud_login"
                else:
                    keys = await cloud.get_cloud_keys(self._info["device_id"])
                    for pair in keys.values():
                        if await self.hass.async_add_executor_job(
                            _can_connect, self._info, pair["token"], pair["key"]
                        ):
                            return await self._async_finish(pair["token"], pair["key"])
                    errors["base"] = "invalid_auth"
            except Exception:  # cloud library raises assorted errors
                _LOGGER.exception("Cloud key retrieval failed")
                errors["base"] = "cloud_error"
        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def _async_finish(self, token: str, key: str) -> ConfigFlowResult:
        info = self._info
        return self.async_create_entry(
            title="Waschmaschine",
            data={
                CONF_DEVICE_ID: info["device_id"],
                CONF_HOST: info["ip_address"],
                CONF_PORT: info["port"],
                CONF_PROTOCOL: int(info["protocol"]),
                CONF_MODEL: info["model"],
                CONF_SERIAL: info.get("sn"),
                CONF_TOKEN: token,
                CONF_KEY: key,
            },
        )
