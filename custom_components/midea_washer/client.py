"""LAN client: midea-local transport + our 0xDB codec + the app's command sequences."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from midealocal.const import DeviceType, ProtocolVersion
from midealocal.devices.db import MideaDBDevice
from midealocal.message import MessageRequest, MessageType

from .const import COMMAND_TIMEOUT, DEVICE_TYPE_DB, DOMAIN, RECONNECT_INTERVAL
from .models import WasherModel, load_model
from .protocol import Control, RunStatus, WasherStatus, build_control, query_body

_LOGGER = logging.getLogger(__name__)

HEADER_LEN = 10


class _RawRequest(MessageRequest):
    """A request whose body is already encoded (body[0] is the body type)."""

    def __init__(self, protocol_version: int, message_type: MessageType, body: bytes) -> None:
        super().__init__(
            device_type=DeviceType.DB,
            protocol_version=protocol_version,
            message_type=message_type,
            body_type=body[0],  # type: ignore[arg-type]
        )
        self._raw = body[1:]

    @property
    def _body(self) -> bytearray:
        return bytearray(self._raw)


class _Transport(MideaDBDevice):
    """midea-local's socket thread, with frames decoded by our codec."""

    def process_message(self, msg: bytes) -> dict[str, Any]:
        if len(msg) <= HEADER_LEN or msg[2] != DEVICE_TYPE_DB:
            return {}
        status = WasherStatus.parse(msg[HEADER_LEN:-1])
        if status is None:
            _LOGGER.debug("Ignoring frame %s", msg.hex())
            return {}
        return {"status": status}

    def _connect_loop(self) -> None:
        """Retry at a fixed short interval: the washer leaves Wi-Fi whenever it is off,
        and midea-local's backoff (up to 10 min) would miss it being switched back on."""
        while self._socket is None and self._is_run:
            if self._should_run() and not self.connect(check_protocol=True):
                for _ in range(RECONNECT_INTERVAL):
                    if not self._should_run():
                        break
                    time.sleep(1)

    def send_body(self, body: bytes) -> None:
        self._send(MessageType.set, body)

    def send_query(self) -> None:
        self._send(MessageType.query, query_body())

    def _send(self, message_type: MessageType, body: bytes) -> None:
        try:
            self.build_send(_RawRequest(self._message_protocol_version, message_type, body))
        except Exception as err:  # midea-local raises bare socket errors
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_connected"
            ) from err


