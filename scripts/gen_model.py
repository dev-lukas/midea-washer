"""Turn the plugin's per-model JSON (en + de) into the integration's model file."""
import json, sys
from pathlib import Path

SLUGS = {
    0: "cotton", 2: "quick_15", 3: "mix", 4: "synthetic", 5: "wool", 7: "drum_clean",
    9: "spin_only", 10: "rinse_spin", 16: "cold_20", 18: "rapid_45", 54: "jeans",
    108: "eco_40_60", 109: "steam_care", 110: "allergy_care", 115: "bulky",
}
# plugin commandName -> integration option key
PARAMS = {"temperature": "temperature", "dewatering_speed": "spin_speed", "water_level": "water_level",
          "pre_wash": "pre_wash", "extra_rinse": "extra_rinse", "FCS": "turbo", "silent": "silent"}

src, sub, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
en = json.loads((src / f"DB_0000.db.{sub}.json").read_text())
de = json.loads((src / f"DB_0000.db.{sub}_de.json").read_text())
de_names = {p["value"]: p["modeName"] for p in de["paramData"]}
programs = []
for p in en["paramData"]:
    params = {}
    for a in p["paramArray"]:
        key = PARAMS[a["commandName"]]
        params[key] = {"values": a["paramProtocolArray"], "labels": a["paramArray"],
                       "default": a["paramProtocolArray"][a["defaultIndex"]]}
    programs.append({"value": p["value"], "slug": SLUGS[p["value"]], "name_en": p["modeName"],
                     "name_de": de_names[p["value"]], "default_minutes": int(p["defaultTime"]),
                     "options": params})
model = {"subtype": int(sub), "model_name": en["modelName"],
         "locked_while_running": [PARAMS[k] for k in en.get("notSupportChangeParams", [])],
         "requires_remote_control": bool(en.get("notRemoteControlSwitch")),
         "delay_by_minute": bool(en.get("reserveStartByMinute")), "programs": programs}
out.write_text(json.dumps(model, indent=1, ensure_ascii=False) + "\n")
print(out, len(programs), "programs")
