# KEF Connector - Home Assistant Integration - Context for AI Assistants

A Home Assistant custom component for KEF wireless speakers with W2 platform.

## Project Overview

- **Type:** Home Assistant Custom Component
- **Integration Domain:** `kef_connector`
- **Integration Type:** Device (local polling)
- **Version:** 1.0.0
- **Configuration:** Config Flow (UI-based, YAML no longer supported)
- **Discovery:** Automatic via Zeroconf (AirPlay & Google Cast)

## Supported Models

All KEF W2 Platform speakers:
- LSX II
- LSX II LT
- LS50 Wireless II
- LS60 Wireless
- XIO Soundbar

## Repository Structure

```
hass-kef-connector/
├── custom_components/kef_connector/
│   ├── __init__.py              # Integration setup & entry management
│   ├── config_flow.py           # UI configuration flow
│   ├── const.py                 # Constants and defaults
│   ├── coordinator.py           # Data update coordinator
│   ├── entity.py                # Base entity class
│   ├── manifest.json            # Integration metadata
│   ├── services.yaml            # Service definitions
│   ├── translations/en.json     # English translations
│   ├── media_player.py          # Media player platform
│   ├── button.py                # Button entities
│   ├── number.py                # Number entities
│   ├── select.py                # Select entities
│   ├── sensor.py                # Sensor entities
│   ├── switch.py                # Switch entities
│   ├── update.py                # Update entities
│   └── pykefcontrol/            # Embedded library
│       ├── __init__.py
│       ├── kef_connector.py
│       └── profile_manager.py
├── hacs.json                    # HACS integration metadata
└── README.md                    # User documentation
```

## Architecture

### Integration Flow
1. **Discovery:** Zeroconf finds KEF speakers via AirPlay/Google Cast
2. **Config Flow:** User configures via UI (IP, model, scan intervals, volume settings)
3. **Coordinator:** Manages polling and data updates
4. **Platforms:** Creates entities (media_player, sensors, buttons, etc.)

### Configuration Options

- **IP Address:** Speaker IP (e.g., 192.168.1.42)
- **Speaker Model:** LSX II, LSX II LT, LS50 Wireless II, LS60, XIO
- **Scan Interval:** Polling when online (5-300 seconds)
- **Offline Retry Interval:** Check offline speakers (30-600 seconds)
- **Volume Step:** Volume change increment (0.01-0.10)
- **Maximum Volume:** Safety limit (0.1-1.0)

All settings are reconfigurable via UI without restart.

### Embedded Library

The integration embeds `pykefcontrol` directly in `custom_components/kef_connector/pykefcontrol/` instead of using it as a requirement. This ensures:
- Version compatibility
- No external dependency issues
- Simpler HACS installation

**Note:** When updating pykefcontrol features, copy the updated files from the pykefcontrol repo.

## Platform Entities

### media_player
- Primary entity for speaker control
- Supports: power, volume, mute, source selection, playback control
- Features: sound_mode (EQ profiles), media info, state tracking

### sensor
- Speaker state sensors
- Media information (title, artist, album)
- Firmware version
- Network status

### button
- Firmware check
- Firmware install
- Profile save/load actions

### number
- Volume control
- EQ adjustments (bass, treble, balance)
- Subwoofer gain

### select
- Source selection
- Sound profiles (XIO only)
- Standby modes

### switch
- Power control
- Mute toggle
- Feature enables/disables

### update
- Firmware update tracking
- Update progress monitoring

## Key Files

### coordinator.py
- **Purpose:** Central data coordinator using `DataUpdateCoordinator`
- **Polling:** Async polling with configurable intervals
- **Error Handling:** Manages unavailable states and reconnection
- **Usage:** All platforms subscribe to coordinator updates

**Patterns:**

```python
async def _async_update_data(self):
    """Fetch data from speaker."""
    try:
        # Use pykefcontrol KefAsyncConnector
        data = await self.speaker.get_status()
        return data
    except Exception as err:
        raise UpdateFailed(f"Error communicating: {err}")
```

### config_flow.py
- **Discovery Flow:** Auto-fills IP, name, model from Zeroconf
- **Manual Flow:** User entry with validation
- **Options Flow:** Reconfigure settings without removing device
- **Validation:** IP connectivity check before accepting

### entity.py
- **Base Class:** `KefConnectorEntity(CoordinatorEntity)`
- **Provides:** device_info, unique_id, availability
- **Device Info:** Model, manufacturer, firmware, identifiers

### Platform Files (media_player.py, sensor.py, etc.)
- **Setup:** Async platform setup via `async_setup_entry`
- **Entities:** Create entity classes inheriting from base
- **State:** Pull from `coordinator.data`
- **Actions:** Use `coordinator.speaker` (pykefcontrol instance)

## Development Patterns

### Adding a New Entity

1. **Create entity class** in appropriate platform file:

```python
class KefSpeakerSensor(KefConnectorEntity, SensorEntity):
    """KEF Speaker sensor entity."""

    def __init__(self, coordinator, entity_description):
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.unique_id}_{entity_description.key}"

    @property
    def native_value(self):
        """Return the sensor value."""
        return self.coordinator.data.get(self.entity_description.key)
```

2. **Add to platform setup:**

```python
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        KefSpeakerSensor(coordinator, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)
```

### Using pykefcontrol

Access via coordinator:

```python
# In entity methods
await self.coordinator.speaker.set_volume(50)
volume = await self.coordinator.speaker.volume
profile = await self.coordinator.speaker.get_eq_profile()
```

