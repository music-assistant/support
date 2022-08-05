"""Music Assistant (music-assistant.github.io) integration."""
from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import socket
from urllib.parse import urlparse

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.json import json_loads
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.start import async_at_start
from music_assistant import MusicAssistant
from music_assistant.models.config import MassConfig, MusicProviderConfig
from music_assistant.models.enums import ProviderType
from music_assistant.models.errors import MusicAssistantError
from music_assistant.models.event import MassEvent

from .config_flow import hide_player_entities
from .const import (
    CONF_CREATE_MASS_PLAYERS,
    CONF_FILE_DIRECTORY,
    CONF_FILE_ENABLED,
    CONF_PLAYER_ENTITIES,
    CONF_QOBUZ_ENABLED,
    CONF_QOBUZ_PASSWORD,
    CONF_QOBUZ_USERNAME,
    CONF_SPOTIFY_ENABLED,
    CONF_SPOTIFY_PASSWORD,
    CONF_SPOTIFY_USERNAME,
    CONF_TUNEIN_ENABLED,
    CONF_TUNEIN_USERNAME,
    CONF_YTMUSIC_ENABLED,
    CONF_YTMUSIC_PASSWORD,
    CONF_YTMUSIC_USERNAME,
    DOMAIN,
    DOMAIN_EVENT,
)
from .panel import async_register_panel
from .player_controls import async_register_player_controls
from .services import register_services
from .websockets import async_register_websockets

LOGGER = logging.getLogger(__name__)

PLATFORMS = ("media_player", "switch", "number", "select")

MIN_HA_VERSION = "2022.8.0"
MAX_HA_VERSION = "2022.8.999"


async def read_manifest() -> dict:
    """Read manifest file."""

    def _read_manifest():
        manifest_path = (
            pathlib.Path(__file__).parent.resolve().joinpath("manifest.json")
        )
        return json_loads(manifest_path.read_text("utf-8"))

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _read_manifest)


