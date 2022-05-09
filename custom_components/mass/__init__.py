"""Music Assistant (music-assistant.github.io) integration."""
from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
from music_assistant import MusicAssistant
from music_assistant.models.errors import MusicAssistantError
from music_assistant.providers.filesystem import FileSystemProvider
from music_assistant.providers.qobuz import QobuzProvider
from music_assistant.providers.spotify import SpotifyProvider
from music_assistant.providers.tunein import TuneInProvider

from .const import (
    CONF_CREATE_MASS_PLAYERS,
    CONF_FILE_DIRECTORY,
    CONF_FILE_ENABLED,
    CONF_PLAYLISTS_DIRECTORY,
    CONF_QOBUZ_ENABLED,
    CONF_QOBUZ_PASSWORD,
    CONF_QOBUZ_USERNAME,
    CONF_SPOTIFY_ENABLED,
    CONF_SPOTIFY_PASSWORD,
    CONF_SPOTIFY_USERNAME,
    CONF_TUNEIN_ENABLED,
    CONF_TUNEIN_USERNAME,
    DOMAIN,
)
from .panel import async_register_panel
from .player_controls import async_register_player_controls
from .websockets import async_register_websockets

LOGGER = logging.getLogger(__name__)

PLATFORMS = ("media_player", "switch", "number")


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up from a config entry."""
    http_session = async_get_clientsession(hass, verify_ssl=False)
    # TODO: optionally use mysql if mysql is detected ?
    db_file = hass.config.path("music_assistant.db")
    mass = MusicAssistant(f"sqlite:///{db_file}", session=http_session)
    conf = entry.options
    try:
        await mass.setup()
        # register music providers
        if conf.get(CONF_SPOTIFY_ENABLED):
            await mass.music.register_provider(
                SpotifyProvider(
                    conf.get(CONF_SPOTIFY_USERNAME), conf.get(CONF_SPOTIFY_PASSWORD)
                )
            )
        if conf.get(CONF_QOBUZ_ENABLED):
            await mass.music.register_provider(
                QobuzProvider(
                    conf.get(CONF_QOBUZ_USERNAME), conf.get(CONF_QOBUZ_PASSWORD)
                )
            )
        if conf.get(CONF_TUNEIN_ENABLED):
            await mass.music.register_provider(
                TuneInProvider(conf.get(CONF_TUNEIN_USERNAME))
            )
        if conf.get(CONF_FILE_ENABLED):
            await mass.music.register_provider(
                FileSystemProvider(
                    # empty string --> None
                    conf.get(CONF_FILE_DIRECTORY),
                    conf.get(CONF_PLAYLISTS_DIRECTORY) or None,
                )
            )
    except MusicAssistantError as err:
        await mass.stop()
        LOGGER.exception(err)
        raise ConfigEntryNotReady from err
    except Exception as exc:  # pylint: disable=broad-except
        await mass.stop()
        raise exc

    hass.data[DOMAIN] = mass

    # initialize platforms
    if conf.get(CONF_CREATE_MASS_PLAYERS, True):
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # register hass players with mass
    hass.create_task(async_register_player_controls(hass, mass, entry))

    async def on_hass_stop(event: Event):
        """Handle an incoming stop event from Home Assistant."""
        await mass.stop()

    # setup event listeners, register their unsubscribe in the unload
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    # Websocket support and frontend (panel)
    async_register_websockets(hass)
    entry.async_on_unload(await async_register_panel(hass, entry.title))

    return True


async def _update_listener(hass: HomeAssistantType, entry: ConfigEntry) -> None:
    """Handle ConfigEntry options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistantType, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_remove_entry(hass: HomeAssistantType, entry: ConfigEntry) -> None:
    """Call when entry is about to be removed."""
    if mass := hass.data.pop(DOMAIN, None):
        await mass.stop()
    # remove the db file to allow users make a clean start
    # backup the db file just in case of user error
    db_file = hass.config.path("music_assistant.db")
    db_file_old = f"{db_file}.old"
    if os.path.isfile(db_file_old):
        os.remove(db_file_old)
    if os.path.isfile(db_file):
        os.rename(db_file, db_file_old)


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if mass := hass.data.pop(DOMAIN, None):
        await mass.stop()
    return unload_success
