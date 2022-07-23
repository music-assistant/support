"""Websockets API for Music Assistant."""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from functools import wraps

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.core import HomeAssistant, callback
from music_assistant import MusicAssistant
from music_assistant.models.enums import (
    ContentType,
    CrossFadeMode,
    MediaType,
    MetadataMode,
    ProviderType,
    QueueOption,
    RepeatMode,
)
from music_assistant.models.event import MassEvent

from .const import DOMAIN

# general API constants
TYPE = "type"
ID = "id"
ITEM_ID = "item_id"
PROVIDER = "provider"
PROVIDER_ID = "provider_id"
URI = "uri"
NAME = "name"
MEDIA = "media"
POSITION = "position"
PLAYER_ID = "player_id"
QUEUE_ID = "queue_id"
COMMAND = "command"
COMMAND_ARG = "command_arg"
LAZY = "lazy"
REFRESH = "refresh"
LIBRARY = "library"
SEARCH = "search"
SORT = "sort"
OFFSET = "offset"
LIMIT = "limit"
FORCE_PROVIDER_VERSION = "force_provider_version"

ERR_NOT_LOADED = "not_loaded"

DATA_UNSUBSCRIBE = "unsubs"


@callback
def async_register_websockets(hass: HomeAssistant) -> None:
    """Register all of our websocket commands."""

    websocket_api.async_register_command(hass, websocket_artists)
    websocket_api.async_register_command(hass, websocket_artist)
    websocket_api.async_register_command(hass, websocket_albums)
    websocket_api.async_register_command(hass, websocket_album)
    websocket_api.async_register_command(hass, websocket_album_tracks)
    websocket_api.async_register_command(hass, websocket_album_versions)
    websocket_api.async_register_command(hass, websocket_tracks)
    websocket_api.async_register_command(hass, websocket_track)
    websocket_api.async_register_command(hass, websocket_track_versions)
    websocket_api.async_register_command(hass, websocket_track_preview)
    websocket_api.async_register_command(hass, websocket_playlists)
    websocket_api.async_register_command(hass, websocket_playlist)
    websocket_api.async_register_command(hass, websocket_playlist_tracks)
    websocket_api.async_register_command(hass, websocket_add_playlist_tracks)
    websocket_api.async_register_command(hass, websocket_remove_playlist_tracks)
    websocket_api.async_register_command(hass, websocket_playlist_create)
    websocket_api.async_register_command(hass, websocket_radios)
    websocket_api.async_register_command(hass, websocket_radio)
    websocket_api.async_register_command(hass, websocket_radio_versions)
    websocket_api.async_register_command(hass, websocket_players)
    websocket_api.async_register_command(hass, websocket_playerqueues)
    websocket_api.async_register_command(hass, websocket_playerqueue_items)
    websocket_api.async_register_command(hass, websocket_playerqueue_command)
    websocket_api.async_register_command(hass, websocket_playerqueue_settings)
    websocket_api.async_register_command(hass, websocket_play_media)
    websocket_api.async_register_command(hass, websocket_start_sync)
    websocket_api.async_register_command(hass, websocket_item)
    websocket_api.async_register_command(hass, websocket_thumb)
    websocket_api.async_register_command(hass, websocket_library_add)
    websocket_api.async_register_command(hass, websocket_library_remove)
    websocket_api.async_register_command(hass, websocket_delete_db_item)
    websocket_api.async_register_command(hass, websocket_artist_tracks)
    websocket_api.async_register_command(hass, websocket_artist_albums)
    websocket_api.async_register_command(hass, websocket_search)
    websocket_api.async_register_command(hass, websocket_browse)
    websocket_api.async_register_command(hass, websocket_jobs)
    websocket_api.async_register_command(hass, websocket_providers)
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


