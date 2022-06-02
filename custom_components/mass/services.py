"""Custom services for the Music Assistant integration."""

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import ServiceCall
from music_assistant import MusicAssistant
from music_assistant.models.enums import QueueOption, RepeatMode

from .const import DOMAIN

CMD_PLAY = "play"
CMD_PAUSE = "pause"
CMD_NEXT = "next"
CMD_PREVIOUS = "previous"
CMD_STOP = "stop"
CMD_CLEAR = "clear"
CMD_PLAY_MEDIA = "play_media"
CMD_SHUFFLE = "shuffle"
CMD_REPEAT = "repeat"
CMD_SNAPSHOT_CREATE = "snapshot_create"
CMD_SNAPSHOT_RESTORE = "snapshot_restore"
CMD_PLAY_ALERT = "play_alert"

CMD_ARGS_MAP = {
    "repeat_mode_one": RepeatMode.ONE,
    "repeat_mode_all": RepeatMode.ALL,
    "repeat_mode_off": RepeatMode.OFF,
    "shuffle_mode_on": True,
    "shuffle_mode_off": False,
    "play_media_play_now": QueueOption.PLAY,
    "play_media_play_next": QueueOption.NEXT,
    "play_media_play_add": QueueOption.ADD,
    "play_media_play_replace": QueueOption.REPLACE,
}


QueueCommandServiceSchema = vol.Schema(
    {
        "entity_id": cv.entity_ids,
        "command": str,
        "uri": vol.Optional(str),
        "mode": vol.Any(*CMD_ARGS_MAP.keys()),
    }
)


@callback
def register_services(hass: HomeAssistant, mass: MusicAssistant):
    """Register custom services."""

    async def handle_queue_command(call: ServiceCall) -> None:
        """Handle queue_command service."""
        data = call.data
        if isinstance(data["entity_id"], list):
            entity_ids = data["entity_id"]
        else:
            entity_ids = [data["entity_id"]]
        for entity_id in entity_ids:
            entity = hass.states.get(entity_id)
            entity_id = entity.attributes.get("source_entity_id", entity_id)
            player = mass.players.get_player(entity_id)
            queue = player.active_queue
            if data["command"] == CMD_PLAY:
                await queue.play()
            elif data["command"] == CMD_PAUSE:
                await queue.pause()
            elif data["command"] == CMD_NEXT:
                await queue.next()
            elif data["command"] == CMD_PREVIOUS:
                await queue.previous()
            elif data["command"] == CMD_STOP:
                await queue.stop()
            elif data["command"] == CMD_CLEAR:
                await queue.clear()
            elif data["command"] == CMD_PLAY_MEDIA:
                await queue.play_media(
                    data["uri"], CMD_ARGS_MAP[data.get("mode", "play_media_play_now")]
                )
            elif data["command"] == CMD_SHUFFLE:
                queue.settings.shuffle_enabled = CMD_ARGS_MAP[
                    data.get("mode", "shuffle_mode_on")
                ]
            elif data["command"] == CMD_REPEAT:
                queue.settings.repeat_mode = CMD_ARGS_MAP[
                    data.get("mode", "repeat_mode_all")
                ]
            elif data["command"] == CMD_SNAPSHOT_CREATE:
                await queue.snapshot_create()
            elif data["command"] == CMD_SNAPSHOT_RESTORE:
                await queue.snapshot_restore()
            elif data["command"] == CMD_PLAY_ALERT:
                await queue.play_alert(data["uri"])

    hass.services.async_register(
        DOMAIN, "queue_command", handle_queue_command, schema=QueueCommandServiceSchema
    )
