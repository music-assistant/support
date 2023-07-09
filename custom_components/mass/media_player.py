"""MediaPlayer platform for Music Assistant integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.components.media_player.const import (
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from music_assistant.common.models.enums import (
    EventType,
    MediaType,
    PlayerState,
    QueueOption,
    RepeatMode,
)
from music_assistant.common.models.event import MassEvent

from .const import (
    ATTR_ACTIVE_QUEUE,
    ATTR_GROUP_LEADER,
    ATTR_GROUP_MEMBERS,
    ATTR_MASS_PLAYER_ID,
    ATTR_MASS_PLAYER_TYPE,
    ATTR_QUEUE_INDEX,
    ATTR_QUEUE_ITEMS,
    DOMAIN,
)
from .entity import MassBaseEntity
from .helpers import get_mass
from .media_browser import async_browse_media
from .services import get_item_by_name

if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient
    from music_assistant.common.models.player_queue import PlayerQueue

SUPPORTED_FEATURES = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_STOP
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_REPEAT_SET
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_VOLUME_STEP
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_BROWSE_MEDIA
    | SUPPORT_SEEK
    | SUPPORT_VOLUME_MUTE
)

STATE_MAPPING = {
    PlayerState.IDLE: STATE_IDLE,
    PlayerState.PLAYING: STATE_PLAYING,
    PlayerState.PAUSED: STATE_PAUSED,
}

QUEUE_OPTION_MAP = {
    # map from HA enqueue options to MA enqueue options
    # which are the same but just in case
    MediaPlayerEnqueue.ADD: QueueOption.ADD,
    MediaPlayerEnqueue.NEXT: QueueOption.NEXT,
    MediaPlayerEnqueue.PLAY: QueueOption.PLAY,
    MediaPlayerEnqueue.REPLACE: QueueOption.REPLACE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Music Assistant MediaPlayer(s) from Config Entry."""
    mass = get_mass(hass, config_entry.entry_id)
    added_ids = set()

    async def handle_player_added(event: MassEvent) -> None:
        """Handle Mass Player Added event."""
        if event.object_id in added_ids:
            return
        added_ids.add(event.object_id)
        async_add_entities([MassPlayer(mass, event.object_id)])

    # register listener for new players
    config_entry.async_on_unload(mass.subscribe(handle_player_added, EventType.PLAYER_ADDED))
    # add all current players
    for player in mass.players:
        added_ids.add(player.player_id)
        async_add_entities([MassPlayer(mass, player.player_id)])


