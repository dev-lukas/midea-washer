"""One-time: fetch V3 token/key, lua codec and UI plugin for the washer.

Credentials are read from ~/.config/midea-washer/cloud.json:
  {"username": "...", "password": "..."}
"""
import asyncio, json, sys
from pathlib import Path
import aiohttp
from midealocal.cloud import get_midea_cloud

DEVICE_ID = 152832116467482
SN = "0000DB5103812370438225A006781R0A"
OUT = sys.argv[1]

async def main():
    cred = json.loads((Path.home() / ".config/midea-washer/cloud.json").read_text())
    async with aiohttp.ClientSession() as s:
        cloud = get_midea_cloud("SmartHome", s, cred["username"], cred["password"])
        print("login:", await cloud.login())
        keys = await cloud.get_cloud_keys(DEVICE_ID)
        Path(f"{OUT}/keys.json").write_text(json.dumps({str(k): v for k, v in keys.items()}, indent=1))
        print("keys for methods:", list(keys))
        print("lua:", await cloud.download_lua(OUT, 0xDB, SN, None, "0000"))
        print("plugin:", await cloud.download_plugin(OUT, 0xDB, SN))

asyncio.run(main())
