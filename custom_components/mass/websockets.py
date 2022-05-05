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
from music_assistant.constants import MassEvent
from music_assistant.models.player_queue import QueueOption

from .const import DOMAIN

# general API constants
TYPE = "type"
ID = "id"
ITEM_ID = "item_id"
PROVIDER = "provider"
URI = "uri"
POSITION = "position"
PLAYER_ID = "player_id"
QUEUE_ID = "queue_id"
COMMAND = "command"
COMMAND_ARG = "command_arg"
LAZY = "lazy"
REFRESH = "refresh"

ERR_NOT_LOADED = "not_loaded"

DATA_UNSUBSCRIBE = "unsubs"


@callback
def async_register_websockets(hass: HomeAssistant) -> None:
    """Register all of our websocket commands."""
    websocket_api.async_register_command(hass, websocket_players)
    websocket_api.async_register_command(hass, websocket_playerqueues)
    websocket_api.async_register_command(hass, websocket_playerqueue_items)
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
    websocket_api.async_register_command(hass, websocket_radios)
    websocket_api.async_register_command(hass, websocket_radio)
    websocket_api.async_register_command(hass, websocket_queue_command)
    websocket_api.async_register_command(hass, websocket_play_media)
    websocket_api.async_register_command(hass, websocket_item)
    websocket_api.async_register_command(hass, websocket_library_add)
    websocket_api.async_register_command(hass, websocket_library_remove)
    websocket_api.async_register_command(hass, websocket_artist_tracks)
    websocket_api.async_register_command(hass, websocket_artist_albums)
    websocket_api.async_register_command(hass, websocket_jobs)
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
    result = [item.to_dict() for item in await mass.music.artists.library()]
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/artist",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
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
        vol.Required(PROVIDER): str,
        vol.Optional(LAZY): bool,
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
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/artist/albums",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
        vol.Optional(LAZY): bool,
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
    connection.send_result(
        msg[ID],
        result,
    )


##### ALBUM RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/albums",
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
    result = [item.to_dict() for item in await mass.music.albums.library()]
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/album",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
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
    item = await mass.music.albums.get(
        msg[ITEM_ID], msg[PROVIDER], lazy=msg[LAZY], force_refresh=msg[REFRESH]
    )
    if item is None:
        connection.send_error(
            msg[ID],
            ERR_NOT_FOUND,
            f"album not found: {msg[PROVIDER]}/{msg[ITEM_ID]}",
        )
        return

    connection.send_result(
        msg[ID],
        item.to_dict(),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/album/tracks",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
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
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/album/versions",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
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
    connection.send_result(
        msg[ID],
        result,
    )


##### TRACK RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/tracks",
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
    """Return library tracks."""
    result = [item.to_dict() for item in await mass.music.tracks.library()]
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/track/versions",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
        vol.Optional(LAZY): bool,
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
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/track",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
        vol.Optional(LAZY, default=True): bool,
        vol.Optional(REFRESH, default=False): bool,
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
    item = await mass.music.tracks.get(
        msg[ITEM_ID], msg[PROVIDER], lazy=msg[LAZY], force_refresh=msg[REFRESH]
    )
    if item is None:
        connection.send_error(
            msg[ID],
            ERR_NOT_FOUND,
            f"track not found: {msg[PROVIDER]}/{msg[ITEM_ID]}",
        )
        return

    connection.send_result(
        msg[ID],
        item.to_dict(),
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/track/preview",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
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
    result = [item.to_dict() for item in await mass.music.playlists.library()]
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlist",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
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
        vol.Required(PROVIDER): str,
        vol.Optional(LAZY): bool,
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
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/playlist/tracks/add",
        vol.Required(ITEM_ID): str,
        vol.Required(URI): vol.Any(str, list),
        vol.Optional(COMMAND, default=QueueOption.PLAY): vol.Coerce(QueueOption),
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
    """Add playlist tracks command."""
    positions = msg[POSITION]
    if isinstance(msg[POSITION], int):
        positions = [msg[POSITION]]
    await mass.music.playlists.remove_playlist_tracks(msg[ITEM_ID], positions)

    connection.send_result(
        msg[ID],
        "OK",
    )


##### RADIO RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/radios",
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
    result = [item.to_dict() for item in await mass.music.radio.library()]
    connection.send_result(
        msg[ID],
        result,
    )


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/radio",
        vol.Required(ITEM_ID): str,
        vol.Required(PROVIDER): str,
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


##### PLAYER/QUEUE RELATED COMMANDS ##################


@websocket_api.websocket_command(
    {vol.Required(TYPE): f"{DOMAIN}/players", vol.Optional(PLAYER_ID): str}
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
    if PLAYER_ID in msg:
        item = mass.players.get_player(msg[PLAYER_ID])
        if item is None:
            connection.send_error(
                msg[ID], ERR_NOT_FOUND, f"Player not found: {msg[PLAYER_ID]}"
            )
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
    {vol.Required(TYPE): f"{DOMAIN}/playerqueues", vol.Optional(QUEUE_ID): str}
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
    if QUEUE_ID in msg:
        item = mass.players.get_player_queue(msg[QUEUE_ID])
        if item is None:
            connection.send_error(
                msg[ID], ERR_NOT_FOUND, f"Queue not found: {msg[QUEUE_ID]}"
            )
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
    {vol.Required(TYPE): f"{DOMAIN}/playerqueues/items", vol.Required(QUEUE_ID): str}
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

    connection.send_result(
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
    STOP = "stop"
    POWER = "power"
    POWER_TOGGLE = "power_toggle"
    VOLUME = "volume"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    SHUFFLE = "shuffle"
    REPEAT = "repeat"
    CLEAR = "clear"
    PLAY_INDEX = "play_index"
    MOVE_UP = "move_up"
    MOVE_DOWN = "move_down"
    MOVE_NEXT = "move_next"
    VOLUME_NORMALIZATION_ENABLED = "volume_normalization_enabled"
    VOLUME_NORMALIZATION_TARGET = "volume_normalization_target"
    CROSSFADE_DURATION = "crossfade_duration"


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): f"{DOMAIN}/queue_command",
        vol.Required(QUEUE_ID): str,
        vol.Required(COMMAND): str,
        vol.Optional(COMMAND_ARG): vol.Any(int, bool, float, str),
    }
)
@websocket_api.async_response
@async_get_mass
async def websocket_queue_command(
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
        elif msg[COMMAND] == QueueCommand.SHUFFLE:
            await player_queue.set_shuffle_enabled(bool(msg[COMMAND_ARG]))
        elif msg[COMMAND] == QueueCommand.REPEAT:
            await player_queue.set_repeat_enabled(bool(msg[COMMAND_ARG]))
        elif msg[COMMAND] == QueueCommand.VOLUME_NORMALIZATION_ENABLED:
            await player_queue.set_volume_normalization_enabled(bool(msg[COMMAND_ARG]))
        elif msg[COMMAND] == QueueCommand.VOLUME_NORMALIZATION_TARGET:
            await player_queue.set_volume_normalization_target(float(msg[COMMAND_ARG]))
        elif msg[COMMAND] == QueueCommand.CROSSFADE_DURATION:
            await player_queue.set_crossfade_duration(int(msg[COMMAND_ARG]))

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
        vol.Required(URI): vol.Any(str, list),
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
        await player_queue.play_media(msg[URI], msg[COMMAND])

        connection.send_result(
            msg[ID],
            "OK",
        )
        return
    connection.send_error(msg[ID], ERR_NOT_FOUND, f"Queue not found: {msg[QUEUE_ID]}")


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
