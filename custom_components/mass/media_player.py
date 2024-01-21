"""MediaPlayer platform for Music Assistant integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import media_source
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback, async_get_current_platform
from music_assistant.common.helpers.datetime import from_utc_timestamp
from music_assistant.common.models.enums import (
    EventType,
    MediaType,
    PlayerFeature,
    PlayerState,
    QueueOption,
    RepeatMode,
)
from music_assistant.common.models.errors import MediaNotFoundError
from music_assistant.common.models.event import MassEvent
from music_assistant.common.models.media_items import MediaItemType

from .const import (
    ATTR_ACTIVE_QUEUE,
    ATTR_GROUP_LEADER,
    ATTR_GROUP_MEMBERS,
    ATTR_MASS_PLAYER_ID,
    ATTR_MASS_PLAYER_TYPE,
    ATTR_QUEUE_INDEX,
    ATTR_QUEUE_ITEMS,
    ATTR_STREAM_TITLE,
    DOMAIN,
)
from .entity import MassBaseEntity
from .helpers import get_mass
from .media_browser import async_browse_media

if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient
    from music_assistant.common.models.player_queue import PlayerQueue

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.MEDIA_ENQUEUE
    | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
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

SERVICE_PLAY_MEDIA_ADVANCED = "play_media"
ATTR_RADIO_MODE = "radio_mode"
ATTR_MEDIA_ID = "media_id"
ATTR_MEDIA_TYPE = "media_type"
ATTR_ARTIST = "artist"
ATTR_ALBUM = "album"

# pylint: disable=too-many-public-methods


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

    # add platform service for play_media with advanced options
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            vol.Required(ATTR_MEDIA_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_MEDIA_TYPE): vol.Coerce(MediaType),
            vol.Exclusive(ATTR_MEDIA_ENQUEUE, "enqueue_announce"): vol.Coerce(QueueOption),
            vol.Exclusive(ATTR_MEDIA_ANNOUNCE, "enqueue_announce"): cv.boolean,
            vol.Optional(ATTR_ARTIST): cv.string,
            vol.Optional(ATTR_ALBUM): cv.string,
            vol.Optional(ATTR_RADIO_MODE): vol.Coerce(bool),
        },
        "_async_play_media_advanced",
    )


class MassPlayer(MassBaseEntity, MediaPlayerEntity):
    """Representation of MediaPlayerEntity from Music Assistant Player."""

    # pylint: disable=W0223

    _attr_name = None

    def __init__(self, mass: MusicAssistantClient, player_id: str) -> None:
        """Initialize MediaPlayer entity."""
        super().__init__(mass, player_id)
        self._attr_media_image_remotely_accessible = True
        self._attr_supported_features = SUPPORTED_FEATURES
        if PlayerFeature.SYNC in self.player.supported_features:
            self._attr_supported_features |= MediaPlayerEntityFeature.GROUPING
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
        # we need to get the hass object in order to get our config entry
        # and expose the player to the conversation component, assuming that
        # the config entry has the option enabled.
        await self._expose_players_assist()

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
        attrs = {
            ATTR_MASS_PLAYER_ID: self.player_id,
            ATTR_MASS_PLAYER_TYPE: player.type.value,
            ATTR_GROUP_MEMBERS: player.group_childs,
            ATTR_GROUP_LEADER: player.synced_to,
            ATTR_ACTIVE_QUEUE: player.active_source,
            ATTR_QUEUE_ITEMS: queue.items if queue else None,
            ATTR_QUEUE_INDEX: queue.current_index if queue else None,
        }
        # add optional stream_title for radio streams
        if (
            queue
            and queue.current_item
            and queue.current_item.streamdetails
            and queue.current_item.streamdetails.stream_title
        ):
            attrs[ATTR_STREAM_TITLE] = queue.current_item.streamdetails.stream_title
        elif (
            queue
            and queue.current_item
            and queue.current_item.media_type == MediaType.RADIO
            and queue.current_item.media_item
            and queue.current_item.media_item.metadata
        ):
            attrs[ATTR_STREAM_TITLE] = queue.current_item.media_item.metadata.description
        return attrs

    async def async_on_update(self) -> None:
        """Handle player updates."""
        # ruff: noqa: PLR0915
        # pylint: disable=too-many-statements
        if not self.available:
            return
        player = self.player
        queue = self.mass.players.get_player_queue(player.active_source)
        # update generic attributes
        if player.powered:
            self._attr_state = STATE_MAPPING[self.player.state]
        else:
            self._attr_state = STATE_OFF
        self._attr_group_members = player.group_childs
        self._attr_volume_level = player.volume_level / 100
        self._attr_is_volume_muted = player.volume_muted
        if queue is not None:
            # player has MA as active source (either a group player or the players own queue)
            self._attr_app_id = DOMAIN
            self._attr_shuffle = queue.shuffle_enabled
            self._attr_repeat = queue.repeat_mode.value
            self._attr_media_position = queue.elapsed_time
            self._attr_media_position_updated_at = from_utc_timestamp(
                queue.elapsed_time_last_updated
            )
            self._prev_time = queue.elapsed_time
        else:
            # player has some external source active
            self._attr_app_id = player.active_source
            self._attr_shuffle = None
            self._attr_repeat = None
            self._attr_media_position = player.elapsed_time
            self._attr_media_position_updated_at = from_utc_timestamp(
                player.elapsed_time_last_updated
            )
            self._prev_time = player.elapsed_time
        self._attr_source = player.active_source
        self._update_media_image_url(queue)
        # update current media item infos
        media_artist = None
        media_album_artist = None
        media_album_name = None
        media_title = player.active_source
        media_content_id = player.current_item_id
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
                    if album_artists := getattr(media_item.album, "artists", None):
                        media_album_artist = ", ".join([x.name for x in album_artists])
        # set the attributes
        self._attr_media_artist = media_artist
        self._attr_media_album_artist = media_album_artist
        self._attr_media_album_name = media_album_name
        self._attr_media_title = media_title
        self._attr_media_content_id = media_content_id
        self._attr_media_duration = media_duration

    def _update_media_image_url(self, queue: PlayerQueue | None) -> None:
        """Update image URL for the active queue item."""
        if queue is None or queue.current_item is None:
            self._attr_media_image_url = None
            return
        if image := queue.current_item.image:
            self._attr_media_image_remotely_accessible = image.provider == "url"
            self._attr_media_image_url = self.mass.get_image_url(image)
            return
        self._attr_media_image_url = None

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

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        position = int(position)
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
        media_type: str,
        media_id: str | list[str],
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the play_media command to the media player."""
        if isinstance(media_id, str) and media_source.is_media_source_id(media_id):
            # Handle media_source
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url
            media_id = async_process_play_media_url(self.hass, media_id)

        # forward to our advanced play_media handler
        await self._async_play_media_advanced(
            media_id=media_id if isinstance(media_id, list) else [media_id],
            enqueue=enqueue,
            announce=announce,
            media_type=media_type,
            radio_mode=kwargs[ATTR_MEDIA_EXTRA].get(ATTR_RADIO_MODE),
        )

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        async with asyncio.TaskGroup() as tg:
            for child_entity_id in group_members:
                # resolve HA entity_id to MA player_id
                if (hass_state := self.hass.states.get(child_entity_id)) is None:
                    continue
                if (mass_player_id := hass_state.attributes.get("mass_player_id")) is None:
                    continue
                tg.create_task(
                    self.mass.players.player_command_sync(mass_player_id, self.player_id)
                )

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        await self.mass.players.player_command_unsync(self.player_id)

    async def _async_play_media_advanced(
        self,
        media_id: list[str],
        artist: str | None = None,
        album: str | None = None,
        enqueue: MediaPlayerEnqueue | QueueOption | None = QueueOption.PLAY,
        announce: bool | None = None,  # noqa: ARG002
        radio_mode: bool | None = None,
        media_type: str | None = None,
    ) -> None:
        """Send the play_media command to the media player."""
        # pylint: disable=too-many-arguments
        media_uris: list[str] = []
        # work out (all) uri(s) to play
        for media_id_str in media_id:
            # prefer URI format
            if "://" in media_id_str:
                media_uris.append(media_id_str)
                continue
            # try content id as library id
            if media_type and media_id_str.isnumeric():
                with suppress(MediaNotFoundError):
                    item = await self.mass.music.get_item(media_type, media_id_str, "library")
                    media_uris.append(item.uri)
                    continue
            # lookup by name
            if item := await self._get_item_by_name(media_id_str, artist, album, media_type):
                media_uris.append(item.uri)

        if not media_uris:
            raise MediaNotFoundError(f"Could not resolve {media_id} to playable media item")

        # determine active queue to send the play request to
        if queue := self.mass.players.get_player_queue(self.player.active_source):
            queue_id = queue.queue_id
        else:
            queue_id = self.player_id

        # announce/alert support (WIP)
        if announce and radio_mode:
            radio_mode = None
        if announce is None and "/api/tts_proxy" in media_id:
            announce = True
        if announce:
            raise NotImplementedError("Music Assistant does not yet support announcements")

        await self.mass.players.play_media(
            queue_id, media=media_uris, option=enqueue, radio_mode=radio_mode
        )

    async def async_browse_media(
        self, media_content_type=None, media_content_id=None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await async_browse_media(self.hass, self.mass, media_content_id, media_content_type)

    async def _get_item_by_name(
        self,
        name: str,
        artist: str | None = None,
        album: str | None = None,
        media_type: str | None = None,
    ) -> MediaItemType | None:
        """Try to find a media item (such as a playlist) by name."""
        # pylint: disable=too-many-nested-blocks
        searchname = name.lower()
        library_functions = [
            x
            for x in (
                self.mass.music.get_library_playlists,
                self.mass.music.get_library_radios,
                self.mass.music.get_library_tracks,
                self.mass.music.get_library_albums,
                self.mass.music.get_library_artists,
            )
            if not media_type or media_type.lower() in x.__name__
        ]
        # prefer (exact) lookup in the library by name
        for func in library_functions:
            result = await func(search=searchname)
            for item in result.items:
                # handle optional artist filter
                if (
                    artist
                    and (artists := getattr(item, "artists", None))
                    and not any(x for x in artists if x.name.lower() == artist.lower())
                ):
                    continue
                # handle optional album filter
                if (
                    album
                    and (item_album := getattr(item, "album", None))
                    and item_album.name.lower() != album.lower()
                ):
                    continue
                if searchname == item.name.lower():
                    return item
        # nothing found in the library, fallback to global search
        search_name = name
        if album and artist:
            search_name = f"{artist} - {album} - {name}"
        elif album:
            search_name = f"{album} - {name}"
        elif artist:
            search_name = f"{artist} - {name}"
        result = await self.mass.music.search(
            search_query=search_name,
            media_types=[media_type] if media_type else MediaType.ALL,
            limit=5,
        )
        for results in (
            result.tracks,
            result.albums,
            result.playlists,
            result.artists,
            result.radio,
        ):
            for item in results:
                # simply return the first item because search is already sorted by best match
                return item
        return None

    async def _expose_players_assist(self) -> None:
        """Get the correct config entry."""
        hass = self.hass
        config_entries = hass.config_entries.async_entries(DOMAIN)
        for config_entry in config_entries:
            if config_entry.state == ConfigEntryState.SETUP_IN_PROGRESS and config_entry.data.get(
                "expose_players_assist"
            ):
                async_expose_entity(hass, "conversation", self.entity_id, True)
