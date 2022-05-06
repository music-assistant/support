"""Host Music Assistant frontend in custom panel."""
import logging
import os
from typing import Callable

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_FOLDER = "frontend/dist"
JS_FILENAME = "mass.iife.js"
LIB_URL_BASE = f"/lib/{DOMAIN}/"
JS_URL = LIB_URL_BASE + JS_FILENAME

PANEL_ICON = "mdi:play-circle"
COMPONENT_NAME = "music-assistant"


async def async_register_panel(hass: HomeAssistant, title: str) -> Callable:
    """Register custom panel."""
    panel_url = title.lower().replace(" ", "-")
    root_dir = os.path.dirname(__file__)
    panel_dir = os.path.join(root_dir, PANEL_FOLDER)

    for filename in os.listdir(panel_dir):
        url = LIB_URL_BASE + filename
        filepath = os.path.join(panel_dir, filename)
        hass.http.register_static_path(url, filepath, cache_headers=False)

    # register index page
    index_path = os.path.join(panel_dir, "index.html")
    hass.http.register_static_path(LIB_URL_BASE, index_path)
    hass.http.register_redirect(LIB_URL_BASE[:-1], LIB_URL_BASE)

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=COMPONENT_NAME,
        frontend_url_path=panel_url,
        module_url=os.environ.get("MASS_DEBUG_URL", JS_URL),
        trust_external=True,
        sidebar_title=title,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"title": title},
        # unfortunately embed iframe is needed to prevent issues with the layout
        embed_iframe=True,
    )

    def unregister():
        frontend.async_remove_panel(hass, panel_url)

    return unregister
