"""DataUpdateCoordinator for KEF Connector."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from .pykefcontrol.kef_connector import KefAsyncConnector

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class KefCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching KEF speaker data."""

    def __init__(
        self,
        hass: HomeAssistant,
        speaker: KefAsyncConnector,
        name: str,
        scan_interval: int,
        offline_retry_interval: int,
        speaker_model: str = "LSX2",
    ) -> None:
        """Initialize the coordinator."""
        self.speaker = speaker
        self.name = name
        self.speaker_model = speaker_model.upper()
        self.normal_interval = timedelta(seconds=scan_interval)
        self.offline_interval = timedelta(seconds=offline_retry_interval)
        self._is_offline = False
        self._error_logged = False
        self._consecutive_failures = 0
        self._failure_threshold = 3  # Number of consecutive failures before switching to offline mode
        self._last_successful_data: dict[str, Any] | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=self.normal_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from KEF speaker.

        Returns dict with all speaker state information.
        Raises UpdateFailed if speaker is unreachable.
        """
        try:
            # Get all speaker state in one update cycle
            volume = await self.speaker.volume
            status = await self.speaker.status
            source = await self.speaker.source
            is_playing = (
                await self.speaker.is_playing
                if source in ["wifi", "bluetooth"]
                else False
            )

            # Get media info (may return empty dict if nothing playing)
            media_info = await self.speaker.get_song_information()

            # Get song playback info if playing
            song_length = None
            song_position = None
            if is_playing:
                song_length = await self.speaker.song_length
                song_position = await self.speaker.song_status

            # Get codec info (available on models with HDMI/TV inputs)
            codec_info = await self.speaker.get_audio_codec_information()

            # Get WiFi signal strength
            wifi_info = await self.speaker.get_wifi_information()

            # Get EQ profile (contains all DSP settings)
            eq_profile = await self.speaker.get_eq_profile()
            eq_data = eq_profile.get("kefEqProfileV2", {}) if eq_profile else {}

            # Get hardware settings
            front_led = await self.speaker.get_front_led()
            standby_led = await self.speaker.get_standby_led()
            standby_mode = await self.speaker.get_standby_mode()
            top_panel_enabled = await self.speaker.get_top_panel_enabled()
            top_panel_led = await self.speaker.get_top_panel_led()
            startup_tone = await self.speaker.get_startup_tone()
            cable_mode = await self.speaker.get_cable_mode()
            master_channel = await self.speaker.get_master_channel()
            auto_switch_hdmi = await self.speaker.get_auto_switch_hdmi()
            wake_source = await self.speaker.get_wake_source()

            # Get subwoofer wake on startup settings
            subwoofer_wake_on_startup = await self.speaker.get_subwoofer_wake_on_startup()
            kw1_wake_on_startup = await self.speaker.get_kw1_wake_on_startup()

            # Get firmware version
            firmware_version = await self.speaker.get_firmware_version()

            # Get speaker volume settings (max volume, step)
            try:
                volume_settings = await self.speaker.get_volume_settings()
            except Exception:
                volume_settings = {}

            # Get calibration status (XIO only)
            calibration_status = None
            calibration_result = None
            ble_firmware_version = None
            ble_firmware_status = None
            if self.speaker_model == "XIO":
                try:
                    calibration_status = await self.speaker.get_calibration_status()
                    calibration_result = await self.speaker.get_calibration_result()
                except Exception:
                    pass
                try:
                    # Note: ble_firmware_version returns the server version, not the installed version
                    # The KEF API doesn't expose the actual installed version on the KW2 module
                    # We only fetch status for update detection
                    ble_firmware_status = await self.speaker.get_ble_firmware_status()
                except Exception:
                    pass

            # Get MAC address for device registry
            mac_address = await self.speaker.mac_address

            # Speaker is online - reset offline state
            if self._is_offline:
                _LOGGER.info(
                    "KEF speaker '%s' is back online",
                    self.name,
                )
                self._is_offline = False
                self._error_logged = False
                # Return to normal polling interval
                self.update_interval = self.normal_interval

            # Reset failure counter on successful update
            self._consecutive_failures = 0

            # Cache successful data for use during transient failures
            data = {
                "volume": volume,
                "status": status,
                "source": source,
                "is_playing": is_playing,
                "media_title": media_info.get("title"),
                "media_artist": media_info.get("artist"),
                "media_album": media_info.get("album"),
                "media_album_artist": media_info.get("album_artist"),
                "media_image_url": media_info.get("cover_url"),
                "song_length": song_length,
                "song_position": song_position,
                # Codec information (may be None on some sources/models)
                "audio_codec": codec_info.get("codec"),
                "audio_codec_raw": codec_info.get("codec"),
                "sample_rate": codec_info.get("sampleFrequency"),
                "stream_channels": codec_info.get("streamChannels"),
                "audio_channels": codec_info.get("nrAudioChannels"),
                "streaming_service": codec_info.get("serviceID"),
                # WiFi information
                "wifi_signal_strength": wifi_info.get("signalLevel"),
                "wifi_ssid": wifi_info.get("ssid"),
                "wifi_frequency": wifi_info.get("frequency"),
                "wifi_bssid": wifi_info.get("bssid"),
                # EQ profile data (DSP settings)
                "eq_profile": eq_profile,
                "eq_data": eq_data,
                "eq_profile_name": eq_data.get("profileName"),
                "eq_profile_id": eq_data.get("profileId"),
                # Individual DSP settings from EQ profile
                "treble": eq_data.get("trebleAmount"),
                "balance": eq_data.get("balance"),
                "desk_mode_enabled": eq_data.get("deskMode"),
                "desk_mode_db": eq_data.get("deskModeSetting"),
                "wall_mode_enabled": eq_data.get("wallMode"),
                "wall_mode_db": eq_data.get("wallModeSetting"),
                "phase_correction": eq_data.get("phaseCorrection"),
                "bass_extension": eq_data.get("bassExtension"),
                "high_pass_enabled": eq_data.get("highPassMode"),
                "high_pass_freq": eq_data.get("highPassModeFreq"),
                "audio_polarity": eq_data.get("audioPolarity"),
                # Subwoofer settings from EQ profile
                "subwoofer_enabled": eq_data.get("subwooferCount", 0) > 0 or eq_data.get("subwooferOut", False),
                "subwoofer_gain": eq_data.get("subwooferGain"),
                "subwoofer_polarity": eq_data.get("subwooferPolarity"),
                "subwoofer_preset": eq_data.get("subwooferPreset"),
                "subwoofer_lowpass": eq_data.get("subOutLPFreq"),
                "subwoofer_stereo": eq_data.get("subwooferStereo"),
                # Wireless subwoofer adapter settings
                "kw1_enabled": eq_data.get("isKW1", False),
                "subwoofer_count": eq_data.get("subwooferCount", 1),
                # XIO-specific from EQ profile
                "sound_profile": eq_data.get("soundProfile"),
                "dialogue_mode": eq_data.get("dialogueMode", False),
                "wall_mounted": eq_data.get("wallMounted"),
                # Hardware settings
                "front_led": front_led,
                "standby_led": standby_led,
                "standby_mode": standby_mode,
                "top_panel_enabled": top_panel_enabled,
                "top_panel_led": top_panel_led,
                "startup_tone": startup_tone,
                "cable_mode": cable_mode,
                "master_channel": master_channel,
                "auto_switch_hdmi": auto_switch_hdmi,
                "wake_source": wake_source,
                # Subwoofer wake on startup settings
                "subwoofer_wake_on_startup": subwoofer_wake_on_startup,
                "kw1_wake_on_startup": kw1_wake_on_startup,
                # Device info
                "firmware_version": firmware_version,
                "mac_address": mac_address,
                # Speaker volume settings
                "speaker_max_volume": volume_settings.get("max_volume", 100),
                "speaker_volume_step": volume_settings.get("step", 1),
                # Calibration data (XIO only)
                "calibration_status": calibration_status,
                "calibration_result": calibration_result,
                # BLE firmware data (XIO KW2 module only)
                "ble_firmware_version": ble_firmware_version,
                "ble_firmware_status": ble_firmware_status,
            }
            self._last_successful_data = data
            return data

        except Exception as err:
            # Increment consecutive failure counter
            self._consecutive_failures += 1

            # Check if we've reached the threshold for marking as offline
            if self._consecutive_failures >= self._failure_threshold:
                # Now consider the speaker truly offline
                if not self._is_offline:
                    # First time marking as offline - log warning and switch to slow polling
                    _LOGGER.warning(
                        "KEF speaker '%s' is offline or unreachable after %d consecutive failures: %s. "
                        "Will retry every %d seconds until it comes back online",
                        self.name,
                        self._consecutive_failures,
                        err,
                        self.offline_interval.total_seconds(),
                    )
                    self._is_offline = True
                    self._error_logged = True
                    # Switch to slower retry interval
                    self.update_interval = self.offline_interval

                # Raise UpdateFailed to mark entity as unavailable
                raise UpdateFailed(f"Error communicating with KEF speaker: {err}") from err

            else:
                # Still within tolerance - log as debug and return cached data
                _LOGGER.debug(
                    "KEF speaker '%s' connection attempt %d/%d failed: %s. "
                    "Using cached data and retrying at normal interval",
                    self.name,
                    self._consecutive_failures,
                    self._failure_threshold,
                    err,
                )

                # If we have cached data, return it to keep entity available
                if self._last_successful_data is not None:
                    return self._last_successful_data

                # No cached data yet (first poll ever failed) - have to mark unavailable
                raise UpdateFailed(f"Initial connection failed (attempt {self._consecutive_failures}/{self._failure_threshold}): {err}") from err

    def update_intervals(self, scan_interval: int, offline_retry_interval: int) -> None:
        """Update the polling intervals from options."""
        self.normal_interval = timedelta(seconds=scan_interval)
        self.offline_interval = timedelta(seconds=offline_retry_interval)

        # Update current interval based on current state
        if self._is_offline:
            self.update_interval = self.offline_interval
        else:
            self.update_interval = self.normal_interval

    def async_set_updated_data_optimistic(self, key: str, value: Any) -> None:
        """Optimistically update a single data key and notify listeners.

        Use this after successfully sending a command to the speaker to
        immediately update the UI without waiting for the next poll cycle.

        Args:
            key: The data key to update (e.g., "treble", "balance", "front_led")
            value: The new value
        """
        if self.data is not None:
            self.data[key] = value
            # Also update cached data
            if self._last_successful_data is not None:
                self._last_successful_data[key] = value
            # Notify all listeners (entities) that data has changed
            self.async_set_updated_data(self.data)
