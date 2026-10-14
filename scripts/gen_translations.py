"""Write strings.json / translations/{en,de}.json for the integration."""
import json
from pathlib import Path

CC = Path(__file__).resolve().parent.parent / "custom_components/midea_washer"
model = json.loads((CC / "models/16697.json").read_text())
SUBS = {"en": {}, "de": {}}
L = {
 "en": {
  "title": "Midea Washer (local)",
  "user": ("Find washer", "IP address of the washer. It must have a fixed IP (DHCP reservation).", "Host"),
  "auth": ("Encryption key", "This washer uses protocol V3 and needs a token/key pair, which only the Midea cloud hands out. You can fetch it once with your SmartHome account (not stored), or enter it manually.", {"cloud": "Fetch once from SmartHome cloud", "manual": "Enter token and key"}),
  "manual": ("Token and key", None, "Token", "Key"),
  "cloud": ("SmartHome account", "Used once to fetch the key; not stored.", "E-mail", "Password"),
  "errors": {"not_found": "No Midea device answered at this address.", "invalid_auth": "Token/key rejected by the washer.", "cloud_login": "SmartHome login failed.", "cloud_error": "Midea cloud error, see log."},
  "abort": {"not_a_washer": "This Midea device is not a front-load washer (type 0xDB).", "already_configured": "This washer is already configured."},
  "entities": {
   "select": {"program": "Program", "temperature": "Temperature", "spin_speed": "Spin speed", "water_level": "Water level"},
   "switch": {"power": "Power", "child_lock": "Child lock", "pre_wash": "Pre-wash", "extra_rinse": "Extra rinse", "turbo": "Turbo", "silent": "Mute end signal"},
   "button": {"start": "Start", "pause": "Pause"},
   "number": {"delay_start": "Delayed start"},
   "sensor": {"state": "Status", "phase": "Phase", "remaining_time": "Remaining time", "finish_time": "Finish time", "error_code": "Error code"},
   "binary_sensor": {"remote_control": "Remote control enabled"},
  },
  "temperature": {"cold": "Cold", "20": "20 °C", "30": "30 °C", "40": "40 °C", "50": "50 °C", "60": "60 °C", "70": "70 °C", "90": "90 °C", "95": "95 °C"},
  "spin_speed": {"0": "No spin", **{k: f"{k} rpm" for k in ["400","600","800","1000","1200","1300","1400","1600"]}},
  "water_level": {"auto": "Auto", "1": "Level 1", "2": "Level 2", "3": "Level 3", "4": "Level 4"},
  "state": {"off": "Off", "idle": "Idle", "standby": "Ready", "running": "Running", "paused": "Paused", "finished": "Finished", "fault": "Fault", "delayed": "Delayed start"},
  "phase": {"none": "None", "weigh": "Weighing", "pre_wash": "Pre-wash", "wash": "Washing", "rinse": "Rinsing", "spin": "Spinning", "high_speed_spin": "High-speed spin", "dry": "Drying"},
  "error_none": "None",
  "exceptions": {
   "not_connected": "The washer is off or unreachable. It can only be switched on at its panel (it leaves Wi-Fi while off).",
   "remote_control_off": "Remote control is off. Enable it on the washer panel first.",
   "no_confirmation": "The washer did not confirm the command.",
   "busy": "The program cannot be changed while a cycle is running or paused.",
   "unknown_model": "No program table for this washer model.",
   "option_not_supported": "'{option}' is not available for the current program.",
   "value_not_supported": "Value {value} for '{option}' is not available for this program.",
   "locked_while_running": "'{option}' cannot be changed while a cycle is running.",
   "powered_off": "The washer is off. Switch it on at its panel first.",
  },
  "service": ("Run program", "Turn the washer on, select a program and options, and start it.",
    {"program": ("Program", "Program to run."), "temperature": ("Temperature", "Leave empty for the program default."), "spin_speed": ("Spin speed", "Leave empty for the program default."), "water_level": ("Water level", "Leave empty for the program default."), "pre_wash": ("Pre-wash", ""), "extra_rinse": ("Extra rinse", ""), "turbo": ("Turbo", ""), "silent": ("Mute end signal", ""), "delay": ("Delay (minutes)", "Delayed start in minutes, 0 = start now.")}),
 },
 "de": {
  "title": "Midea Waschmaschine (lokal)",
  "user": ("Waschmaschine finden", "IP-Adresse der Waschmaschine. Sie braucht eine feste IP (DHCP-Reservierung).", "Host"),
  "auth": ("Schlüssel", "Diese Maschine nutzt Protokoll V3 und braucht Token/Key, die nur die Midea-Cloud ausgibt. Einmalig mit dem SmartHome-Konto abrufen (wird nicht gespeichert) oder manuell eingeben.", {"cloud": "Einmalig aus der SmartHome-Cloud holen", "manual": "Token und Key eingeben"}),
  "manual": ("Token und Key", None, "Token", "Key"),
  "cloud": ("SmartHome-Konto", "Wird nur einmal zum Abrufen des Schlüssels genutzt und nicht gespeichert.", "E-Mail", "Passwort"),
  "errors": {"not_found": "Unter dieser Adresse antwortet kein Midea-Gerät.", "invalid_auth": "Token/Key wurden von der Maschine abgelehnt.", "cloud_login": "SmartHome-Anmeldung fehlgeschlagen.", "cloud_error": "Fehler der Midea-Cloud, siehe Log."},
  "abort": {"not_a_washer": "Dieses Midea-Gerät ist kein Frontlader (Typ 0xDB).", "already_configured": "Diese Waschmaschine ist bereits eingerichtet."},
  "entities": {
   "select": {"program": "Programm", "temperature": "Temperatur", "spin_speed": "Schleuderdrehzahl", "water_level": "Wasserstand"},
   "switch": {"power": "Ein/Aus", "child_lock": "Kindersicherung", "pre_wash": "Vorwäsche", "extra_rinse": "Extra Spülen", "turbo": "Turbo", "silent": "Endsignal stumm"},
   "button": {"start": "Start", "pause": "Pause"},
   "number": {"delay_start": "Startverzögerung"},
   "sensor": {"state": "Status", "phase": "Phase", "remaining_time": "Restzeit", "finish_time": "Fertig um", "error_code": "Fehlercode"},
   "binary_sensor": {"remote_control": "Fernsteuerung aktiv"},
  },
  "temperature": {"cold": "Kalt", "20": "20 °C", "30": "30 °C", "40": "40 °C", "50": "50 °C", "60": "60 °C", "70": "70 °C", "90": "90 °C", "95": "95 °C"},
  "spin_speed": {"0": "Kein Schleudern", **{k: f"{k} U/min" for k in ["400","600","800","1000","1200","1300","1400","1600"]}},
  "water_level": {"auto": "Auto", "1": "Stufe 1", "2": "Stufe 2", "3": "Stufe 3", "4": "Stufe 4"},
  "state": {"off": "Aus", "idle": "Bereit", "standby": "Bereit", "running": "Läuft", "paused": "Pausiert", "finished": "Fertig", "fault": "Störung", "delayed": "Startverzögerung"},
  "phase": {"none": "Keine", "weigh": "Wiegen", "pre_wash": "Vorwäsche", "wash": "Waschen", "rinse": "Spülen", "spin": "Schleudern", "high_speed_spin": "Hochtouriges Schleudern", "dry": "Trocknen"},
  "error_none": "Keiner",
  "exceptions": {
   "not_connected": "Die Waschmaschine ist aus oder nicht erreichbar. Einschalten geht nur am Bedienfeld (ausgeschaltet ist sie nicht im WLAN).",
   "remote_control_off": "Fernsteuerung ist aus. Bitte zuerst am Bedienfeld der Maschine aktivieren.",
   "no_confirmation": "Die Waschmaschine hat den Befehl nicht bestätigt.",
   "busy": "Das Programm kann während eines laufenden oder pausierten Waschgangs nicht geändert werden.",
   "unknown_model": "Für dieses Modell gibt es keine Programmtabelle.",
   "option_not_supported": "'{option}' ist für das aktuelle Programm nicht verfügbar.",
   "value_not_supported": "Wert {value} für '{option}' ist für dieses Programm nicht verfügbar.",
   "locked_while_running": "'{option}' kann während des Waschgangs nicht geändert werden.",
   "powered_off": "Die Maschine ist aus. Zuerst am Bedienfeld einschalten.",
  },
  "service": ("Programm starten", "Schaltet die Maschine ein, wählt Programm und Optionen und startet.",
    {"program": ("Programm", "Auszuführendes Programm."), "temperature": ("Temperatur", "Leer = Programmstandard."), "spin_speed": ("Schleuderdrehzahl", "Leer = Programmstandard."), "water_level": ("Wasserstand", "Leer = Programmstandard."), "pre_wash": ("Vorwäsche", ""), "extra_rinse": ("Extra Spülen", ""), "turbo": ("Turbo", ""), "silent": ("Endsignal stumm", ""), "delay": ("Verzögerung (Minuten)", "Startverzögerung in Minuten, 0 = sofort.")}),
 },
}

