"""Run a Midea device lua codec (jsonToData / dataToJson) under lupa.

The vendor scripts target LuaJIT (`bit`, `cjson`); both are shimmed here.
"""

import json
import re
from pathlib import Path

from lupa.lua55 import LuaRuntime

_SHIMS = r"""
local function u32(x) return x & 0xFFFFFFFF end
package.preload["bit"] = function()
  return {
    band = function(...) local r = 0xFFFFFFFF for _, v in ipairs({...}) do r = r & math.tointeger(v) end return u32(r) end,
    bor = function(...) local r = 0 for _, v in ipairs({...}) do r = r | math.tointeger(v) end return u32(r) end,
    bxor = function(...) local r = 0 for _, v in ipairs({...}) do r = r ~ math.tointeger(v) end return u32(r) end,
    bnot = function(a) return u32(~math.tointeger(a)) end,
    lshift = function(a, n) return u32(math.tointeger(a) << n) end,
    rshift = function(a, n) return u32(math.tointeger(a)) >> n end,
    arshift = function(a, n) return math.tointeger(a) >> n end,
    tohex = function(a, n) return string.format("%0" .. (n or 8) .. "x", u32(math.tointeger(a))) end,
  }
end
package.preload["cjson"] = function()
  return { decode = py_json_decode, encode = py_json_encode }
end
"""


def _relax_loop_vars(src: str) -> str:
    """Lua 5.5 makes for-loop variables const; the vendor scripts assign to them.

    Rebind each loop variable as a body-local so the scripts behave as on LuaJIT.
    """
    src = re.sub(
        r"\bfor\s+(\w+)\s*,\s*(\w+)\s+in\s+(.+?)\s+do\b",
        r"for __k, __v in \3 do local \1, \2 = __k, __v",
        src,
    )
    return re.sub(
        r"\bfor\s+(\w+)\s*=\s*(.+?)\s+do\b",
        r"for __i = \2 do local \1 = __i",
        src,
    )


class LuaCodec:
    def __init__(self, path: str | Path) -> None:
        self._lua = LuaRuntime(unpack_returned_tuples=True)
        g = self._lua.globals()
        g.py_json_decode = self._decode
        g.py_json_encode = self._encode
        self._lua.execute(_SHIMS)
        self._lua.execute(_relax_loop_vars(Path(path).read_text()))
        self._j2d = g.jsonToData
        self._d2j = g.dataToJson

    def _decode(self, s: str):
        return self._to_lua(json.loads(s))

    def _to_lua(self, v):
        if isinstance(v, dict):
            return self._lua.table_from({k: self._to_lua(x) for k, x in v.items()})
        if isinstance(v, list):
            return self._lua.table_from([self._to_lua(x) for x in v])
        return v

    def _encode(self, t) -> str:
        return json.dumps(self._from_lua(t), ensure_ascii=False)

    def _from_lua(self, t):
        if not hasattr(t, "items"):
            return t
        items = dict(t.items())
        if items and all(isinstance(k, int) for k in items) and sorted(items) == list(
            range(1, len(items) + 1)
        ):
            return [self._from_lua(items[i]) for i in range(1, len(items) + 1)]
        return {str(k): self._from_lua(v) for k, v in items.items()}

    def encode(self, control: dict, subtype: int = 0, status: dict | None = None) -> str:
        cmd = {"deviceinfo": {"deviceSubType": subtype}, "control": control}
        if status:
            cmd["status"] = status
        return self._j2d(json.dumps(cmd))

    def query(self, subtype: int = 0) -> str:
        return self._j2d(json.dumps({"deviceinfo": {"deviceSubType": subtype}, "query": {}}))

    def decode(self, frame_hex: str, subtype: int = 0) -> dict:
        out = self._d2j(
            json.dumps({"deviceinfo": {"deviceSubType": subtype}, "msg": {"data": frame_hex}})
        )
        return json.loads(out)


if __name__ == "__main__":
    import sys

    codec = LuaCodec(sys.argv[1])
    print("query  :", codec.query())
    print("decode :", json.dumps(codec.decode(sys.argv[2]) if len(sys.argv) > 2 else {}, indent=1))
    print("program:", codec.encode({"program": "cotton", "temperature": "40", "control_status": "start"}))
