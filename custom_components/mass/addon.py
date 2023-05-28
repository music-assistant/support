"""Provide add-on management."""
from __future__ import annotations

from homeassistant.components.hassio import DOMAIN as HASSIO_DOMAIN
from homeassistant.components.hassio import AddonManager, HassIO
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import ADDON_REPOSITORY, ADDON_SLUG, DOMAIN, LOGGER

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass, LOGGER, "Music Assistant Server", ADDON_SLUG)


async def install_repository(hass: HomeAssistant) -> None:
    """Make sure that the MA repository is installed."""
    hassio: HassIO = hass.data[HASSIO_DOMAIN]
    command = "/store/repositories"
    payload = {"repository": ADDON_REPOSITORY}
    return await hassio.send_command(command, payload=payload, timeout=None)