class MassPlayer(MassBaseEntity, MediaPlayerEntity):
    """Representation of MediaPlayerEntity from Music Assistant Player."""

    _attr_name = None

    def __init__(self, mass: MusicAssistantClient, player_id: str) -> None:
        """Initialize MediaPlayer entity."""
        super().__init__(mass, player_id)
        self._attr_media_image_remotely_accessible = True
        self._attr_supported_features = SUPPORTED_FEATURES
        self._attr_device_class = MediaPlayerDeviceClass.SPEAKER
        self._attr_media_position_updated_at = None
        self._attr_media_position = None
        self._attr_media_duration = None
        self._attr_media_album_artist = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_title = None
        self._attr_media_content_id = None
        self._attr_media_content_type = "music"
        self._attr_media_image_url = None
        self._prev_time = 0

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        # we subscribe to player queue time update but we only
        # accept a state change on big time jumps (e.g. seeking)
        async def queue_time_updated(event: MassEvent):
            if event.object_id != self.player.active_source:
                return
            if abs(self._prev_time - event.data) > 5:
                await self.async_on_update()
                self.async_write_ha_state()
            self._prev_time = event.data

        self.async_on_remove(
            self.mass.subscribe(
                queue_time_updated,
                EventType.QUEUE_TIME_UPDATED,
            )
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return additional state attributes."""
        player = self.player
        queue = self.mass.players.get_player_queue(player.active_source)
        return {
            ATTR_MASS_PLAYER_ID: self.player_id,
            ATTR_MASS_PLAYER_TYPE: player.type.value,
            ATTR_GROUP_MEMBERS: player.group_childs,
            ATTR_GROUP_LEADER: player.synced_to,
            ATTR_ACTIVE_QUEUE: player.active_source,
            ATTR_QUEUE_ITEMS: queue.items if queue else None,
            ATTR_QUEUE_INDEX: queue.current_index if queue else None,
        }

    async def async_on_update(self) -> None:
        """Handle player updates."""
        if not self.available:
            return
        player = self.player
        queue = self.mass.players.get_player_queue(player.active_source)
        # update generic attributes
        if player.powered:
            self._attr_state = STATE_MAPPING[self.player.state]
        else:
            self._attr_state = STATE_OFF
        self._attr_app_id = DOMAIN if queue else player.active_source
        self._attr_shuffle = queue.shuffle_enabled if queue else None
        self._attr_repeat = queue.repeat_mode.value if queue else None
        self._attr_group_members = player.group_childs
        self._attr_volume_level = player.volume_level / 100
        self._attr_is_volume_muted = player.volume_muted
        if queue is not None:
            self._attr_media_position = queue.elapsed_time
            self._attr_media_position_updated_at = queue.elapsed_time_last_updated
        else:
            self._attr_media_position = player.elapsed_time
            self._attr_media_position_updated_at = player.elapsed_time_last_updated
        self._prev_time = self._attr_media_position
        self._update_media_image_url(queue)
        # update current media item infos
        media_artist = None
        media_album_artist = None
        media_album_name = None
        media_title = player.active_source
        media_content_id = player.current_url
        media_duration = None
        # Music Assistant is the active source and actually has a MediaItem loaded
        if queue and queue.current_item and queue.current_item.media_item:
            media_item = queue.current_item.media_item
            media_title = media_item.name
            media_content_id = queue.current_item.uri
            media_duration = queue.current_item.duration
            if media_item.media_type == MediaType.TRACK:
                media_artist = ", ".join([x.name for x in media_item.artists])
                if media_item.version:
                    media_title += f" ({media_item.version})"
                if media_item.album:
                    media_album_name = media_item.album.name
                    if getattr(media_item.album, "artist", None):
                        media_album_artist = media_item.album.artist.name
        # set the attributes
        self._attr_media_artist = media_artist
        self._attr_media_album_artist = media_album_artist
        self._attr_media_album_name = media_album_name
        self._attr_media_title = media_title
        self._attr_media_content_id = media_content_id
        self._attr_media_duration = media_duration

    def _update_media_image_url(self, queue: PlayerQueue) -> None:
        """Update image URL forthe active queue item."""
        if queue is None or queue.current_item is None:
            self._attr_media_image_url = None
            return
        if image := queue.current_item.image:
            self._attr_media_image_remotely_accessible = image.provider == "url"
            self._attr_media_image_url = self.mass.get_image_url(image)

    async def async_media_play(self) -> None:
        """Send play command to device."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_play(queue.queue_id)
        else:
            await self.mass.players.queue_command_play(self.player_id)

    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_pause(queue.queue_id)
        else:
            await self.mass.players.queue_command_pause(self.player_id)

    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_stop(queue.queue_id)
        else:
            await self.mass.players.queue_command_stop(self.player_id)

    async def async_media_next_track(self) -> None:
        """Send next track command to device."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_next(queue.queue_id)
        else:
            await self.mass.players.queue_command_next(self.player_id)

    async def async_media_previous_track(self) -> None:
        """Send previous track command to device."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_previous(queue.queue_id)
        else:
            await self.mass.players.queue_command_previous(self.player_id)

    async def async_media_seek(self, position: int) -> None:
        """Send seek command."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_seek(queue.queue_id, position)
        else:
            await self.mass.players.queue_command_seek(self.player_id, position)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.mass.players.player_command_volume_mute(self.player_id, mute)

    async def async_set_volume_level(self, volume: float) -> None:
        """Send new volume_level to device."""
        volume = int(volume * 100)
        await self.mass.players.player_command_volume_set(self.player_id, volume)

    async def async_volume_up(self) -> None:
        """Send new volume_level to device."""
        await self.mass.players.player_command_volume_up(self.player_id)

    async def async_volume_down(self) -> None:
        """Send new volume_level to device."""
        await self.mass.players.player_command_volume_down(self.player_id)

    async def async_turn_on(self) -> None:
        """Turn on device."""
        await self.mass.players.player_command_power(self.player_id, True)

    async def async_turn_off(self) -> None:
        """Turn off device."""
        await self.mass.players.player_command_power(self.player_id, False)

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle state."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_shuffle(queue.queue_id, shuffle)
        else:
            await self.mass.players.queue_command_shuffle(self.player_id, shuffle)

    async def async_set_repeat(self, repeat: str) -> None:
        """Set repeat state."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_repeat(queue.queue_id, RepeatMode(repeat))
        else:
            await self.mass.players.queue_command_repeat(self.player_id, RepeatMode(repeat))

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.queue_command_clear(queue.queue_id)
        else:
            await self.mass.players.queue_command_clear(self.player_id)

    async def async_play_media(
        self,
        media_type: str,  # noqa: ARG002
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,  # noqa: ARG002
        **kwargs: Any,
    ) -> None:
        """Send the play_media command to the media player."""
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url
            media_id = async_process_play_media_url(self.hass, media_id)
        # try to handle playback of item by name
        elif "://" not in media_id and (item := await get_item_by_name(self.mass, media_id)):
            media_id = item.uri

        queue_opt = QUEUE_OPTION_MAP.get(enqueue, QueueOption.PLAY)
        radio_mode = kwargs.get("radio_mode") or kwargs.get("extra", {}).get("radio_mode") or False

        if queue := self.mass.players.get_player_queue(self.player.active_source):
            await self.mass.players.play_media(queue.queue_id, media_id, queue_opt, radio_mode)
        else:
            await self.mass.players.play_media(self.player_id, media_id, queue_opt, radio_mode)

        # announce/alert support
        # is_tts = "/api/tts_proxy" in media_id
        # if announce or is_tts:
        #     self.hass.create_task(
        #         self.player.active_queue.play_announcement(media_id, is_tts)
        #     )
        # else:
        #     await self.player.active_queue.play_media(media_id, queue_opt)

    async def async_browse_media(
        self, media_content_type=None, media_content_id=None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await async_browse_media(self.hass, self.mass, media_content_id, media_content_type)
