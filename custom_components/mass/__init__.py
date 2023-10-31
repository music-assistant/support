"""Music Assistant (music-assistant.github.io) integration."""
from __future__ import annotations

import asyncio

import async_timeout
from homeassistant.components.hassio import AddonError, AddonManager, AddonState
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from music_assistant.client import MusicAssistantClient
from music_assistant.client.exceptions import CannotConnect, InvalidServerVersion
from music_assistant.common.models.errors import MusicAssistantError

from .addon import get_addon_manager
from .const import CONF_INTEGRATION_CREATED_ADDON, CONF_USE_ADDON, DOMAIN, LOGGER
from .helpers import MassEntryData
from .services import register_services

PLATFORMS = ("media_player",)

CONNECT_TIMEOUT = 10
LISTEN_READY_TIMEOUT = 30


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    # ruff: noqa: PLR0915
    if use_addon := entry.data.get(CONF_USE_ADDON):
        await _async_ensure_addon_running(hass, entry)

    http_session = async_get_clientsession(hass, verify_ssl=False)

    # handle case where user had old V1 mass installed
    if CONF_URL not in entry.data:
        async_create_issue(
            hass,
            DOMAIN,
            "prev_version",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            learn_more_url="https://github.com/music-assistant/hass-music-assistant/issues/1143",
            translation_key="prev_version",
        )
        raise ConfigEntryError("Invalid configuration (migrating from V1 is not possible)")

    mass_url = entry.data[CONF_URL]
    mass = MusicAssistantClient(mass_url, http_session)

    try:
        async with async_timeout.timeout(CONNECT_TIMEOUT):
            await mass.connect()
    except (CannotConnect, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to music assistant server {mass_url}"
        ) from err
    except InvalidServerVersion as err:
        if use_addon:
            addon_manager = _get_addon_manager(hass)
            addon_manager.async_schedule_update_addon(catch_error=True)
        else:
            async_create_issue(
                hass,
                DOMAIN,
                "invalid_server_version",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="invalid_server_version",
            )
        raise ConfigEntryNotReady(f"Invalid server version: {err}") from err
    except Exception as err:
        LOGGER.exception("Failed to connect to music assistant server", exc_info=err)
        raise ConfigEntryNotReady(
            f"Unknown error connecting to the Music Assistant server {mass_url}"
        ) from err

    async_delete_issue(hass, DOMAIN, "invalid_server_version")

    async def on_hass_stop(event: Event) -> None:  # noqa: ARG001
        """Handle incoming stop event from Home Assistant."""
        await mass.disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop))

    # launch the music assistant client listen task in the background
    # use the init_ready event to wait until initialization is done
    init_ready = asyncio.Event()
    listen_task = asyncio.create_task(_client_listen(hass, entry, mass, init_ready))

    try:
        async with async_timeout.timeout(LISTEN_READY_TIMEOUT):
            await init_ready.wait()
    except asyncio.TimeoutError as err:
        listen_task.cancel()
        raise ConfigEntryNotReady("Music Assistant client not ready") from err

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        register_services(hass)

    hass.data[DOMAIN][entry.entry_id] = MassEntryData(mass, listen_task)

    # initialize platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # If the listen task is already failed, we need to raise ConfigEntryNotReady
    if listen_task.done() and (listen_error := listen_task.exception()) is not None:
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await mass.disconnect()
        finally:
            raise ConfigEntryNotReady(listen_error) from listen_error

    # cleanup orphan devices/entities
    # TODO: uncomment once we can read player configs to determine if a player still exists
    # dev_reg = dr.async_get(hass)
    # stored_devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    # for device in stored_devices:
    #     for _, player_id in device.identifiers:
    #         if mass.players.get_player(player_id) is None:
    #             dev_reg.async_remove_device(device.id)
    return True


async def _client_listen(
    hass: HomeAssistant,
    entry: ConfigEntry,
    mass: MusicAssistantClient,
    init_ready: asyncio.Event,
) -> None:
    """Listen with the client."""
    try:
        await mass.start_listening(init_ready)
    except MusicAssistantError as err:
        if entry.state != ConfigEntryState.LOADED:
            raise
        LOGGER.error("Failed to listen: %s", err)
    except Exception as err:  # pylint: disable=broad-except
        # We need to guard against unknown exceptions to not crash this task.
        LOGGER.exception("Unexpected exception: %s", err)
        if entry.state != ConfigEntryState.LOADED:
            raise

    if not hass.is_stopping:
        LOGGER.debug("Disconnected from server. Reloading integration")
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        mass_entry_data: MassEntryData = hass.data[DOMAIN].pop(entry.entry_id)
        mass_entry_data.listen_task.cancel()
        await mass_entry_data.mass.disconnect()

    if entry.data.get(CONF_USE_ADDON) and entry.disabled_by:
        addon_manager: AddonManager = get_addon_manager(hass)
        LOGGER.debug("Stopping Music Assistant Server add-on")
        try:
            await addon_manager.async_stop_addon()
        except AddonError as err:
            LOGGER.error("Failed to stop the Music Assistant Server add-on: %s", err)
            return False

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Call when entry is about to be removed."""
    if not entry.data.get(CONF_INTEGRATION_CREATED_ADDON):
        return

    addon_manager: AddonManager = get_addon_manager(hass)
    try:
        await addon_manager.async_stop_addon()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_create_backup()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_uninstall_addon()
    except AddonError as err:
        LOGGER.error(err)


async def async_remove_config_entry_device(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,  # noqa: ARG001
    device_entry: dr.DeviceEntry,  # noqa: ARG001
) -> bool:
    """Remove a config entry from a device."""
    return True


async def _async_ensure_addon_running(
    hass: HomeAssistant, entry: ConfigEntry  # noqa: ARG001
) -> None:
    """Ensure that Music Assistant Server add-on is installed and running."""
    addon_manager = _get_addon_manager(hass)
    try:
        addon_info = await addon_manager.async_get_addon_info()
    except AddonError as err:
        raise ConfigEntryNotReady(err) from err

    addon_state = addon_info.state

    if addon_state == AddonState.NOT_INSTALLED:
        addon_manager.async_schedule_install_setup_addon(
            addon_info.options,
            catch_error=True,
        )
        raise ConfigEntryNotReady

    if addon_state == AddonState.NOT_RUNNING:
        addon_manager.async_schedule_start_addon(catch_error=True)
        raise ConfigEntryNotReady


@callback
def _get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Ensure that Music Assistant Server add-on is updated and running.

    May only be used as part of async_setup_entry above.
    """
    addon_manager: AddonManager = get_addon_manager(hass)
    if addon_manager.task_in_progress():
        raise ConfigEntryNotReady
    return addon_manager