class WasherClient:
    """Owns the connection and the latest state; entities subscribe to it."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        device_id: int,
        host: str,
        port: int,
        token: str,
        key: str,
        protocol: int,
        model: str,
        serial: str | None,
    ) -> None:
        self.hass = hass
        self.device_id = device_id
        self.serial = serial
        self.sn8 = model
        self.name = "Midea washer"
        self.delay_minutes = 0
        self.status: WasherStatus | None = None
        self.model: WasherModel | None = None
        self.available = False
        self._listeners: list[Callable[[], None]] = []
        self._changed = asyncio.Event()
        self._lock = asyncio.Lock()
        self._transport = _Transport(
            name="Midea washer",
            device_id=device_id,
            ip_address=host,
            port=port,
            token=token,
            key=key,
            device_protocol=ProtocolVersion(protocol),
            model=model,
            subtype=0,
            customize="",
        )
        self._transport.register_update(self._on_update_threadsafe)

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        self._transport.open()

    def stop(self) -> None:
        self._transport.unregister_update(self._on_update_threadsafe)
        self._transport.close()

    def _on_update_threadsafe(self, update: dict[str, Any]) -> None:
        self.hass.loop.call_soon_threadsafe(self._on_update, update)

    @callback
    def _on_update(self, update: dict[str, Any]) -> None:
        if "available" in update:
            self.available = bool(update["available"])
        if (status := update.get("status")) is not None:
            self.available = True
            self.status = status
            if self.model is None and status.project_no:
                self.hass.async_create_task(self._async_load_model(status.project_no))
        self._changed.set()
        for listener in list(self._listeners):
            listener()

    async def _async_load_model(self, subtype: int) -> None:
        model = await self.hass.async_add_executor_job(load_model, subtype)
        if model is None:
            _LOGGER.warning(
                "No program table for washer subtype %s; programs unavailable", subtype
            )
            return
        if self.model is None:
            self.model = model
            for listener in list(self._listeners):
                listener()

    @callback
    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    # --- low level -------------------------------------------------------

    def _require_status(self) -> WasherStatus:
        if not self.available or self.status is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_connected"
            )
        return self.status

    def _require_remote(self, status: WasherStatus) -> None:
        if self.model and self.model.requires_remote_control and not status.remote_control:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="remote_control_off"
            )

    async def _send(self, ctl: Control) -> None:
        status = self._require_status()
        body = build_control(status, ctl)
        _LOGGER.debug("Sending %s -> %s", ctl, body.hex())
        self._changed.clear()
        await self.hass.async_add_executor_job(self._transport.send_body, body)

    async def _wait_for(self, predicate: Callable[[WasherStatus], bool]) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + COMMAND_TIMEOUT
        while not (self.status is not None and predicate(self.status)):
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_confirmation"
                )
            self._changed.clear()
            try:
                await asyncio.wait_for(self._changed.wait(), min(remaining, 3))
            except TimeoutError:
                await self.hass.async_add_executor_job(self._transport.send_query)

    # --- commands --------------------------------------------------------

    async def async_set_power(self, on: bool) -> None:
        async with self._lock:
            self._require_remote(self._require_status())
            await self._send(Control(power=on))
            await self._wait_for(lambda s: s.power == on)

    async def async_set_lock(self, on: bool) -> None:
        async with self._lock:
            self._require_remote(self._require_status())
            await self._send(Control(lock=on))
            await self._wait_for(lambda s: s.option("lock") == on)

    async def async_select_program(self, value: int) -> None:
        async with self._lock:
            await self._select_program(value)

    async def _ensure_on(self) -> None:
        status = self._require_status()
        self._require_remote(status)
        if not status.power:
            await self._send(Control(power=True))
            await self._wait_for(lambda s: s.power)

    async def _select_program(self, value: int) -> None:
        await self._ensure_on()
        status = self._require_status()
        if status.running or status.run_status is RunStatus.PAUSED:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="busy"
            )
        if status.program != value:
            await self._send(Control(program=value, merge=False))
            await self._wait_for(lambda s: s.program == value)

    def _check_option_change(self, status: WasherStatus, key: str) -> None:
        if self.model is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_model"
            )
        program = self.model.by_value(status.program)
        if program is None or key not in program.options:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="option_not_supported",
                translation_placeholders={"option": key},
            )
        busy = status.running or status.run_status is RunStatus.PAUSED
        if busy and key in self.model.locked_while_running:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="locked_while_running",
                translation_placeholders={"option": key},
            )

    async def async_set_options(self, **options: int | bool) -> None:
        async with self._lock:
            await self._set_options(options)

    async def _set_options(self, options: dict[str, int | bool]) -> None:
        status = self._require_status()
        self._require_remote(status)
        changes: dict[str, int | bool] = {}
        for key, value in options.items():
            self._check_option_change(status, key)
            current = status.option(key) if isinstance(value, bool) else getattr(status, key)
            if current != value:
                changes[key] = value
        if not changes:
            return
        await self._send(Control(**changes))

        def applied(s: WasherStatus) -> bool:
            return all(
                (s.option(k) if isinstance(v, bool) else getattr(s, k)) == v
                for k, v in changes.items()
            )

        await self._wait_for(applied)

    async def async_start(self, delay_minutes: int = 0) -> None:
        async with self._lock:
            await self._start(delay_minutes)

    async def _start(self, delay_minutes: int) -> None:
        status = self._require_status()
        self._require_remote(status)
        if status.running:
            return
        if not status.power:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="powered_off"
            )
        if delay_minutes and status.run_status is not RunStatus.PAUSED:
            await self._send(Control(delay_minutes=delay_minutes))
            await self._wait_for(lambda s: s.delay_minutes == delay_minutes)
        await self._send(Control(start=True, merge=False))
        await self._wait_for(lambda s: s.running)

    async def async_pause(self) -> None:
        async with self._lock:
            status = self._require_status()
            self._require_remote(status)
            if status.run_status is RunStatus.PAUSED:
                return
            await self._send(Control(start=False, merge=False))
            await self._wait_for(lambda s: not s.running)

    async def async_run_program(
        self, program: int, options: dict[str, int | bool], delay_minutes: int = 0
    ) -> None:
        """The app's 'run through' flow: power on, program, options, start."""
        async with self._lock:
            await self._select_program(program)
            if options:
                await self._set_options(options)
            await self._start(delay_minutes)
