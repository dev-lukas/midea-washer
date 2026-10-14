"""Print the SmartHome cloud's appliance record for the washer (no secrets)."""
import asyncio, json
from pathlib import Path
import aiohttp
from midealocal.cloud import get_midea_cloud

async def main():
    cred = json.loads((Path.home() / ".config/midea-washer/cloud.json").read_text())
    async with aiohttp.ClientSession() as s:
        cloud = get_midea_cloud("SmartHome", s, cred["username"], cred["password"])
        await cloud.login()
        apps = await cloud.list_appliances(None) or {}
        for k, v in apps.items():
            print(k, json.dumps(v, default=str))
        info = await cloud.get_device_info(152832116467482)
        print("device_info:", json.dumps(info, default=str))

asyncio.run(main())
