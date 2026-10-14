"""Cross-check the Python codec against the vendor lua (T_0000_DB_41.lua).

Needs lupa and the lua file from research/cloud (not shipped); skipped otherwise.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LUA = ROOT / "research/cloud/T_0000_DB_41.lua"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "custom_components/midea_washer"))

lupa = pytest.importorskip("lupa")
if not LUA.exists():
    pytest.skip("vendor lua not available", allow_module_level=True)

from luacodec import LuaCodec  # noqa: E402
from protocol import Control, WasherStatus, build_control  # noqa: E402

PROGRAM_NAMES = {
    0: "cotton", 2: "fast_wash", 3: "mixed_wash", 4: "fiber", 5: "wool", 7: "ssp",
    9: "single_dehytration", 10: "rinsing_dehydration", 16: "color", 18: "quick_wash",
    54: "jean", 108: "eco_40_60", 109: "steam_care", 110: "allergy_care", 115: "bulky",
}
TEMPS = {1: "0", 2: "20", 3: "30", 4: "40", 5: "60", 6: "95", 7: "70", 8: "90", 9: "50"}
SPEEDS = {0: "0", 1: "400", 2: "600", 3: "800", 4: "1000", 5: "1200", 6: "1400", 7: "1600", 8: "1300"}
WATER = {1: "low", 2: "mid", 3: "high", 4: "4", 5: "auto"}
ONOFF = {True: "on", False: "off"}

# Real frame captured from the washer (Mix, 40 °C, 800 rpm, washing).
LIVE = "aa33db000000000000030301020003052004030000000000000004450000db39414c0000002f0880000000000000000000000019"


def frame(body: bytes) -> str:
    msg = bytes([0xAA, len(body) + 10, 0xDB, 0, 0, 0, 0, 0, 0, 0x03]) + body
    return (msg + bytes([(-sum(msg[1:])) & 0xFF])).hex()


def random_body(rng: random.Random) -> bytes:
    b = bytearray(40)
    b[0] = 0x03
    b[1] = rng.choice([0, 1])
    b[2] = rng.randint(0, 6)
    b[4] = rng.choice(list(PROGRAM_NAMES))
    b[5] = rng.choice(list(WATER))
    b[6] = rng.randint(0, 5) << 4 | rng.randint(0, 14)
    b[7] = rng.choice(list(TEMPS))
    b[8] = rng.choice(list(SPEEDS))
    b[9], b[10] = rng.randint(0, 60), rng.randint(0, 15)
    b[11], b[12] = rng.randint(0, 5), rng.randint(0, 5)
    b[13] = rng.randint(0, 255)
    b[14], b[15] = rng.randint(0, 255), rng.randint(0, 5)
    b[16] = rng.choice([0, 1, 2, 4, 8, 16, 32, 64])
    b[17], b[18] = rng.randint(0, 255), rng.randint(0, 1)
    b[21], b[22] = 0x39, 0x41
    b[25] = rng.randint(0, 255)
    b[26] = rng.randint(0, 9)
    b[27], b[28] = rng.randint(0, 60), rng.randint(0, 15)
    b[29] = rng.randint(0, 255)
    b[30] = rng.randint(0, 4)
    b[31] = rng.randint(0, 15)
    return bytes(b)


def lua_control(ctl: Control) -> dict:
    out: dict = {}
    if ctl.power is not None:
        return {"power": ONOFF[ctl.power]}
    if ctl.start is not None:
        out["control_status"] = "start" if ctl.start else "pause"
    if ctl.program is not None:
        out["program"] = PROGRAM_NAMES[ctl.program]
    if ctl.temperature is not None:
        out["temperature"] = TEMPS[ctl.temperature]
    if ctl.spin_speed is not None:
        out["dehydration_speed"] = SPEEDS[ctl.spin_speed]
    if ctl.water_level is not None:
        out["water_level"] = WATER[ctl.water_level]
    if ctl.lock is not None:
        out["lock"] = ONOFF[ctl.lock]
    if ctl.pre_wash is not None:
        out["beforehand_wash"] = ONOFF[ctl.pre_wash]
    if ctl.extra_rinse is not None:
        out["super_clean_wash"] = ONOFF[ctl.extra_rinse]
    if ctl.turbo is not None:
        out["fast_clean_wash"] = ONOFF[ctl.turbo]
    if ctl.silent is not None:
        out["silent"] = "1" if ctl.silent else "0"
    if ctl.delay_minutes is not None:
        out["appointment"] = ONOFF[ctl.delay_minutes > 0]
        out["appointment_time"] = ctl.delay_minutes
    if not ctl.merge:
        out["merge"] = "false"
    return out


def random_control(rng: random.Random) -> Control:
    kind = rng.randint(0, 5)
    if kind == 0:
        return Control(power=rng.choice([True, False]))
    if kind == 1:
        return Control(start=rng.choice([True, False]), merge=False)
    if kind == 2:
        return Control(program=rng.choice(list(PROGRAM_NAMES)), merge=False)
    ctl = Control()
    for name, pool in (
        ("temperature", list(TEMPS)), ("spin_speed", list(SPEEDS)), ("water_level", list(WATER)),
        ("lock", [True, False]), ("pre_wash", [True, False]), ("extra_rinse", [True, False]),
        ("turbo", [True, False]), ("silent", [True, False]), ("delay_minutes", [0, 90, 600]),
    ):
        if rng.random() < 0.4:
            setattr(ctl, name, rng.choice(pool))
    return ctl


@pytest.fixture(scope="module")
def lua() -> LuaCodec:
    return LuaCodec(LUA)


def encode_with_lua(lua: LuaCodec, body: bytes, ctl: Control) -> bytes:
    status = lua.decode(frame(body))["status"]
    hexframe = lua.encode(lua_control(ctl), status=status)
    return bytes.fromhex(hexframe)[10:-1]


def test_live_frame_decodes(lua: LuaCodec) -> None:
    st = WasherStatus.parse(bytes.fromhex(LIVE)[10:-1])
    ref = lua.decode(LIVE)["status"]
    assert st.program == 3 and ref["program"] == "mixed_wash"
    assert st.remaining_minutes == ref["remain_time"] == 69
    assert st.project_no == ref["project_no"] == 16697
    assert st.phase == "wash"
    assert st.remote_control is (ref["remote_control_flag"] == "1")


@pytest.mark.parametrize("seed", range(400))
def test_encoder_matches_lua(lua: LuaCodec, seed: int) -> None:
    rng = random.Random(seed)
    body = bytes.fromhex(LIVE)[10:-1] if seed == 0 else random_body(rng)
    ctl = random_control(rng)
    ours = build_control(WasherStatus(body), ctl)
    theirs = encode_with_lua(lua, body, ctl)
    assert ours.hex(" ") == theirs.hex(" "), json.dumps(lua_control(ctl))


@pytest.mark.parametrize("seed", range(200))
def test_decoder_matches_lua(lua: LuaCodec, seed: int) -> None:
    body = random_body(random.Random(seed))
    st = WasherStatus(body)
    ref = lua.decode(frame(body))["status"]
    assert st.remaining_minutes == ref["remain_time"]
    assert st.remote_control is (ref["remote_control_flag"] == "1")
    assert st.option("lock") is (ref["lock"] == "on")
    assert st.option("pre_wash") is (ref["beforehand_wash"] == "on")
    assert st.option("extra_rinse") is (ref["super_clean_wash"] == "on")
    assert st.option("turbo") is (ref["fast_clean_wash"] == "on")
    assert st.option("silent") is (ref["silent"] == "1")
    assert st.delay_minutes == ref["appointment_time"]
    assert st.rinse_count == int(ref["soak_count"])
