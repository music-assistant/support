"""Custom services for the Music Assistant integration."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service import ServiceCall
from music_assistant.common.models.enums import QueueOption, RepeatMode
from music_assistant.common.models.media_items import MediaItemType

from .const import DOMAIN
from .helpers import get_mass

if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient

CMD_PLAY = "play"
CMD_PAUSE = "pause"
CMD_NEXT = "next"
CMD_PREVIOUS = "previous"
CMD_STOP = "stop"
CMD_CLEAR = "clear"
CMD_PLAY_MEDIA = "play_media"
CMD_SHUFFLE_ON = "shuffle_on"
CMD_SHUFFLE_OFF = "shuffle_off"
CMD_REPEAT = "repeat"
CMD_SNAPSHOT_CREATE = "snapshot_create"
CMD_SNAPSHOT_RESTORE = "snapshot_restore"
CMD_PLAY_ANNOUNCEMENT = "play_announcement"


def validate_command_data(data: dict) -> dict:
    """Validate command args/mode."""
    cmd = data["command"]
    if cmd == CMD_REPEAT and "repeat_mode" not in data:
        raise vol.Invalid("Missing repeat_mode")
    if cmd == CMD_PLAY_MEDIA and "enqueue_mode" not in data:
        raise vol.Invalid("Missing enqueue_mode")
    if cmd in (CMD_PLAY_MEDIA, CMD_PLAY_ANNOUNCEMENT) and not data.get("uri"):
        raise vol.Invalid("No URI specified")
    return data


QueueCommandServiceSchema = vol.Schema(
    vol.All(
        {
            "player_id": vol.Union(str, [str]),
            "command": str,
            "uri": vol.Union(str, [str], None),
            "radio_mode": vol.Optional(bool),
            "repeat_mode": vol.Optional(vol.Coerce(RepeatMode)),
            "enqueue_mode": vol.Optional(vol.Coerce(QueueOption)),
        },
        validate_command_data,
    )
)


@callback
def register_services(hass: HomeAssistant):
    """Register custom services."""

    async def handle_queue_command(call: ServiceCall) -> None:
        """Handle queue_command service."""
        mass = get_mass(hass)
        data = call.data
        cmd = data["command"]
        if isinstance(data["player_id"], list):
            player_ids = data["player_id"]
        else:
            player_ids = [data["player_id"]]
        for player_id in player_ids:
            # translate entity_id --> player_id
            if entity := hass.states.get(player_id):
                player_id = entity.attributes.get("mass_player_id", player_id)  # noqa: PLW2901
            player = mass.players.get_player(player_id)
            if not player:
                raise RuntimeError(f"Invalid player id: {player_id}")
            if queue := mass.players.get_player_queue(player.active_source):
                queue_id = queue.queue_id
            else:
                queue_id = player_id
            if cmd == CMD_PLAY:
                await mass.players.queue_command_play(queue_id)
            elif cmd == CMD_PAUSE:
                await mass.players.queue_command_pause(queue_id)
            elif cmd == CMD_NEXT:
                await mass.players.queue_command_next(queue_id)
            elif cmd == CMD_PREVIOUS:
                await mass.players.queue_command_previous(queue_id)
            elif cmd == CMD_STOP:
                await mass.players.queue_command_stop(queue_id)
            elif cmd == CMD_CLEAR:
                await mass.players.queue_command_clear(queue_id)
            elif cmd == CMD_PLAY_MEDIA:
                media_items = []
                uris = data["uri"] if isinstance(data["uri"], list) else [data["uri"]]
                for uri in uris:
                    # try to handle playback of item by name
                    if "://" not in uri and (item := await get_item_by_name(mass, uri)):
                        media_items.append(item)
                    else:
                        media_items.append(uri)
                await mass.players.play_media(
                    queue_id,
                    media_items,
                    data["enqueue_mode"],
                    radio_mode=data.get("radio_mode", False),
                )
            elif cmd == CMD_SHUFFLE_ON:
                await mass.players.queue_command_shuffle(queue_id, True)
            elif cmd == CMD_SHUFFLE_OFF:
                await mass.players.queue_command_shuffle(queue_id, False)
            elif cmd == CMD_REPEAT:
                await mass.players.queue_command_repeat(queue_id, data["repeat_mode"])
            # elif cmd == CMD_SNAPSHOT_CREATE:
            #     await queue.snapshot_create()
            # elif cmd == CMD_SNAPSHOT_RESTORE:
            #     await queue.snapshot_restore()
            # elif cmd == CMD_PLAY_ANNOUNCEMENT:
            #     await queue.play_announcement(data["uri"])

    hass.services.async_register(
        DOMAIN, "queue_command", handle_queue_command, schema=QueueCommandServiceSchema
    )


async def get_item_by_name(mass: MusicAssistantClient, name: str) -> MediaItemType | None:
    """Try to find a media item (such as a playlist) by name."""
    # iterate media controllers one by one,
    # start with playlists and radio as those are the most common one
    for func in (
        mass.music.get_library_playlists,
        mass.music.get_library_radios,
        mass.music.get_library_albums,
        mass.music.get_library_tracks,
        mass.music.get_library_artists,
    ):
        result = await func(search=name)
        for item in result.items:
            if name.lower() == item.name.lower():
                return item
    return None
