"""Host Music Assistant frontend in custom panel."""
import logging
import os

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_FOLDER = "frontend/dist"
JS_FILENAME = "mass.umd.js"
ICO_FILENAME = "favicon.ico"
INDEX_FILENAME = "index.html"

PANEL_URL_BASE = f"/panel_custom/{DOMAIN}/"
JS_URL = PANEL_URL_BASE + JS_FILENAME
ICO_URL = PANEL_URL_BASE + ICO_FILENAME
INDEX_URL = PANEL_URL_BASE
PANEL_TITLE = DEFAULT_NAME
PANEL_ICON = "mdi:play-circle"
PANEL_NAME = "music-assistant"


async def async_register_panel(hass: HomeAssistant):
    """Register custom panel."""
    root_dir = os.path.dirname(__file__)
    panel_dir = os.path.join(root_dir, PANEL_FOLDER)
    js_path = os.path.join(panel_dir, JS_FILENAME)
    ico_path = os.path.join(panel_dir, JS_FILENAME)
    index_path = os.path.join(panel_dir, INDEX_FILENAME)

    hass.http.register_static_path(JS_URL, js_path, cache_headers=False)
    hass.http.register_static_path(ICO_URL, ico_path)
    hass.http.register_static_path(PANEL_URL_BASE, index_path)
    hass.http.register_redirect(PANEL_URL_BASE[:-1], PANEL_URL_BASE)

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_NAME,
        frontend_url_path=DOMAIN,
        module_url=os.environ.get("MASS_DEBUG_URL", JS_URL),
        trust_external=False,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"title": DEFAULT_NAME},
        # unfortunately embed iframe is needed to prevent issues with the layout
        embed_iframe=True,
    )


def async_unregister_panel(hass):
    """Unregister custom panel."""
    frontend.async_remove_panel(hass, DOMAIN)
    _LOGGER.debug("Removing panel")