def get_local_ip_from_internal_url(hass: HomeAssistant):
    """Get the stream ip address from the internal_url."""
    try:
        url = get_url(
            hass,
            allow_internal=True,
            allow_external=False,
            allow_cloud=False,
            allow_ip=True,
        )
    except NoURLAvailableError:
        LOGGER.warning(
            "Unable to retrieve the internal URL from Home Assistant, "
            "this may cause issues resolving the correct internal stream ip. "
            "Please set a valid internal url in the Home Assistant configuration"
        )
        return hass.config.api.local_ip
    parsed_uri = urlparse(url)

    if parsed_uri.netloc == "":
        return hass.config.api.local_ip

    try:
        return socket.gethostbyname(parsed_uri.netloc)
    except socket.gaierror:
        # url is set as ip instead of hostname
        return hass.config.api.local_ip


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up from a config entry."""
    http_session = async_get_clientsession(hass, verify_ssl=False)

    # compare version in manifest with HA version
    manifest = await read_manifest()
    ha_vers = AwesomeVersion(HA_VERSION, AwesomeVersionStrategy.SEMVER, True)
    req_ha_vers = AwesomeVersion(MIN_HA_VERSION, AwesomeVersionStrategy.SEMVER, True)
    max_ha_vers = AwesomeVersion(MAX_HA_VERSION, AwesomeVersionStrategy.SEMVER, True)
    # for now, just raise at mismatch of major/minor because in 99% of the cases
    # there are breaking changes between HA releases
    if ha_vers < req_ha_vers:
        raise ConfigEntryAuthFailed(
            "This version of Music Assistant is only compatible "
            f"with Home Assistant version {manifest['ha_version']} (or higher)."
        )
    if ha_vers > max_ha_vers:
        LOGGER.warning(
            "This version of Music Assistant is compatible "
            "with Home Assistant version %s, "
            "and you are running %s. You may run into compatibility issues. "
            "Please check if there's a newer (beta) version available of Music Assistant.",
            manifest["ha_version"],
            HA_VERSION,
        )

    # databases is really chatty with logging at info level
    logging.getLogger("databases").setLevel(logging.WARNING)
    logging.getLogger("music_assistant").setLevel(logging.getLogger(__name__).level)

    conf = entry.options

    # TODO: adjust config flow to support creating multiple provider entries
    providers = []

    if conf.get(CONF_SPOTIFY_ENABLED):
        providers.append(
            MusicProviderConfig(
                ProviderType.SPOTIFY,
                username=conf.get(CONF_SPOTIFY_USERNAME),
                password=conf.get(CONF_SPOTIFY_PASSWORD),
            )
        )

    if conf.get(CONF_QOBUZ_ENABLED):
        providers.append(
            MusicProviderConfig(
                ProviderType.QOBUZ,
                username=conf.get(CONF_QOBUZ_USERNAME),
                password=conf.get(CONF_QOBUZ_PASSWORD),
            )
        )

    if conf.get(CONF_TUNEIN_ENABLED):
        providers.append(
            MusicProviderConfig(
                ProviderType.TUNEIN,
                username=conf.get(CONF_TUNEIN_USERNAME),
            )
        )
    if conf.get(CONF_FILE_ENABLED) and conf.get(CONF_FILE_DIRECTORY):
        providers.append(
            MusicProviderConfig(
                ProviderType.FILESYSTEM_LOCAL,
                path=conf.get(CONF_FILE_DIRECTORY),
            )
        )
    if conf.get(CONF_YTMUSIC_ENABLED):
        providers.append(
            MusicProviderConfig(
                ProviderType.YTMUSIC,
                username=conf.get(CONF_YTMUSIC_USERNAME),
                password=conf.get(CONF_YTMUSIC_PASSWORD),
            )
        )

    db_file = hass.config.path("music_assistant.db")
    stream_ip = get_local_ip_from_internal_url(hass)
    mass_conf = MassConfig(
        database_url=f"sqlite:///{db_file}", providers=providers, stream_ip=stream_ip
    )

    mass = MusicAssistant(mass_conf, session=http_session)

    try:
        await mass.setup()
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
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def on_hass_start(*args, **kwargs):
        """Start sync actions when Home Assistant is started."""
        register_services(hass, mass)
        # register hass players with mass
        await async_register_player_controls(hass, mass, entry)
        # start and schedule sync (every 3 hours)
        await mass.music.start_sync(schedule=3)

    async def on_hass_stop(event: Event):
        """Handle an incoming stop event from Home Assistant."""
        await mass.stop()

    async def on_mass_event(event: MassEvent):
        """Handle an incoming event from Music Assistant."""
        # forward event to the HA eventbus
        if hasattr(event.data, "to_dict"):
            data = event.data.to_dict()
        else:
            data = event.data
        hass.bus.async_fire(
            DOMAIN_EVENT,
            {"type": event.type.value, "object_id": event.object_id, "data": data},
        )

    # setup event listeners, register their unsubscribe in the unload
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.async_on_unload(async_at_start(hass, on_hass_start))
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    entry.async_on_unload(mass.subscribe(on_mass_event))

    # Websocket support and frontend (panel)
    async_register_websockets(hass)
    entry.async_on_unload(await async_register_panel(hass, entry.title))

    # cleanup orphan devices/entities
    dev_reg = dr.async_get(hass)
    stored_devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    if CONF_PLAYER_ENTITIES in entry.options:
        for device in stored_devices:
            for _, player_id in device.identifiers:
                if player_id not in entry.options[CONF_PLAYER_ENTITIES]:
                    dev_reg.async_remove_device(device.id)
                elif not entry.options[CONF_CREATE_MASS_PLAYERS]:
                    dev_reg.async_remove_device(device.id)
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle ConfigEntry options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
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

    # unhide the player entities
    hide_player_entities(hass, entry.options.get(CONF_PLAYER_ENTITIES, []), False)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if entry.options.get(CONF_CREATE_MASS_PLAYERS, True):
        unload_success = await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS
        )
    else:
        unload_success = True
    if mass := hass.data.pop(DOMAIN, None):
        await mass.stop()
    return unload_success
