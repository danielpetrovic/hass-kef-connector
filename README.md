# 🏠🔉 KEF Connector

A Home Assistant integration for KEF speakers with **complete feature parity** with the KEF Connect app.

## ✨ Complete W2 Platform Support

KEF Connector provides **comprehensive local control** for all KEF W2 Platform speakers:
- **LSX II** - Compact bookshelf speakers
- **LSX II LT** - Compact bookshelf (without analogue input)
- **LS50 Wireless II** - Premium bookshelf speakers
- **LS60 Wireless** - Floorstanding speakers
- **XIO Soundbar** - 5.1.2 soundbar with Dolby Atmos

### 🎯 Full API Coverage

Built on [pykefcontrol](https://github.com/N0ciple/pykefcontrol) with **100% API discovery** (209 endpoints):
- ✅ **188 implemented methods** - Complete control of all speaker features
- ✅ **Full DSP/EQ control** - 36 methods for audio customization
- ✅ **Advanced features** - Calibration, firmware updates, network diagnostics, alarms/timers
- ✅ **XIO-specific** - Sound profiles, room calibration, BLE firmware
- ✅ **Profile management** - Save, load, and share custom EQ presets
- ✅ **Bluetooth & Multiroom** - Device management, speaker grouping
- ✅ **No cloud dependency** - 100% local control via HTTP API  

---

## 📦 Installation

This custom component is available via [HACS](https://hacs.xyz).  
Search for **KEF Connector** in HACS and click **Download**. Restart Home Assistant to complete installation.

**Manual installation**  
Copy the [`kef_connector`](custom_components/kef_connector) folder into your Home Assistant `config/custom_components` directory. Restart Home Assistant to activate the integration.

---

## ⚙️ Configuration

KEF Connector uses **Config Flow** and is configured entirely through the **Home Assistant UI**.
**YAML configuration is no longer supported.**

You can add the integration manually or wait for it to be discovered.

### Auto Discovery
When your KEF speaker is discovered via Google Cast or AirPlay:
- **Name**, **IP Address** and **Speaker Model** are automatically filled in.
- You can review and adjust parameters before completing setup.

### Manual Setup
If your speaker isn’t discovered automatically, you can add it manually via the Integrations page.  
You’ll be prompted to enter:

| Field                     | Description                                                                 |
|--------------------------|-----------------------------------------------------------------------------|
| **IP Address**            | IP of your KEF speaker (e.g. `192.168.1.42`)                                |
| **Speaker Model**         | Choose from LSX II, LSX II LT, LS50 Wireless II, LS60 Wireless, or XIO      |
| **Scan Interval**         | How often to poll the speaker when online (5–300 seconds)                   |
| **Offline Retry Interval**| How often to check if an offline speaker is back online (30–600 seconds)    |
| **Volume Step**           | Volume change per up/down command (0.01–0.10)                               |
| **Maximum Volume**        | Safety limit for volume (0.1–1.0)                                           |

All these settings can be changed later from the **Integration settings page**.

---

## 🔁 Migrating from YAML

If you previously configured KEF Connector via `configuration.yaml`:
- Remove any `kef_connector` entries from your YAML file.
- Install or enable the integration via the UI:  
  **Settings → Devices & Services → Add Integration → KEF Connector**
- Recreate your previous settings during setup.  
  All parameters are editable later from the Integration page — no restart required.

---

## 🎛️ Features

This integration exposes comprehensive control through Home Assistant:

### Media Player Entity
- **Playback control** - Play, pause, next, previous track
- **Volume control** - Full volume management with safety limits
- **Source selection** - WiFi, Bluetooth, Optical, USB, Analogue, TV/HDMI
- **Sound modes** - Save and load custom EQ profiles
- **Media information** - Track title, artist, album, cover art

### Additional Entities
- **Sensors** - Speaker state, firmware version, media info, network status
- **Number controls** - Volume, bass, treble, balance, subwoofer gain
- **Select controls** - Source selection, sound profiles (XIO), standby modes
- **Switches** - Power, mute, feature toggles
- **Buttons** - Firmware check/install, profile management
- **Update entity** - Firmware update tracking and progress

### Advanced Controls
- **DSP/EQ settings** - Complete audio customization (36 methods)
  - Desk mode, wall mode, bass extension, treble, balance
  - Phase correction, high-pass filter, audio polarity
- **Subwoofer control** - Gain, preset, crossover, polarity, KW1 wireless
- **XIO soundbar features** - Sound profiles, room calibration, wall mount detection
- **Network diagnostics** - Internet ping, stability check, speed tests
- **Profile management** - Save, load, share custom EQ presets
- **Firmware updates** - Check, install, and monitor updates

For a complete feature list, see [pykefcontrol documentation](https://github.com/N0ciple/pykefcontrol#readme).

---

## 📚 Documentation & Support

- [KEF Connector GitHub](https://github.com/N0ciple/hass-kef-connector)
- [Issue Tracker](https://github.com/N0ciple/hass-kef-connector/issues)
- [pykefcontrol Library](https://github.com/N0ciple/pykefcontrol) - Python library with 100% API coverage
- [CLAUDE.md](CLAUDE.md) - Detailed technical documentation for developers and AI assistants
