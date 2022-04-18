"""Host Music Assistant frontend in custom panel."""
import logging
import os

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_FOLDER = "frontend/dist"
PANEL_FILENAME = "mass.iife.js"
PANEL_URL = f"/panel_custom/{DOMAIN}"
PANEL_TITLE = DEFAULT_NAME
PANEL_ICON = "mdi:play"
PANEL_NAME = "music-assistant"


async def async_register_panel(hass: HomeAssistant):
    """Register custom panel."""
    root_dir = os.path.dirname(__file__)
    panel_dir = os.path.join(root_dir, PANEL_FOLDER)
    js_path = os.path.join(panel_dir, PANEL_FILENAME)

    hass.http.register_static_path(PANEL_URL, js_path, cache_headers=False)

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_NAME,
        frontend_url_path=DOMAIN,
        module_url=PANEL_URL,
        trust_external=False,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"title": DEFAULT_NAME},
        # unfortunately embed iframe is needed to prevent issues with the layout
        embed_iframe=True,
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_NAME,
        frontend_url_path=DOMAIN + "_dev",
        module_url="http://192.168.1.109:3000/src/main.ts",
        trust_external=True,
        sidebar_title=PANEL_TITLE + " DEV",
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"title": DEFAULT_NAME},
        embed_iframe=True,
    )


def async_unregister_panel(hass):
    """Unregister custom panel."""
    frontend.async_remove_panel(hass, DOMAIN)
    _LOGGER.debug("Removing panel")
