"""Constants for the KEF Connector integration."""
from __future__ import annotations

from typing import Final

# Domain
DOMAIN: Final = "kef_connector"

# Configuration keys
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_OFFLINE_RETRY_INTERVAL: Final = "offline_retry_interval"
CONF_SPEAKER_MODEL: Final = "speaker_model"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 10  # seconds
DEFAULT_OFFLINE_RETRY_INTERVAL: Final = 60  # seconds
DEFAULT_SPEAKER_MODEL: Final = "LSX2"
DEFAULT_FAILURE_THRESHOLD: Final = 3  # consecutive failures before marking offline

# Validation ranges
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 300
MIN_OFFLINE_RETRY_INTERVAL: Final = 30
MAX_OFFLINE_RETRY_INTERVAL: Final = 600

# Speaker models and their available sources
SOURCES: Final = {
    "LSX2": ["wifi", "bluetooth", "tv", "optical", "analog", "usb"],
    "LSX2LT": ["wifi", "bluetooth", "tv", "optical", "usb"],
    "LS50W2": ["wifi", "bluetooth", "tv", "optical", "coaxial", "analog"],
    "LS60": ["wifi", "bluetooth", "tv", "optical", "coaxial", "analog"],
    "XIO": ["wifi", "bluetooth", "tv", "optical"],
}

# Model-specific feature flags
# Note: subwoofer_stereo removed - API field exists but has no effect
MODEL_FEATURES: Final = {
    "LSX2": {
        "subwoofer": True,
        "sound_profile": False,
        "calibration": False,
        "top_panel_led": False,
        "front_led": False,  # API exists but no visible effect on any model
        "stereo_pair": True,
        "cable_mode": True,  # Supports wired/wireless inter-speaker link
        "desk_mode": True,  # Bookshelf speaker
        "wall_mode": True,  # Bookshelf speaker
    },
    "LSX2LT": {
        "subwoofer": True,
        "sound_profile": False,
        "calibration": False,
        "top_panel_led": False,
        "front_led": False,  # No illuminated logo on LT model
        "stereo_pair": True,
        "cable_mode": False,  # USB-C only - no wireless option
        "desk_mode": True,  # Bookshelf speaker
        "wall_mode": True,  # Bookshelf speaker
    },
    "LS50W2": {
        "subwoofer": True,
        "sound_profile": False,
        "calibration": False,
        "top_panel_led": False,
        "front_led": False,  # API exists but no visible effect on any model
        "stereo_pair": True,
        "cable_mode": True,  # Supports wired/wireless inter-speaker link
        "desk_mode": True,  # Bookshelf speaker
        "wall_mode": True,  # Bookshelf speaker
    },
    "LS60": {
        "subwoofer": True,
        "sound_profile": False,
        "calibration": False,
        "top_panel_led": False,
        "front_led": False,  # API exists but no visible effect on any model
        "stereo_pair": True,
        "cable_mode": True,  # Supports wired/wireless inter-speaker link
        "desk_mode": False,  # Floorstanding speaker - no desk mode
        "wall_mode": False,  # Floorstanding speaker - no wall mode
    },
    "XIO": {
        "subwoofer": True,
        "sound_profile": True,
        "calibration": True,
        "top_panel_led": True,
        "front_led": False,  # API exists but no visible effect on any model
        "stereo_pair": False,
        "cable_mode": False,  # Soundbar - no external speaker pair
        "desk_mode": False,  # Soundbar - no desk mode
        "wall_mode": False,  # Soundbar - has wall_mounted instead
    },
}

# Bass extension modes (ordered: less -> standard -> extra)
BASS_EXTENSION_MODES: Final = ["less", "standard", "extra"]

# Audio polarity options
AUDIO_POLARITY_OPTIONS: Final = ["normal", "inverted"]

# Subwoofer presets (must match pykefcontrol SUBWOOFER_PRESETS)
SUBWOOFER_PRESETS: Final = [
    "custom",
    "kc62",
    "kf92",
    "kube8b",
    "kube10b",
    "kube12b",
    "kube15",
    "t2",
]

# Sound profiles (XIO only)
SOUND_PROFILES: Final = ["default", "music", "movie", "night", "dialogue", "direct"]

# Standby modes
STANDBY_MODES: Final = {
    "standby_20mins": "20 minutes",
    "standby_30mins": "30 minutes",
    "standby_60mins": "60 minutes",
    "standby_none": "Never",
}

# Cable modes
CABLE_MODES: Final = ["wired", "wireless"]

# Master channel options
MASTER_CHANNELS: Final = ["left", "right"]

# Wake source options (which input can wake speaker from standby)
# Only physical inputs with signal detection - WiFi cannot wake speaker
WAKE_SOURCE_OPTIONS: Final = {
    "LSX2": ["wakeup_default", "bluetooth", "tv", "optical", "analog", "usb"],
    "LSX2LT": ["wakeup_default", "bluetooth", "tv", "optical", "usb"],
    "LS50W2": ["wakeup_default", "bluetooth", "tv", "optical", "coaxial", "analog"],
    "LS60": ["wakeup_default", "bluetooth", "tv", "optical", "coaxial", "analog"],
    "XIO": ["wakeup_default", "bluetooth", "tv", "optical"],
}

# KEF speaker model prefixes for zeroconf filtering
# Order matters: check more specific patterns first (LSX-II-LT- before LSX-II-)
KEF_ZEROCONF_PREFIXES: Final = [
    "LSX-II-LT-",      # LSX2LT model
    "LSX-II-",         # LSX2 model (check after LSX-II-LT-)
    "LS50-WIRELESS-II-",  # LS50W2 model
    "LS60-",           # LS60 model
    "XIO-",            # XIO model
]

# Speaker model display names
MODEL_NAMES: Final = {
    "LSX2": "LSX II",
    "LSX2LT": "LSX II LT",
    "LS50W2": "LS50 Wireless II",
    "LS60": "LS60 Wireless",
    "XIO": "XIO",
}

# Unique ID prefix for entity registry
UNIQUE_ID_PREFIX: Final = "KEF_SPEAKER"

# Zeroconf discovery
ZEROCONF_TYPE: Final = "_http._tcp.local."

# Device info
MANUFACTURER: Final = "KEF"
