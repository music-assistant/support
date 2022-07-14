"""Host Music Assistant frontend in custom panel."""
import logging
import os
import urllib.parse
from http import HTTPStatus
from typing import Callable

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL
from aiohttp.typedefs import LooseHeaders
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from music_assistant import MusicAssistant

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
    hass.http.register_view(MassImageView())
    hass.http.register_view(MassPlaylistView())

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


class MassImageView(HomeAssistantView):
    """Music Assistant Image proxy."""

    name = "api:mass:image"
    url = "/api/mass/image_proxy"
    requires_auth = False

    @staticmethod
    async def get(request: web.Request) -> web.Response:
        """Start a get request."""
        size = int(request.query.get("size", 0))
        # strip off authSig added by the HA frontend, yikes
        url = request.query.get("url").split("?")[0]
        url = urllib.parse.unquote(url)

        hass: HomeAssistant = request.app["hass"]
        mass: MusicAssistant = hass.data[DOMAIN]

        if not url:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        if not url.startswith("http") and "://" in url:
            media_item = await mass.music.get_item_by_uri(url)
            url = mass.metadata.get_image_url_for_item(media_item)

        data = await mass.metadata.get_thumbnail(url, size=size)

        if data is None:
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        headers: LooseHeaders = {CACHE_CONTROL: "public, max-age=604800"}
        return web.Response(body=data, content_type="image/png", headers=headers)


class MassPlaylistView(HomeAssistantView):
    """Music Assistant Playlist proxy."""

    name = "api:mass:playlist"
    url = "/api/mass/{player_id}.m3u"
    requires_auth = False

    @staticmethod
    async def get(request: web.Request, player_id: str) -> web.Response:
        """Start a get request."""

        hass: HomeAssistant = request.app["hass"]
        mass: MusicAssistant = hass.data[DOMAIN]

        if not player_id:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        player = mass.players.get_player(player_id)
        if not player:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        if not player.active_queue.stream or player.active_queue.stream.done.is_set():
            await player.active_queue.play_index(
                player.active_queue.current_index or 0, passive=True
            )

        data = f"{player.active_queue.stream.url}\n"

        if data is None:
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        headers: LooseHeaders = {CACHE_CONTROL: "Cache-Control, no-cache"}
        return web.Response(
            body=data, content_type="application/x-mpegurl", headers=headers
        )
