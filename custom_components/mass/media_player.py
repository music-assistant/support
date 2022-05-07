"""MediaPlayer platform for Music Assistant integration."""
from __future__ import annotations

from typing import Any, Mapping

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ENQUEUE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow
from music_assistant import MusicAssistant
from music_assistant.constants import EventType, MassEvent
from music_assistant.helpers.images import get_image_url
from music_assistant.models.media_items import MediaType
from music_assistant.models.player import Player, PlayerState
from music_assistant.models.player_queue import QueueOption, RepeatMode

from .const import (
    ATTR_ACTIVE_QUEUE,
    ATTR_GROUP_CHILDS,
    ATTR_GROUP_PARENTS,
    ATTR_IS_GROUP,
    ATTR_QUEUE_ITEMS,
    ATTR_SOURCE_ENTITY_ID,
    DOMAIN,
)
from .entity import MassBaseEntity

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
)

STATE_MAPPING = {
    PlayerState.OFF: STATE_OFF,
    PlayerState.IDLE: STATE_IDLE,
    PlayerState.PLAYING: STATE_PLAYING,
    PlayerState.PAUSED: STATE_PAUSED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Music Assistant MediaPlayer(s) from Config Entry."""
    mass: MusicAssistant = hass.data[DOMAIN]
    added_ids = set()

    async def async_add_player(event: MassEvent) -> None:
        """Add MediaPlayerEntity from Music Assistant Player."""
        if event.object_id in added_ids:
            return
        added_ids.add(event.object_id)
        async_add_entities([MassPlayer(mass, event.data)])

    # register listener for new players
    config_entry.async_on_unload(
        mass.subscribe(async_add_player, EventType.PLAYER_ADDED)
    )

    # add all current items in controller
    for player in mass.players:
        await async_add_player(
            MassEvent(EventType.PLAYER_ADDED, object_id=player.player_id, data=player)
        )


class MassPlayer(MassBaseEntity, MediaPlayerEntity):
    """Representation of MediaPlayerEntity from Music Assistant Player."""

    def __init__(self, mass: MusicAssistant, player: Player) -> None:
        """Initialize MediaPlayer entity."""
        super().__init__(mass, player)
        # prefix suggested/default entity_id with 'mass'
        self.entity_id = f'media_player.mass_{player.player_id.split(".")[-1]}'
        self._attr_supported_features = SUPPORTED_FEATURES
        self._attr_device_class = MediaPlayerDeviceClass.SPEAKER
        self._attr_media_position_updated_at = None
        self._attr_media_position = None
        self._attr_media_album_artist = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_title = None
        self._attr_media_content_id = None
        self._attr_media_content_type = None
        self._attr_media_image_url = None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return additional state attributes."""
        return {
            ATTR_SOURCE_ENTITY_ID: self.player.player_id,  # player_id = entity_id of HA source entity
            ATTR_IS_GROUP: self.player.is_group,
            ATTR_GROUP_CHILDS: self.player.group_childs,
            ATTR_GROUP_PARENTS: self.player.group_parents,
            ATTR_ACTIVE_QUEUE: self.player.active_queue.queue_id,
            ATTR_QUEUE_ITEMS: len(self.player.active_queue.items),
        }

    @property
    def group_members(self) -> list[str]:
        """Return group members of this group player."""
        return self.player.group_childs

    @property
    def volume_level(self) -> float:
        """Return current volume level."""
        return self.player.volume_level / 100

    @property
    def state(self) -> str:
        """Return current state."""
        if not self.player.powered:
            return STATE_OFF
        return STATE_MAPPING[self.player.state]

    @property
    def shuffle(self) -> bool:
        """Return if shuffle is enabled."""
        return self.player.active_queue.settings.shuffle_enabled

    @property
    def repeat(self) -> str:
        """Return current repeat mode."""
        return self.player.active_queue.settings.repeat_mode.value

    @property
    def media_duration(self) -> int | None:
        """Return duration of current item in queue."""
        if self.player.active_queue.current_item is None:
            return None
        return self.player.active_queue.current_item.duration

    async def async_on_update(self) -> None:
        """Handle player updates."""
        self._attr_media_position = self.player.active_queue.elapsed_time
        self._attr_media_position_updated_at = utcnow()
        # update current media item infos
        artist = None
        album_artist = None
        album_name = None
        media_title = None
        content_id = None
        content_type = None
        image_url = None
        current_item = self.player.active_queue.current_item
        if (
            self.player.active_queue.active
            and current_item
            and current_item.is_media_item
        ):
            media_item = await self.mass.music.get_item_by_uri(current_item.uri)
            media_title = media_item.name
            content_id = current_item.uri
            content_type = media_item.media_type.value
            image_url = await get_image_url(self.mass, media_item)
            if media_item.media_type == MediaType.TRACK:
                artist = ", ".join([x.name for x in media_item.artists])
                if media_item.version:
                    media_title += f" ({media_item.version})"
                if media_item.album:
                    album_name = media_item.album.name
                    album_artist = media_item.album.artist.name
        elif current_item and not current_item.is_media_item:
            media_title = current_item.name
            content_type = "music"
        elif (
            not self.player.active_queue.active
            and self.player.state in [PlayerState.PLAYING, PlayerState.PAUSED]
            and self.player.current_url
        ):
            media_title = self.player.current_url
            content_type = "music"
        # set the attributes
        self._attr_media_artist = artist
        self._attr_media_album_artist = album_artist
        self._attr_media_album_name = album_name
        self._attr_media_title = media_title
        self._attr_media_content_id = content_id
        self._attr_media_content_type = content_type
        self._attr_media_image_url = image_url

    async def async_media_play(self) -> None:
        """Send play command to device."""
        await self.player.active_queue.play()

    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.player.active_queue.pause()

    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        await self.player.active_queue.stop()

    async def async_media_next_track(self) -> None:
        """Send next track command to device."""
        await self.player.active_queue.next()

    async def async_media_previous_track(self) -> None:
        """Send previous track command to device."""
        await self.player.active_queue.previous()

    async def async_set_volume_level(self, volume: float) -> None:
        """Send new volume_level to device."""
        volume = int(volume * 100)
        await self.player.volume_set(volume)

    async def async_volume_up(self) -> None:
        """Send new volume_level to device."""
        await self.player.volume_up()

    async def async_volume_down(self) -> None:
        """Send new volume_level to device."""
        await self.player.volume_down()

    async def async_turn_on(self) -> None:
        """Turn on device."""
        await self.player.power(True)

    async def async_turn_off(self) -> None:
        """Turn off device."""
        await self.player.power(False)

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle state."""
        self.player.active_queue.settings.shuffle_enabled = shuffle

    async def async_set_repeat(self, repeat: str) -> None:
        """Set repeat state."""
        self.player.active_queue.settings.repeat_mode = RepeatMode(repeat)

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self.player.active_queue.clear()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs) -> None:
        """Send the play_media command to the media player."""
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(self.hass, media_id)
            media_id = sourced_media.url

        queue_opt = (
            QueueOption.ADD if kwargs.get(ATTR_MEDIA_ENQUEUE) else QueueOption.PLAY
        )
        await self.player.active_queue.play_media(media_id, queue_opt)

    async def async_browse_media(
        self, media_content_type=None, media_content_id=None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/")
            or item.media_content_type == DOMAIN,
        )
