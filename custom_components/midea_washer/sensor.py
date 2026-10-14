"""Status, phase, remaining time, finish time and error sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import WasherConfigEntry
from .client import WasherClient
from .entity import WasherEntity
from .protocol import PHASES, RunStatus, WasherStatus

STATES = {
    RunStatus.IDLE: "idle",
    RunStatus.STANDBY: "standby",
    RunStatus.RUNNING: "running",
    RunStatus.PAUSED: "paused",
    RunStatus.FINISHED: "finished",
    RunStatus.FAULT: "fault",
    RunStatus.DELAYED: "delayed",
}


def _state(s: WasherStatus) -> str | None:
    if not s.power:
        return "off"
    return STATES.get(s.run_status) if s.run_status is not None else None


def _phase(s: WasherStatus) -> str | None:
    if not s.power or s.run_status not in (RunStatus.RUNNING, RunStatus.PAUSED):
        return "none"
    return s.phase or "none"


@dataclass(frozen=True, kw_only=True)
class WasherSensorDescription(SensorEntityDescription):
    value_fn: Callable[[WasherStatus], str | int | None]
    unreachable_value: str | None = None  # shown instead of unavailable


SENSORS = (
    WasherSensorDescription(
        key="state",
        device_class=SensorDeviceClass.ENUM,
        options=["off", *STATES.values()],
        value_fn=_state,
        unreachable_value="off",
    ),
    WasherSensorDescription(
        key="phase",
        device_class=SensorDeviceClass.ENUM,
        options=["none", *PHASES.values()],
        value_fn=_phase,
    ),
    WasherSensorDescription(
        key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda s: s.remaining_minutes if s.power else 0,
    ),
    WasherSensorDescription(
        key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: f"E{s.error_code:X}" if s.error_code else "none",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasherConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = entry.runtime_data
    async_add_entities(
        [WasherSensor(client, d) for d in SENSORS] + [FinishTimeSensor(client)]
    )


class WasherSensor(WasherEntity, SensorEntity):
    entity_description: WasherSensorDescription

    def __init__(self, client: WasherClient, description: WasherSensorDescription) -> None:
        super().__init__(client, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available or self.entity_description.unreachable_value is not None

    @property
    def native_value(self) -> str | int | None:
        if not super().available:
            return self.entity_description.unreachable_value
        return self.entity_description.value_fn(self.status)


class FinishTimeSensor(WasherEntity, SensorEntity):
    """Expected end of the running cycle; stable unless it moves by > 1 min."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, client: WasherClient) -> None:
        super().__init__(client, "finish_time")
        self._finish: datetime | None = None

    @property
    def native_value(self) -> datetime | None:
        s = self.status
        if not s.power or s.run_status not in (RunStatus.RUNNING, RunStatus.DELAYED):
            self._finish = None
            return None
        # Unverified whether remaining time includes the delay while DELAYED.
        finish = dt_util.utcnow().replace(second=0, microsecond=0) + timedelta(
            minutes=s.remaining_minutes
        )
        if self._finish is None or abs(finish - self._finish) > timedelta(minutes=1):
            self._finish = finish
        return self._finish
