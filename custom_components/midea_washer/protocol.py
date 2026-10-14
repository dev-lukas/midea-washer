"""Midea 0xDB front-loader protocol: status decoding and control encoding.

Pure Python port of the vendor codec T_0000_DB_41.lua (the script the
SmartHome app downloads for this washer). Bodies here start at the body-type
byte, i.e. offset 10 of the AA frame; framing and encryption are midea-local's job.

Encoding follows the vendor codec exactly, so the washer sees the same bytes the
app would send: scalar fields not being changed are sent as 0xFF ("keep"),
2-bit flag fields as 3 ("keep"). The 1-bit flags packed into control bytes 13
and 16 have no "keep" value; they are re-sent from the current status, or the
whole byte is sent as 0xFF when merge is off (program select, start/pause).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

BODY_CONTROL = 0x02
BODY_QUERY = 0x03
CONTROL_BODY_LEN = 22
KEEP = 0xFF

# Status body data types that carry the full appliance state.
STATE_BODY_TYPES = (0x02, 0x03, 0x04)


class RunStatus(IntEnum):
    IDLE = 0
    STANDBY = 1
    RUNNING = 2
    PAUSED = 3
    FINISHED = 4
    FAULT = 5
    DELAYED = 6


# Progress byte is a one-hot phase flag.
PHASES = {
    0x01: "spin",
    0x02: "rinse",
    0x04: "wash",
    0x08: "pre_wash",
    0x10: "dry",
    0x20: "weigh",
    0x40: "high_speed_spin",
}

# 1-bit options as (status byte, bit) -> (control byte, bit).
FLAG_BITS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "lock": ((13, 5), (13, 5)),
    "pre_wash": ((25, 0), (16, 0)),
    "extra_rinse": ((25, 1), (16, 1)),
    "turbo": ((25, 5), (16, 5)),
}
# 2-bit options (3 = keep) as (status byte, bit) -> (control byte, shift).
PAIR_BITS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "silent": ((31, 3), (19, 6)),
}
OPTIONS = (*FLAG_BITS, *PAIR_BITS)
PAIR_KEEP = 0b11


def _bit(value: int | None, bit: int) -> bool:
    return value is not None and bool(value >> bit & 1)


def _byte(body: bytes, idx: int) -> int | None:
    return body[idx] if idx < len(body) else None


@dataclass(frozen=True, slots=True)
class WasherStatus:
    """Decoded 0x02/0x03/0x04 status body."""

    body: bytes

    @classmethod
    def parse(cls, body: bytes) -> WasherStatus | None:
        if len(body) < 19 or body[0] not in STATE_BODY_TYPES:
            return None
        return cls(bytes(body))

    @property
    def power(self) -> bool:
        return self.body[1] == 1

    @property
    def run_status(self) -> RunStatus | None:
        try:
            return RunStatus(self.body[2])
        except ValueError:
            return None

    @property
    def program(self) -> int:
        return self.body[4]

    @property
    def water_level(self) -> int:
        return self.body[5]

    @property
    def rinse_count(self) -> int:
        return self.body[6] >> 4

    @property
    def temperature(self) -> int:
        return self.body[7]

    @property
    def spin_speed(self) -> int:
        return self.body[8]

    @property
    def delay_minutes(self) -> int:
        return self.body[14] | self.body[15] << 8

    @property
    def phase(self) -> str | None:
        return PHASES.get(self.body[16])

    @property
    def remaining_minutes(self) -> int:
        return self.body[17] | self.body[18] << 8

    @property
    def error_code(self) -> int:
        return _byte(self.body, 24) or 0

    @property
    def project_no(self) -> int | None:
        lo, hi = _byte(self.body, 21), _byte(self.body, 22)
        return None if lo is None or hi is None else lo | hi << 8

    @property
    def wash_minutes(self) -> int | None:
        return _byte(self.body, 27)

    @property
    def spin_minutes(self) -> int | None:
        return _byte(self.body, 28)

    @property
    def remote_control(self) -> bool:
        return _bit(_byte(self.body, 31), 2)

    def option(self, name: str) -> bool:
        (idx, bit), _ = (FLAG_BITS | PAIR_BITS)[name]
        return _bit(_byte(self.body, idx), bit)

    @property
    def running(self) -> bool:
        return self.run_status in (RunStatus.RUNNING, RunStatus.DELAYED)


@dataclass(slots=True)
class Control:
    """A control request. None means: leave unchanged."""

    power: bool | None = None
    start: bool | None = None  # True = start/resume, False = pause
    program: int | None = None
    temperature: int | None = None
    spin_speed: int | None = None
    water_level: int | None = None
    lock: bool | None = None
    pre_wash: bool | None = None
    extra_rinse: bool | None = None
    turbo: bool | None = None
    silent: bool | None = None
    delay_minutes: int | None = None  # 0 = no delayed start
    merge: bool = True  # False: leave the option bytes 13/16 untouched (0xFF)


def query_body() -> bytes:
    return bytes([BODY_QUERY])


def _flag_bytes(s: bytes) -> tuple[int, int]:
    """Current 1-bit flags as control bytes 13 and 16."""

    def b(i: int) -> int:
        return s[i] if i < len(s) else 0

    return b(13), (b(25) & 0x3F) | (b(29) & 0x01) << 6


def _set_bit(value: int, bit: int, on: bool) -> int:
    return value | 1 << bit if on else value & ~(1 << bit) & 0xFF


def build_control(status: WasherStatus, ctl: Control) -> bytes:
    """Encode a control body (body type 0x02) on top of the current status."""
    c = bytearray([KEEP] * CONTROL_BODY_LEN)
    c[0] = BODY_CONTROL
    if ctl.power is not None:
        c[1] = int(ctl.power)
        return bytes(c)

    if ctl.start is not None:
        c[2] = int(ctl.start)
    for idx, value in (
        (4, ctl.program),
        (5, ctl.water_level),
        (7, ctl.temperature),
        (8, ctl.spin_speed),
    ):
        if value is not None:
            c[idx] = value

    c[13], c[16] = _flag_bytes(status.body)
    for name, (_, (idx, bit)) in FLAG_BITS.items():
        if (value := getattr(ctl, name)) is not None:
            c[idx] = _set_bit(c[idx], bit, value)
    if ctl.delay_minutes is not None:
        c[13] = _set_bit(c[13], 1, ctl.delay_minutes > 0)
        c[14], c[15] = ctl.delay_minutes & 0xFF, ctl.delay_minutes >> 8 & 0xFF

    # Bytes 18, 19, 21 are four 2-bit fields each (byte 21 only three).
    c[18], c[19], c[21] = 0xFF, 0xFF, 0x3F
    for name, (_, (idx, shift)) in PAIR_BITS.items():
        if (value := getattr(ctl, name)) is not None:
            c[idx] = c[idx] & ~(PAIR_KEEP << shift) & 0xFF | int(value) << shift

    if ctl.start is False:
        c[4] = KEEP
    if not ctl.merge:
        c[13] = c[16] = KEEP
    return bytes(c)