### Profile Management

Uses HA Storage API (not pykefcontrol's ProfileManager):

```python
from homeassistant.helpers.storage import Store

STORAGE_VERSION = 1
STORAGE_KEY = "kef_connector.profiles"

# Store profiles per speaker
store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{speaker_mac}")
```

### Error Handling

```python
from homeassistant.exceptions import HomeAssistantError

try:
    await self.coordinator.speaker.some_action()
except Exception as err:
    raise HomeAssistantError(f"Failed to perform action: {err}")
```

## Coordinator Update Logic

The coordinator handles two polling intervals:

1. **Online Interval:** Fast polling when speaker is available (default: 30s)
2. **Offline Interval:** Slow polling when speaker is unavailable (default: 60s)

This reduces network traffic when speakers are off.

## Zeroconf Discovery

The integration discovers KEF speakers via:
- `_airplay._tcp.local.` (AirPlay service)
- `_googlecast._tcp.local.` (Google Cast service)

Discovery auto-fills:
- Speaker name
- IP address
- Model (inferred from service info)

## Services

Custom services defined in `services.yaml`:
- Profile save/load/delete
- EQ preset application
- Firmware management
- Advanced speaker controls

## Translation

All user-facing strings are in `translations/en.json`:
- Config flow steps
- Entity names
- Error messages
- Service descriptions

## Testing Locally

1. Copy integration to HA config:

```bash
cp -r custom_components/kef_connector /config/custom_components/
```

2. Restart Home Assistant

3. Add via UI: **Settings → Devices & Services → Add Integration → KEF Connector**

4. Monitor logs:

```bash
tail -f /config/home-assistant.log | grep kef_connector
```

## Debugging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.kef_connector: debug
```

## Code Style

- Follow Home Assistant development guidelines
- Use async/await for all I/O operations
- Type hints on all methods
- Docstrings for classes and complex methods
- Use HA helpers (storage, entity platform, etc.)

## Dependencies

- **Home Assistant Core:** 2024.8.0+ (minimum for blueprint features)
- **pykefcontrol:** Embedded in integration (no external requirement)
- **Python:** 3.11+ (HA requirement)

## HACS Integration

Configured in `hacs.json`:

```json
{
  "name": "KEF Connector",
  "render_readme": true,
  "domains": ["media_player", "sensor", "button", "number", "select", "switch", "update"]
}
```

## Related Repositories

- **pykefcontrol:** https://github.com/N0ciple/pykefcontrol (Python library)
- **Original Repo:** https://github.com/N0ciple/hass-kef-connector

## Codeowners

- @n0ciple (Original author)
- @danielpetrovic (Maintainer)

## Known Patterns

### Coordinator Data Structure

```python
{
    "status": "powerOn" | "standby",
    "source": "wifi" | "bluetooth" | "optical" | "tv" | ...,
    "volume": 0-100,
    "mute": True | False,
    "is_playing": True | False,
    "song_info": {
        "title": str,
        "artist": str,
        "album": str,
        "cover_url": str
    },
    "firmware_version": str,
    "speaker_model": str,
    ...
}
```

### Entity Unique IDs
Format: `{mac_address}_{entity_type}_{entity_key}`
Example: `ab_cd_ef_12_34_56_sensor_volume`

### Device Identifiers
Uses MAC address for consistent device identification across HA restarts.

## Recent Bug Fixes (2025-12-25)

### 1. Number Entity Step Sizes
**Files:** `number.py`

**Treble Step Size** (Line 42)
- **Old:** `native_step=0.5` (allowed 0.5 dB increments)
- **New:** `native_step=0.25` (matches KEF Connect app)
- **Effect:** Treble slider now moves in 0.25 dB steps (-3.0, -2.75, -2.5, ..., +3.0)

**Subwoofer Gain Step Size** (Line 103)
- **Old:** `native_step=0.5` (allowed decimal values like 5.5 dB)
- **New:** `native_step=1.0` (integer steps only)
- **Effect:** Subwoofer gain slider now moves in 1 dB steps (-10, -9, ..., +10)

**Status:** ✅ Fixed - UI now prevents invalid values at the slider level

### 2. Subwoofer Preset Refresh
**Files:** `select.py` (Lines 186-195)

**Issue:** When changing subwoofer preset (e.g., kube12b → kc62), only the preset name would update. The KEF speaker also changes gain, low-pass, and high-pass values to match the preset, but these didn't refresh in HA.

**Fix:** Added special handling for `subwoofer_preset` selector:
```python
if self.entity_description.key == "subwoofer_preset":
    # Force full refresh to get all updated subwoofer settings
    await self.coordinator.async_request_refresh()
```

**Effect:** Now when you change preset, all related settings (gain, crossover frequencies) update immediately.

**Status:** ⏳ Pending testing

### 3. XIO Calibration Display
**Files:** Inherited from pykefcontrol library update

**Issue:** Calibration sensor showed "Not calibrated" when calibrated, adjustment showed 0 dB instead of -5 dB.

**Fix:** Updated `pykefcontrol/kef_connector.py` to correctly parse API responses:
- Calibration status: Parse nested `kefDspCalibrationStatus` object
- Calibration result: Read `double_` type instead of `i32_`

**Effect:** Room Calibration sensor now shows:
- State: "Calibrated" (was "Not calibrated")
- Attribute `adjustment_db`: -5 (was 0)

**Status:** ✅ Verified working on XIO soundbar
