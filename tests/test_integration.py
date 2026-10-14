"""End-to-end tests against a simulated washer."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.midea_washer.const import DOMAIN

DATA = {
    "device_id": 152832116467482,
    "host": "192.168.178.36",
    "port": 6444,
    "protocol": 3,
    "model": "38123704",
    "serial_number": "0000DB5103812370438225A006781R0A",
    "token": "00" * 64,
    "key": "11" * 32,
}
DISCOVERED = {
    "device_id": DATA["device_id"],
    "type": 0xDB,
    "ip_address": DATA["host"],
    "port": 6444,
    "model": DATA["model"],
    "sn": DATA["serial_number"],
    "protocol": 3,
}
E = "waschmaschine"


async def setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Waschmaschine", data=DATA, unique_id=str(DATA["device_id"]))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_manual(hass: HomeAssistant) -> None:
    with (
        patch("custom_components.midea_washer.config_flow._discover", return_value=DISCOVERED),
        patch("custom_components.midea_washer.config_flow._can_connect", return_value=True),
        patch("custom_components.midea_washer.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": DATA["host"]})
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "manual"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": DATA["token"].upper(), "key": DATA["key"]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == DATA


async def test_states_from_live_frame(hass: HomeAssistant, washer) -> None:
    await setup(hass)
    fake = washer.instances[0]
    from tests.conftest import LIVE_BODY

    fake.body[:] = LIVE_BODY
    fake.push()
    await hass.async_block_till_done()
    assert hass.states.get(f"select.{E}_program").state == "mix"
    assert hass.states.get(f"select.{E}_temperature").state == "40"
    assert hass.states.get(f"select.{E}_spin_speed").state == "800"
    assert hass.states.get(f"sensor.{E}_status").state == "running"
    assert hass.states.get(f"sensor.{E}_phase").state == "wash"
    assert hass.states.get(f"sensor.{E}_remaining_time").state == "69"
    assert hass.states.get(f"binary_sensor.{E}_remote_control_enabled").state == "off"
    options = hass.states.get(f"select.{E}_program").attributes["options"]
    assert len(options) == 15 and "eco_40_60" in options


async def test_run_program_sequence(hass: HomeAssistant, washer) -> None:
    await setup(hass)
    fake = washer.instances[0]
    await hass.services.async_call(
        DOMAIN,
        "run_program",
        {"entity_id": f"select.{E}_program", "program": "cotton", "temperature": "60",
         "spin_speed": "1400", "pre_wash": True},
        blocking=True,
    )
    sent = [b.hex() for b in fake.sent]
    assert sent[0] == "02" + "01" + "ff" * 20  # power on
    assert sent[1][8:10] == "00" and sent[1][26:28] == "ff"  # program cotton, merge off
    opts = fake.sent[2]
    assert (opts[7], opts[8], opts[16] & 1) == (5, 6, 1)  # 60 °C, 1400 rpm, pre-wash
    assert opts[4] == 0xFF  # program not re-sent
    assert fake.sent[3][2] == 1 and fake.sent[3][13] == 0xFF  # start, merge off
    assert hass.states.get(f"sensor.{E}_status").state == "running"
    assert hass.states.get(f"switch.{E}_pre_wash").state == "on"


async def test_option_not_offered_by_program(hass: HomeAssistant, washer) -> None:
    await setup(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "run_program",
            {"entity_id": f"select.{E}_program", "program": "spin_only", "temperature": "40"},
            blocking=True,
        )
    assert washer.instances[0].sent == []


async def test_remote_control_required(hass: HomeAssistant, washer) -> None:
    await setup(hass)
    fake = washer.instances[0]
    fake.body[31] &= ~0x04
    fake.push()
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": f"switch.{E}_power"}, blocking=True
        )
    assert fake.sent == []


async def test_option_select_follows_program(hass: HomeAssistant, washer) -> None:
    await setup(hass)
    fake = washer.instances[0]
    fake.body[1], fake.body[4] = 1, 9  # on, spin only
    fake.push()
    await hass.async_block_till_done()
    assert hass.states.get(f"select.{E}_temperature").state == "unavailable"
    assert hass.states.get(f"switch.{E}_pre_wash").state == "unavailable"
    await hass.services.async_call(
        "select", "select_option", {"entity_id": f"select.{E}_spin_speed", "option": "400"}, blocking=True
    )
    assert fake.sent[-1][8] == 1 and fake.sent[-1][4] == 0xFF


async def test_pause_and_resume(hass: HomeAssistant, washer) -> None:
    await setup(hass)
    fake = washer.instances[0]
    fake.body[1], fake.body[2] = 1, 2
    fake.push()
    await hass.async_block_till_done()
    await hass.services.async_call("button", "press", {"entity_id": f"button.{E}_pause"}, blocking=True)
    assert fake.sent[-1][2] == 0 and fake.sent[-1][4] == 0xFF
    assert hass.states.get(f"sensor.{E}_status").state == "paused"
    await hass.services.async_call("button", "press", {"entity_id": f"button.{E}_start"}, blocking=True)
    assert fake.sent[-1][2] == 1
    assert hass.states.get(f"sensor.{E}_status").state == "running"


async def test_unreachable_means_off(hass: HomeAssistant, washer) -> None:
    await setup(hass)
    fake = washer.instances[0]
    fake.body[1], fake.body[2] = 1, 1
    fake.push()
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.{E}_power").state == "on"
    fake.go_offline()
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.{E}_power").state == "off"
    assert hass.states.get(f"sensor.{E}_status").state == "off"
    assert hass.states.get(f"select.{E}_program").state == "unavailable"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": f"switch.{E}_power"}, blocking=True
        )
    assert fake.sent == []
    fake.push()  # switched on at the panel, reconnected
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.{E}_status").state == "standby"
    assert hass.states.get(f"select.{E}_program").state == "mix"


def test_reconnect_interval_is_fixed() -> None:
    from custom_components.midea_washer.client import _Transport

    t = _Transport.__new__(_Transport)
    t._socket, t._is_run = None, True
    calls: list[float] = []

    def connect(check_protocol: bool = False) -> bool:
        calls.append(0)
        if len(calls) == 4:
            t._socket = object()
            return True
        return False

    t.connect = connect
    t._should_run = lambda: True
    with patch("custom_components.midea_washer.client.time.sleep") as sleep:
        t._connect_loop()
    assert len(calls) == 4 and sleep.call_count == 3 * 5


async def test_unload(hass: HomeAssistant, washer) -> None:
    entry = await setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