##### ARTIST RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/artists",
        vol.Optional(OFFSET, default=0): int,
        vol.Optional(LIMIT, default=250): int,
        vol.Optional(SORT, default="sort_name"): str,
        vol.Optional(LIBRARY): bool,
        vol.Optional(SEARCH): str,
        vol.Optional("album_artists_only"): bool,
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
    """Return artists."""
    if msg.get("album_artists_only"):
        func = mass.music.artists.album_artists
    else:
        func = mass.music.artists.db_items

    await connection.send_big_result(
        msg[ID],
        await func(
            msg.get(LIBRARY),
            msg.get(SEARCH),
            limit=msg[LIMIT],
            offset=msg[OFFSET],
            order_by=msg[SORT],
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/artist",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_artist(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return artist."""
    item = await mass.music.artists.get(
        msg[ITEM_ID], msg[PROVIDER], lazy=msg[LAZY], force_refresh=msg[REFRESH]
    )
    if item is None:
        connection.send_error(
            msg[ID],
            ERR_NOT_FOUND,
            f"Artist not found: {msg[PROVIDER]}/{msg[ITEM_ID]}",
        )
        return

    connection.send_result(
        msg[ID],
        item.to_dict(),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/artist/tracks",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_artist_tracks(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return artist toptracks."""
    result = [
        item.to_dict()
        for item in await mass.music.artists.toptracks(msg[ITEM_ID], msg[PROVIDER])
    ]
    await connection.send_big_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/artist/albums",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_artist_albums(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return artist albums."""
    result = [
        item.to_dict()
        for item in await mass.music.artists.albums(msg[ITEM_ID], msg[PROVIDER])
    ]
    await connection.send_big_result(
        msg[ID],
        result,
    )


##### ALBUM RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/albums",
        vol.Optional(OFFSET, default=0): int,
        vol.Optional(LIMIT, default=250): int,
        vol.Optional(SORT, default="sort_name"): str,
        vol.Optional(LIBRARY): bool,
        vol.Optional(SEARCH): str,
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
    """Return albums."""
    await connection.send_big_result(
        msg[ID],
        await mass.music.albums.db_items(
            msg.get(LIBRARY),
            msg.get(SEARCH),
            limit=msg[LIMIT],
            offset=msg[OFFSET],
            order_by=msg[SORT],
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/album",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
        vol.Optional(FORCE_PROVIDER_VERSION, default=False): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_album(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return album."""
    if msg.get(FORCE_PROVIDER_VERSION):
        item = await mass.music.albums.get_provider_item(msg[ITEM_ID], msg[PROVIDER])
    else:
        item = await mass.music.albums.get(
            msg[ITEM_ID], msg[PROVIDER], lazy=msg[LAZY], force_refresh=msg[REFRESH]
        )

    connection.send_result(
        msg[ID],
        item.to_dict(),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/album/tracks",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
        vol.Optional(LAZY): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_album_tracks(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return album tracks."""
    result = [
        item.to_dict()
        for item in await mass.music.albums.tracks(msg[ITEM_ID], msg[PROVIDER])
    ]
    await connection.send_big_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/album/versions",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
        vol.Optional(LAZY): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_album_versions(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return album versions."""
    result = [
        item.to_dict()
        for item in await mass.music.albums.versions(msg[ITEM_ID], msg[PROVIDER])
    ]
    await connection.send_big_result(
        msg[ID],
        result,
    )


##### TRACK RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/tracks",
        vol.Optional(OFFSET, default=0): int,
        vol.Optional(LIMIT, default=250): int,
        vol.Optional(SORT, default="sort_name"): str,
        vol.Optional(LIBRARY): bool,
        vol.Optional(SEARCH): str,
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
    """Return tracks."""
    await connection.send_big_result(
        msg[ID],
        await mass.music.tracks.db_items(
            msg.get(LIBRARY),
            msg.get(SEARCH),
            limit=msg[LIMIT],
            offset=msg[OFFSET],
            order_by=msg[SORT],
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/track/versions",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_track_versions(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return track versions."""
    result = [
        item.to_dict()
        for item in await mass.music.tracks.versions(msg[ITEM_ID], msg[PROVIDER])
    ]
    await connection.send_big_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/track",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
        vol.Optional(FORCE_PROVIDER_VERSION, default=False): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_track(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return track."""
    if msg.get(FORCE_PROVIDER_VERSION):
        item = await mass.music.albums.get_provider_item(msg[ITEM_ID], msg[PROVIDER])
    else:
        item = await mass.music.tracks.get(
            msg[ITEM_ID], msg[PROVIDER], lazy=msg[LAZY], force_refresh=msg[REFRESH]
        )
    connection.send_result(
        msg[ID],
        item.to_dict(),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/track/preview",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_track_preview(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return track preview url."""
    url = await mass.streams.get_preview_url(msg[PROVIDER], msg[ITEM_ID])

    connection.send_result(
        msg[ID],
        url,
    )


##### PLAYLIST RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlists",
        vol.Optional(OFFSET, default=0): int,
        vol.Optional(LIMIT, default=250): int,
        vol.Optional(SORT, default="sort_name"): str,
        vol.Optional(LIBRARY): bool,
        vol.Optional(SEARCH): str,
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
    """Return playlists."""
    await connection.send_big_result(
        msg[ID],
        await mass.music.playlists.db_items(
            msg.get(LIBRARY),
            msg.get(SEARCH),
            limit=msg[LIMIT],
            offset=msg[OFFSET],
            order_by=msg[SORT],
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlist",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_playlist(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return track."""
    item = await mass.music.playlists.get(
        msg[ITEM_ID], msg[PROVIDER], lazy=msg[LAZY], force_refresh=msg[REFRESH]
    )
    if item is None:
        connection.send_error(
            msg[ID],
            ERR_NOT_FOUND,
            f"playlist not found: {msg[PROVIDER]}/{msg[ITEM_ID]}",
        )
        return
    connection.send_result(
        msg[ID],
        item.to_dict(),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlist/tracks",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_playlist_tracks(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return playlist tracks."""
    result = [
        item.to_dict()
        for item in await mass.music.playlists.tracks(msg[ITEM_ID], msg[PROVIDER])
    ]
    await connection.send_big_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlist/tracks/add",
        vol.Required(ITEM_ID): str,
        vol.Required(URI): vol.Any(str, list),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_add_playlist_tracks(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Add playlist tracks command."""
    if isinstance(msg[URI], list):
        await mass.music.playlists.add_playlist_tracks(msg[ITEM_ID], msg[URI])
    else:
        await mass.music.playlists.add_playlist_track(msg[ITEM_ID], msg[URI])

    connection.send_result(
        msg[ID],
        "OK",
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlist/tracks/remove",
        vol.Required(ITEM_ID): str,
        vol.Required(POSITION): vol.Any(int, list),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_remove_playlist_tracks(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Remove playlist track(s) command."""
    positions = msg[POSITION]
    if isinstance(msg[POSITION], int):
        positions = [msg[POSITION]]
    await mass.music.playlists.remove_playlist_tracks(msg[ITEM_ID], positions)

    connection.send_result(
        msg[ID],
        "OK",
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlist/create",
        vol.Required(NAME): str,
        vol.Optional(PROVIDER_ID): str,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_playlist_create(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Create new playlist command."""
    new_playlist = await mass.music.playlists.create(msg[NAME], msg.get(PROVIDER_ID))

    connection.send_result(
        msg[ID],
        new_playlist.to_dict(),
    )


##### RADIO RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/radios",
        vol.Optional(OFFSET, default=0): int,
        vol.Optional(LIMIT, default=250): int,
        vol.Optional(SORT, default="sort_name"): str,
        vol.Optional(LIBRARY): bool,
        vol.Optional(SEARCH): str,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_radios(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return radios."""
    await connection.send_big_result(
        msg[ID],
        await mass.music.radio.db_items(
            msg.get(LIBRARY),
            msg.get(SEARCH),
            limit=msg[LIMIT],
            offset=msg[OFFSET],
            order_by=msg[SORT],
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/radio",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
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
    """Return radio."""
    item = await mass.music.radio.get(
        msg[ITEM_ID], msg[PROVIDER], lazy=msg[LAZY], force_refresh=msg[REFRESH]
    )
    if item is None:
        connection.send_error(
            msg[ID],
            ERR_NOT_FOUND,
            f"radio not found: {msg[PROVIDER]}/{msg[ITEM_ID]}",
        )
        return

    connection.send_result(
        msg[ID],
        item.to_dict(),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/radio/versions",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): vol.Coerce(ProviderType),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_radio_versions(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return radio versions."""
    result = [
        item.to_dict()
        for item in await mass.music.radio.versions(msg[ITEM_ID], msg[PROVIDER])
    ]
    await connection.send_big_result(
        msg[ID],
        result,
    )


##### GENERIC MEDIA ITEM RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/item",
        vol.Required(URI): str,
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_item(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return single MediaItem by uri."""
    if item := await mass.music.get_item_by_uri(
        msg[URI], lazy=msg[LAZY], force_refresh=msg[REFRESH]
    ):
        connection.send_result(
            msg[ID],
            item.to_dict(),
        )
        return
    connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[URI]}")


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/thumb",
        vol.Required("path"): str,
        vol.Optional("size"): int,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_thumb(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return (resized) image thumb from url or local image."""
    res = await mass.metadata.get_thumbnail(msg["path"], msg.get("size"), True)
    connection.send_result(
        msg[ID],
        res,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/library/add",
        vol.Required(URI): str,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_library_add(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Add item to library."""
    item = await mass.music.get_item_by_uri(msg[URI])
    if not item:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[URI]}")

    await mass.music.add_to_library(item.media_type, item.item_id, item.provider)

    connection.send_result(
        msg[ID],
        "OK",
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/library/remove",
        vol.Required(URI): str,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_library_remove(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Remove item from library."""
    item = await mass.music.get_item_by_uri(msg[URI])
    if not item:
        connection.send_error(msg[ID], ERR_NOT_FOUND, f"Item not found: {msg[URI]}")

    await mass.music.remove_from_library(item.media_type, item.item_id, item.provider)

    connection.send_result(
        msg[ID],
        "OK",
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/delete_db_item",
        vol.Required("media_type"): vol.Coerce(MediaType),
        vol.Required("db_id"): vol.Coerce(int),
        vol.Optional("recursive"): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_delete_db_item(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Delete item from the database."""
    await mass.music.delete_db_item(
        msg["media_type"], msg["db_id"], msg.get("recursive", False)
    )

    connection.send_result(
        msg[ID],
        "OK",
    )


##### BROWSE and SEARCH RELATED COMMANDS #######################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/search",
        vol.Required("query"): str,
        vol.Optional("media_types", default=MediaType.ALL): list,
        vol.Optional("limit", default=5): int,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_search(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return Browse items."""
    result = await mass.music.search(
        msg["query"], media_types=msg["media_types"], limit=msg["limit"]
    )
    result = [x.to_dict() for x in result]

    await connection.send_big_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {vol.Required(TYPE): f"{DOMAIN}/browse", vol.Optional("path"): str}
)
@websocket_api.async_response
@async_get_mass
async def websocket_browse(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return Browse items."""

    await connection.send_big_result(
        msg[ID],
        await mass.music.browse(msg.get("path")),
    )


##### PLAYER/QUEUE RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/players",
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_players(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return registered players."""
    result = [item.to_dict() for item in mass.players.players]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playerqueues",
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_playerqueues(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return all player queue's."""
    result = [item.to_dict() for item in mass.players.player_queues]

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {vol.Required(TYPE): f"{DOMAIN}/playerqueue", vol.Required(QUEUE_ID): str}
)
@websocket_api.async_response
@async_get_mass
async def websocket_playerqueue(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return single player queue details by id."""
    item = mass.players.get_player_queue(msg[QUEUE_ID])
    if item is None:
        connection.send_error(
            msg[ID], ERR_NOT_FOUND, f"Queue not found: {msg[QUEUE_ID]}"
        )
        return
    result = item.to_dict()

    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {vol.Required(TYPE): f"{DOMAIN}/playerqueue/items", vol.Required(QUEUE_ID): str}
)
@websocket_api.async_response
@async_get_mass
async def websocket_playerqueue_items(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return player queue items."""
    queue = mass.players.get_player_queue(msg[QUEUE_ID])
    if queue is None:
        connection.send_error(
            msg[ID], ERR_NOT_FOUND, f"Queue not found: {msg[QUEUE_ID]}"
        )
        return
    result = [x.to_dict() for x in queue.items]

    await connection.send_big_result(
        msg[ID],
        result,
    )


class QueueCommand(str, Enum):
    """Enum with the player/queue commands."""

    PLAY = "play"
    PAUSE = "pause"
    PLAY_PAUSE = "play_pause"
    NEXT = "next"
    PREVIOUS = "previous"
    SEEK = "seek"
    SKIP_AHEAD = "skip_ahead"
    SKIP_BACK = "skip_back"
    STOP = "stop"
    POWER = "power"
    POWER_TOGGLE = "power_toggle"
    VOLUME = "volume"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    CLEAR = "clear"
    PLAY_INDEX = "play_index"
    MOVE_UP = "move_up"
    MOVE_DOWN = "move_down"
    MOVE_NEXT = "move_next"
    DELETE = "delete"
    GROUP_VOLUME = "group_volume"
    GROUP_POWER = "group_power"


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playerqueue/command",
        vol.Required(QUEUE_ID): str,
        vol.Required(COMMAND): str,
        vol.Optional(COMMAND_ARG): vol.Any(int, bool, float, str),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_playerqueue_command(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Execute command on PlayerQueue."""
    if player_queue := mass.players.get_player_queue(msg[QUEUE_ID]):
        if msg[COMMAND] == QueueCommand.PLAY:
            await player_queue.play()
        elif msg[COMMAND] == QueueCommand.PAUSE:
            await player_queue.pause()
        elif msg[COMMAND] == QueueCommand.NEXT:
            await player_queue.next()
        elif msg[COMMAND] == QueueCommand.PREVIOUS:
            await player_queue.previous()
        elif msg[COMMAND] == QueueCommand.STOP:
            await player_queue.stop()
        elif msg[COMMAND] == QueueCommand.PLAY_PAUSE:
            await player_queue.play_pause()
        elif msg[COMMAND] == QueueCommand.SEEK:
            await player_queue.seek(int(msg[COMMAND_ARG]))
        elif msg[COMMAND] == QueueCommand.SKIP_AHEAD:
            await player_queue.skip_ahead()
        elif msg[COMMAND] == QueueCommand.SKIP_BACK:
            await player_queue.skip_back()
        elif msg[COMMAND] == QueueCommand.POWER_TOGGLE:
            await player_queue.player.power_toggle()
        elif msg[COMMAND] == QueueCommand.VOLUME:
            await player_queue.player.volume_set(int(msg[COMMAND_ARG]))
        elif msg[COMMAND] == QueueCommand.VOLUME_UP:
            await player_queue.player.volume_up()
        elif msg[COMMAND] == QueueCommand.VOLUME_DOWN:
            await player_queue.player.volume_down()
        elif msg[COMMAND] == QueueCommand.POWER:
            await player_queue.player.power(msg[COMMAND_ARG])
        elif msg[COMMAND] == QueueCommand.PLAY_INDEX:
            await player_queue.play_index(msg[COMMAND_ARG])
        elif msg[COMMAND] == QueueCommand.MOVE_UP:
            await player_queue.move_item(msg[COMMAND_ARG], -1)
        elif msg[COMMAND] == QueueCommand.MOVE_DOWN:
            await player_queue.move_item(msg[COMMAND_ARG], 1)
        elif msg[COMMAND] == QueueCommand.MOVE_NEXT:
            await player_queue.move_item(msg[COMMAND_ARG], 0)
        elif msg[COMMAND] == QueueCommand.CLEAR:
            await player_queue.clear()
        elif msg[COMMAND] == QueueCommand.DELETE:
            await player_queue.delete_item(msg[COMMAND_ARG])
        elif msg[COMMAND] == QueueCommand.GROUP_POWER:
            await player_queue.player.set_group_power(msg[COMMAND_ARG])
        elif msg[COMMAND] == QueueCommand.GROUP_VOLUME:
            await player_queue.player.set_group_volume(int(msg[COMMAND_ARG]))

        connection.send_result(
            msg[ID],
            "OK",
        )
        return
    connection.send_error(msg[ID], ERR_NOT_FOUND, f"Queue not found: {msg[QUEUE_ID]}")


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playerqueue/settings",
        vol.Required(QUEUE_ID): str,
        vol.Required("settings"): {
            vol.Optional("repeat_mode"): vol.Coerce(RepeatMode),
            vol.Optional("crossfade_mode"): vol.Coerce(CrossFadeMode),
            vol.Optional("shuffle_enabled"): bool,
            vol.Optional("crossfade_duration"): vol.Coerce(int),
            vol.Optional("volume_normalization_enabled"): bool,
            vol.Optional("volume_normalization_target"): vol.Coerce(float),
            vol.Optional("stream_type"): vol.Coerce(ContentType),
            vol.Optional("max_sample_rate"): vol.Coerce(int),
            vol.Optional("announce_volume_increase"): vol.Coerce(int),
            vol.Optional("metadata_mode"): vol.Coerce(MetadataMode),
        },
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_playerqueue_settings(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Set PlayerQueue setting/preference."""
    if player_queue := mass.players.get_player_queue(msg[QUEUE_ID]):
        for key, value in msg["settings"].items():
            setattr(player_queue.settings, key, value)

        connection.send_result(
            msg[ID],
            "OK",
        )
        return
    connection.send_error(msg[ID], ERR_NOT_FOUND, f"Queue not found: {msg[QUEUE_ID]}")


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/play_media",
        vol.Required(QUEUE_ID): str,
        vol.Required(MEDIA): vol.Any(str, list, dict),
        vol.Optional(COMMAND, default=QueueOption.PLAY): vol.Coerce(QueueOption),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_play_media(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Execute play_media command on PlayerQueue."""
    if player_queue := mass.players.get_player_queue(msg[QUEUE_ID]):
        await player_queue.play_media(msg[MEDIA], msg[COMMAND])

        connection.send_result(
            msg[ID],
            "OK",
        )
        return
    connection.send_error(msg[ID], ERR_NOT_FOUND, f"Queue not found: {msg[QUEUE_ID]}")


# generic/other endpoints


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/start_sync",
        vol.Optional("media_type"): vol.Coerce(MediaType),
        vol.Optional("prov_type"): vol.Coerce(ProviderType),
        vol.Optional("clear_cache"): bool,
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_start_sync(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Execute play_media command on PlayerQueue."""
    if media_type := msg.get("media_type"):
        media_types = (media_type,)
    else:
        media_types = None
    if prov_type := msg.get("prov_type"):
        prov_types = (prov_type,)
    else:
        prov_types = None
    if media_type := msg.get("clear_cache"):
        await mass.cache.clear()
    await mass.music.start_sync(media_types, prov_types)


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/jobs",
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_jobs(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return running background jobs."""
    connection.send_result(
        msg[ID],
        [x.to_dict() for x in mass.jobs],
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/providers",
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_providers(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
    mass: MusicAssistant,
) -> None:
    """Return some statistics and generic info."""
    connection.send_result(
        msg[ID],
        {x.id: x.to_dict() for x in mass.music.providers},
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
