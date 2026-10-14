"""Connect to the washer over LAN, capture raw frames, decode with midea-local and the vendor lua.

Read-only: only sends the standard status query midea-local issues on its own.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from luacodec import LuaCodec  # noqa: E402
from midealocal.devices.db import MideaDBDevice  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEYS = json.loads((ROOT / "research/cloud/keys.json").read_text())
LUA = ROOT / "research/cloud/T_0000_DB_41.lua"
SUBTYPE = 16697
frames: list[bytes] = []


class Probe(MideaDBDevice):
    def process_message(self, msg: bytes):
        frames.append(bytes(msg))
        return super().process_message(msg)


def main() -> None:
    method = sys.argv[1] if len(sys.argv) > 1 else "1"
    dev = Probe(
        name="Waschmaschine",
        device_id=152832116467482,
        ip_address="192.168.178.36",
        port=6444,
        token=KEYS[method]["token"],
        key=KEYS[method]["key"],
        device_protocol=3,
        model="38123704",
        subtype=SUBTYPE,
        customize="",
    )
    dev.open()
    deadline = time.time() + float(sys.argv[2] if len(sys.argv) > 2 else 15)
    while time.time() < deadline and not frames:
        time.sleep(0.5)
    time.sleep(1)
    dev.close()
    print("available:", dev.available)
    print("midea-local attrs:", json.dumps({k: v for k, v in dev.attributes.items() if k != "washing_data"}, default=str))
    codec = LuaCodec(LUA)
    for f in frames:
        print("frame:", f.hex())
        st = codec.decode(f.hex(), SUBTYPE)["status"]
        print("lua  :", json.dumps(dict(sorted(st.items())), ensure_ascii=False))


if __name__ == "__main__":
    main()
