"""MediaPlayer platform for Music Assistant integration."""
from __future__ import annotations

from typing import Any, Mapping

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
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
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow
from music_assistant import MusicAssistant
from music_assistant.models.enums import EventType
from music_assistant.models.event import MassEvent
from music_assistant.models.media_items import MediaType
from music_assistant.models.player import Player, PlayerState
from music_assistant.models.player_queue import QueueOption, RepeatMode

from .const import (
    ATTR_ACTIVE_QUEUE,
    ATTR_GROUP_LEADER,
    ATTR_GROUP_MEMBERS,
    ATTR_IS_GROUP,
    ATTR_QUEUE_INDEX,
    ATTR_QUEUE_ITEMS,
    ATTR_SOURCE_ENTITY_ID,
    CONF_PLAYER_ENTITIES,
    DEFAULT_NAME,
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
    | SUPPORT_SEEK
    | SUPPORT_VOLUME_MUTE
)

STATE_MAPPING = {
    PlayerState.OFF: STATE_OFF,
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
    mass: MusicAssistant = hass.data[DOMAIN]
    allowed_players = config_entry.options.get(CONF_PLAYER_ENTITIES, [])
    added_ids = set()

    async def async_add_player(event: MassEvent) -> None:
        """Add MediaPlayerEntity from Music Assistant Player."""
        if event.object_id in added_ids:
            return
        if event.object_id not in allowed_players:
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
            if event.object_id != self.player.active_queue.queue_id:
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
        return {
            ATTR_SOURCE_ENTITY_ID: self.player.player_id,  # player_id = entity_id of HA source entity
            ATTR_IS_GROUP: self.player.is_group,
            ATTR_GROUP_MEMBERS: self.player.group_members,
            ATTR_GROUP_LEADER: self.player.group_leader,
            ATTR_ACTIVE_QUEUE: self.player.active_queue.queue_id,
            ATTR_QUEUE_ITEMS: len(self.player.active_queue.items),
            ATTR_QUEUE_INDEX: self.player.active_queue.current_index,
        }

    @property
    def group_members(self) -> list[str]:
        """Return group members of this group player."""
        return self.player.group_members

    @property
    def volume_level(self) -> float:
        """Return current volume level."""
        return self.player.volume_level / 100

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self.player.volume_muted

    @property
    def state(self) -> str:
        """Return current state."""
        if not self.player.powered:
            return STATE_OFF
        return STATE_MAPPING[self.player.state]

    @property
    def shuffle(self) -> bool:
        """Return if shuffle is enabled."""
        if self.player.active_queue.active:
            return self.player.active_queue.settings.shuffle_enabled
        return self.hass.states.get(self.player.player_id).attributes.get(
            ATTR_MEDIA_SHUFFLE, False
        )

    @property
    def repeat(self) -> str:
        """Return current repeat mode."""
        if self.player.active_queue.active:
            return self.player.active_queue.settings.repeat_mode.value
        return self.hass.states.get(self.player.player_id).attributes.get(
            ATTR_MEDIA_REPEAT, False
        )

    @property
    def app_id(self) -> str:
        """Return current app_id."""
        if self.player.active_queue.active:
            return DOMAIN
        return self.hass.states.get(self.player.player_id).attributes.get(
            ATTR_APP_ID, self.player.player_id
        )

    @property
    def app_name(self) -> str:
        """Return current app_name."""
        if self.player.active_queue.active:
            return DEFAULT_NAME
        return self.hass.states.get(self.player.player_id).attributes.get(
            ATTR_APP_NAME, self.player.name
        )

    async def async_on_update(self) -> None:
        """Handle player updates."""
        if not self.available:
            return
        self._attr_media_position = self.player.active_queue.elapsed_time
        self._attr_media_position_updated_at = utcnow()
        self._prev_time = self.player.active_queue.elapsed_time
        # update current media item infos
        media_artist = None
        media_album_artist = None
        media_album_name = None
        media_title = None
        media_content_id = None
        media_image_url = None
        media_duration = None
        current_item = self.player.active_queue.current_item
        # Music Assistant is the active source and actually has a MediaItem loaded
        if self.player.active_queue.active and current_item and current_item.media_item:
            media_item = current_item.media_item
            media_title = media_item.name
            media_content_id = current_item.uri
            media_duration = current_item.duration
            media_image_url = current_item.image.url
            if media_item.media_type == MediaType.TRACK:
                media_artist = ", ".join([x.name for x in media_item.artists])
                if media_item.version:
                    media_title += f" ({media_item.version})"
                if media_item.album:
                    media_album_name = media_item.album.name
                    if getattr(media_item.album, "artist", None):
                        media_album_artist = media_item.album.artist.name
        # Music Assistant is NOT the active source
        elif not self.player.active_queue.active:
            # grab details from 'origin' media player
            source_entity = self.hass.states.get(self.player.player_id)
            attrs = source_entity.attributes
            media_artist = attrs.get(ATTR_MEDIA_ARTIST)
            media_album_artist = attrs.get(ATTR_MEDIA_ALBUM_ARTIST)
            media_album_name = attrs.get(ATTR_MEDIA_ALBUM_NAME)
            media_title = attrs.get(ATTR_MEDIA_TITLE)
            media_content_id = attrs.get(ATTR_MEDIA_CONTENT_ID)
            media_image_url = attrs.get(ATTR_ENTITY_PICTURE)
            media_duration = attrs.get(ATTR_MEDIA_DURATION)
        # Music Assistant is active but not playing MediaItem (e.g. manual URL/TTS etc.)
        elif current_item and not current_item.media_item:
            media_title = current_item.name
            media_image_url = current_item.image
            media_duration = current_item.duration
        # set the attributes
        self._attr_media_artist = media_artist
        self._attr_media_album_artist = media_album_artist
        self._attr_media_album_name = media_album_name
        self._attr_media_title = media_title
        self._attr_media_content_id = media_content_id
        self._attr_media_image_url = media_image_url
        self._attr_media_duration = media_duration

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        if not self.player.active_queue.active:
            return True
        return self.media_image_url is None or self.media_image_url.startswith("https")

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing image."""
        if not self.media_image_remotely_accessible:
            img_data = await self.mass.metadata.get_thumbnail(self.media_image_url)
            return (img_data, "image/png")
        return await super().async_get_media_image()

    async def async_media_play(self) -> None:
        """Send play command to device."""
        await self.player.active_queue.play()

    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.player.active_queue.pause()

    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        if not self.player.active_queue.active:
            # directly control source player if queue is not loaded/active
            await self.player.stop()
            return
        await self.player.active_queue.stop()

    async def async_media_next_track(self) -> None:
        """Send next track command to device."""
        if not self.player.active_queue.active:
            # directly control source player if queue is not loaded/active
            await self.player.next_track()
            return
        await self.player.active_queue.next()

    async def async_media_previous_track(self) -> None:
        """Send previous track command to device."""
        if not self.player.active_queue.active:
            # directly control source player if queue is not loaded/active
            await self.player.previous_track()
            return
        await self.player.active_queue.previous()

    async def async_media_seek(self, position: int) -> None:
        """Send seek command."""
        await self.player.active_queue.seek(position)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.player.volume_mute(mute)

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

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
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

        queue_opt = QUEUE_OPTION_MAP.get(enqueue, QueueOption.PLAY)

        # announce/alert support
        is_tts = "/api/tts_proxy" in media_id
        if announce or is_tts:
            self.hass.create_task(
                self.player.active_queue.play_announcement(media_id, is_tts)
            )
        else:
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