def build(lang: str) -> dict:
    t = L[lang]
    names = {p["slug"]: p[f"name_{lang}"] for p in model["programs"]}
    ent = {}
    for platform, items in t["entities"].items():
        ent[platform] = {}
        for key, name in items.items():
            e = {"name": name}
            if platform == "select":
                e["state"] = names if key == "program" else t[key]
            if platform == "sensor" and key in ("state", "phase"):
                e["state"] = t[key]
            if key == "error_code":
                e["state"] = {"none": t["error_none"]}
            ent[platform][key] = e
    sname, sdesc, fields = t["service"]
    return {
        "title": t["title"],
        "config": {
            "step": {
                "user": {"title": t["user"][0], "description": t["user"][1], "data": {"host": t["user"][2]}},
                "auth": {"title": t["auth"][0], "description": t["auth"][1], "menu_options": t["auth"][2]},
                "manual": {"title": t["manual"][0], "data": {"token": t["manual"][2], "key": t["manual"][3]}},
                "cloud": {"title": t["cloud"][0], "description": t["cloud"][1], "data": {"username": t["cloud"][2], "password": t["cloud"][3]}},
            },
            "error": t["errors"],
            "abort": t["abort"],
        },
        "entity": ent,
        "exceptions": {k: {"message": v} for k, v in t["exceptions"].items()},
        "services": {"run_program": {"name": sname, "description": sdesc,
            "fields": {k: {"name": n, "description": d} for k, (n, d) in fields.items()}}},
        "selector": {"program": {"options": names}},
    }

(CC / "translations").mkdir(exist_ok=True)
for lang in ("en", "de"):
    out = json.dumps(build(lang), indent=2, ensure_ascii=False) + "\n"
    (CC / "translations" / f"{lang}.json").write_text(out)
    if lang == "en":
        (CC / "strings.json").write_text(out)
print("ok")
