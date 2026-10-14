# Midea Washer (local)

Home Assistant custom integration that controls a Midea front-load washer (device
type 0xDB) entirely over the LAN, **including program selection**: the same
programs, temperatures, spin speeds and options as the SmartHome (MSmartHome) app.

Built and tested for the MF200W80WB-14AS (model code `38123704`, subtype `16697`,
`MFL80-U1403B/C14EW-EU`). Personal project; not affiliated with Midea.

## How it works

- Transport, V3 handshake and encryption: [midea-local](https://github.com/midea-lan/midea-local).
- Frames: `protocol.py`, a Python port of Midea's own codec `T_0000_DB_41.lua`.
  `tests/test_protocol_oracle.py` checks the port byte for byte against the
  original Lua when it is available locally.
- Programs and their allowed options: `models/16697.json`, generated from the
  app's per-model program file (`scripts/gen_model.py`).

The cloud is needed exactly once, to get the token/key for the V3 handshake.
After that, nothing leaves the LAN.

## Install (no HACS needed)

1. Copy `custom_components/midea_washer/` to `/config/custom_components/midea_washer/`.
2. Restart Home Assistant.
3. Settings → Devices & services → Add integration → "Midea Washer (local)".
4. Enter the washer's IP (give it a DHCP reservation). Then either fetch the
   key once with your SmartHome login (it isn't stored) or paste token + key.

If the washer is also set up in midea_ac_lan, remove it there. These
appliances usually accept only one LAN connection at a time.

## Entities

| Entity | Notes |
|---|---|
| Program (select) | 15 programs, names as in the app |
| Temperature / spin speed / water level (select) | choices follow the selected program |
| Pre-wash, extra rinse, turbo, mute end signal (switch) | unavailable when the program doesn't offer them |
| Power, child lock (switch) | power can only switch **off**; see below |
| Start, pause (button) | start applies the delayed-start value |
| Delayed start (number) | hours; only stored locally until start |
| Status, phase, remaining time, finish time, error code (sensor) | |
| Remote control enabled (binary sensor) | |

**Remote control must be enabled on the washer panel**, otherwise the machine
(like the app) refuses all commands. The binary sensor shows the state. The
washer clears it on every power-off, so it has to be enabled again each time.

**Switched off = off the network.** When the washer is off, its Wi-Fi module is
off too. It can therefore only be switched on at the panel, never from Home
Assistant. While it is unreachable, power and status show "off" and the other
entities are unavailable. The integration retries every 5 s, so it reconnects
within seconds of the washer being switched on. (Verified live 2026-10-14.)

Selecting a program or option sends it to the machine right away, as the app does.
The program can't change during a cycle; pre-wash and turbo can't change during a cycle or pause.

## Service `midea_washer.run_program`

Selects the program, applies the options and starts, all in one call. The washer must be
switched on at the panel with remote control enabled:

```yaml
action: midea_washer.run_program
target:
  entity_id: select.waschmaschine_programm
data:
  program: eco_40_60
  spin_speed: "1200"
  delay: 120   # minutes, optional
```

## Development

```sh
uv venv -p 3.14 .venv-ha
VIRTUAL_ENV=.venv-ha uv pip install pytest-homeassistant-custom-component midea-local==12.3.0 lupa
.venv-ha/bin/python -m pytest
```

The research scripts in `scripts/` (`fetch_cloud.py`, `fetch_model_json.py`,
`probe.py`, `luacodec.py`) reproduce the reverse engineering. Their inputs and
outputs live in the git-ignored `research/` folder.
