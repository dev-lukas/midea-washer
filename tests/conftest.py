"""Shared fixtures: a simulated washer behind the client's transport."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

from custom_components.midea_washer.protocol import KEEP, WasherStatus

# Captured live: power on, Mix, 40 °C, 800 rpm, washing, 69 min left (remote control off).
LIVE_BODY = bytes.fromhex(
    "0301020003052004030000000000000004450000db39414c0000002f088000000000000000000000"
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeWasher:
    """Applies control bodies like the firmware and answers with status frames."""

    instances: list[FakeWasher] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.sent: list[bytes] = []
        self.callbacks: list[Callable[[dict[str, Any]], None]] = []
        body = bytearray(LIVE_BODY)
        body[1], body[2] = 0, 0  # off, idle
        body[31] |= 0x04  # remote control enabled
        self.body = body
        FakeWasher.instances.append(self)

    def register_update(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self.callbacks.append(cb)

    def unregister_update(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self.callbacks.remove(cb)

    def open(self) -> None:
        self.push()

    def close(self) -> None:
        pass

    def push(self) -> None:
        for cb in list(self.callbacks):
            cb({"status": WasherStatus(bytes(self.body))})

    def go_offline(self) -> None:
        """What midea-local reports once the washer has been switched off."""
        for cb in list(self.callbacks):
            cb({"available": False})

    def send_query(self) -> None:
        self.push()

    def send_body(self, c: bytes) -> None:
        self.sent.append(c)
        b = self.body
        if c[1] != KEEP:
            b[1] = c[1]
            b[2] = 1 if c[1] else 0
        if c[2] != KEEP:
            b[2] = 2 if c[2] == 1 else 3
        for i in (4, 5, 7, 8):
            if c[i] != KEEP:
                b[i] = c[i]
        if c[13] != KEEP:
            b[13] = c[13]
            if c[13] & 0x02 and c[14] != KEEP:
                b[14], b[15] = c[14], c[15]
        if c[16] != KEEP:
            b[25] = (b[25] & 0xC0) | (c[16] & 0x3F)
        if (c[19] >> 6) != 3:
            b[31] = (b[31] & ~0x08) | ((c[19] >> 6 & 1) << 3)
        b[0] = 0x02
        self.push()


@pytest.fixture
def washer():
    FakeWasher.instances.clear()
    with patch("custom_components.midea_washer.client._Transport", FakeWasher):
        yield FakeWasher
