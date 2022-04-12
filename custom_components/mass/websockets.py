"""Websockets API for Music Assistant."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.core import HomeAssistant, callback
from music_assistant import MusicAssistant
from music_assistant.constants import MassEvent

from .const import DOMAIN

# general API constants
TYPE = "type"
ID = "id"
OBJECT_ID = "object_id"
LAZY = "lazy"

ERR_NOT_LOADED = "not_loaded"

DATA_UNSUBSCRIBE = "unsubs"


@callback
def async_register_websockets(hass: HomeAssistant) -> None:
    """Register all of our websocket commands."""
    websocket_api.async_register_command(hass, websocket_players)
    websocket_api.async_register_command(hass, websocket_playerqueues)
    websocket_api.async_register_command(hass, websocket_artists)
    websocket_api.async_register_command(hass, websocket_albums)
    websocket_api.async_register_command(hass, websocket_tracks)
    websocket_api.async_register_command(hass, websocket_playlists)
    websocket_api.async_register_command(hass, websocket_radio)
    websocket_api.async_register_command(hass, websocket_subscribe_events)


def async_get_mass(orig_func: Callable) -> Callable:
    """Decorate async function to get mass object."""

    @wraps(orig_func)
    async def async_get_mass_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict
    ) -> None:
        """Lookup mass object in hass data and provide to function."""
        mass = hass.data.get(DOMAIN)
        if mass is None:
            connection.send_error(
                msg[ID], ERR_NOT_LOADED, "Music Assistant is not (yet) loaded"
            )
            return

        await orig_func(hass, connection, msg, mass)

    return async_get_mass_func


@websocket_api.websocket_command(
    {vol.Required(TYPE): f"{DOMAIN}/players", vol.Optional(OBJECT_ID): str}
)
@websocket_api.async_response
@async_get_mass
async def websocket_players(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return player(s)."""
    if OBJECT_ID in msg:
        item = mass.players.get_player(msg[OBJECT_ID])
        if item is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[ID]}")
            return
        result = item.to_dict()
    else:
        # all items
        result = [item.to_dict() for item in mass.players.players]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {vol.Required(TYPE): f"{DOMAIN}/playerqueues", vol.Optional(OBJECT_ID): str}
)
@websocket_api.async_response
@async_get_mass
async def websocket_playerqueues(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return player queue(s)."""
    if OBJECT_ID in msg:
        item = mass.players.get_player_queue(msg[OBJECT_ID])
        if item is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[ID]}")
            return
        result = item.to_dict()
    else:
        # all items
        result = [item.to_dict() for item in mass.players.player_queues]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/artists",
        vol.Optional(OBJECT_ID): str,
        vol.Optional(LAZY): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_artists(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return artist(s)."""
    if OBJECT_ID in msg:
        item = await mass.music.get_item_by_uri(
            msg[OBJECT_ID], lazy=msg.get(LAZY, True)
        )
        if item is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[ID]}")
            return
        result = item.to_dict()
    else:
        # all items
        result = [item.to_dict() for item in await mass.music.artists.library()]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/albums",
        vol.Optional(OBJECT_ID): str,
        vol.Optional(LAZY): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_albums(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return album(s)."""
    if OBJECT_ID in msg:
        item = await mass.music.get_item_by_uri(
            msg[OBJECT_ID], lazy=msg.get(LAZY, True)
        )
        if item is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[ID]}")
            return
        result = item.to_dict()
    else:
        # all items
        result = [item.to_dict() for item in await mass.music.albums.library()]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/tracks",
        vol.Optional(OBJECT_ID): str,
        vol.Optional(LAZY): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_tracks(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return track(s)."""
    if OBJECT_ID in msg:
        item = await mass.music.get_item_by_uri(
            msg[OBJECT_ID], lazy=msg.get(LAZY, True)
        )
        if item is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[ID]}")
            return
        result = item.to_dict()
    else:
        # all items
        result = [item.to_dict() for item in await mass.music.tracks.library()]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlists",
        vol.Optional(OBJECT_ID): str,
        vol.Optional(LAZY): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_playlists(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return playlist(s)."""
    if OBJECT_ID in msg:
        item = await mass.music.get_item_by_uri(
            msg[OBJECT_ID], lazy=msg.get(LAZY, True)
        )
        if item is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[ID]}")
            return
        result = item.to_dict()
    else:
        # all items
        result = [item.to_dict() for item in await mass.music.playlists.library()]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/radio",
        vol.Optional(OBJECT_ID): str,
        vol.Optional(LAZY): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_radio(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return radio(s)."""
    if OBJECT_ID in msg:
        item = await mass.music.get_item_by_uri(
            msg[OBJECT_ID], lazy=msg.get(LAZY, True)
        )
        if item is None:
            connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[ID]}")
            return
        result = item.to_dict()
    else:
        # all items
        result = [item.to_dict() for item in await mass.music.radio.library()]

    connection.send_result(
        msg[ID],
        result,
    )


### subscribe events
@websocket_api.websocket_command({vol.Required(TYPE): f"{DOMAIN}/subscribe"})
@websocket_api.async_response
@async_get_mass
async def websocket_subscribe_events(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict, mass: MusicAssistant
) -> None:
    """Subscribe to Music Assistant events."""

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for unsub in unsubs:
            unsub()

    @callback
    def forward_event(event: MassEvent) -> None:

        if isinstance(event.data, list):
            event_data = [x.to_dict() for x in event.data]
        elif event.data and hasattr(event.data, "to_dict"):
            event_data = event.data.to_dict()
        else:
            event_data = event.data

        connection.send_message(
            websocket_api.event_message(
                msg[ID],
                {
                    "event": event.type.value,
                    "object_id": event.object_id,
                    "data": event_data,
                },
            )
        )

    msg[DATA_UNSUBSCRIBE] = unsubs = [mass.subscribe(forward_event)]
    connection.subscriptions[msg[ID]] = async_cleanup

    connection.send_result(msg[ID], None)
