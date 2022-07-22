"""Support Home Assistant media_player entities to be used as Players for Music Assistant."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.event import Event
from homeassistant.util.dt import utcnow
from music_assistant import MusicAssistant
from music_assistant.models.enums import ContentType
from music_assistant.models.player import DeviceInfo, Player, PlayerState

from .const import (
    ATTR_SOURCE_ENTITY_ID,
    BLACKLIST_DOMAINS,
    CONF_PLAYER_ENTITIES,
    DEFAULT_NAME,
    DLNA_DOMAIN,
    DOMAIN,
    ESPHOME_DOMAIN,
    GROUP_DOMAIN,
    KODI_DOMAIN,
    SLIMPROTO_DOMAIN,
    SLIMPROTO_EVENT,
    SONOS_DOMAIN,
    VOLUMIO_DOMAIN,
)

LOGGER = logging.getLogger(__name__)

OFF_STATES = (STATE_OFF, STATE_UNAVAILABLE, STATE_STANDBY)
CAST_DOMAIN = "cast"
CAST_MULTIZONE_MANAGER_KEY = "cast_multizone_manager"


STATE_MAPPING = {
    STATE_OFF: PlayerState.OFF,
    STATE_ON: PlayerState.IDLE,
    STATE_UNKNOWN: PlayerState.IDLE,
    STATE_UNAVAILABLE: PlayerState.OFF,
    STATE_IDLE: PlayerState.IDLE,
    STATE_PLAYING: PlayerState.PLAYING,
    STATE_PAUSED: PlayerState.PAUSED,
    STATE_STANDBY: PlayerState.OFF,
}


def get_source_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Return source entity_id from child entity_id."""
    if hass_state := hass.states.get(entity_id):
        # if entity is actually already mass entity, return the source entity
        if source_id := hass_state.attributes.get(ATTR_SOURCE_ENTITY_ID):
            return source_id
    return entity_id


class HassPlayer(Player):
    """Generic/base Mapping from Home Assistant Mediaplayer to Music Assistant Player."""

    _attr_use_mute_as_power: bool = False

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize player."""
        self.hass = hass
        self.logger = LOGGER.getChild(entity_id)
        # use the (source) entity_id as player_id for now, to be improved later with unique_id ?
        self.player_id = entity_id
        self.entity_id = entity_id

        # grab a reference to the underlying entity
        # we perform all logic directly on the entity instance and bypass the state machine
        entity_comp = hass.data.get(DATA_INSTANCES, {}).get(MP_DOMAIN)
        self.entity: MediaPlayerEntity = entity_comp.get_entity(entity_id)

        manufacturer = "Home Assistant"
        model = entity_id
        if reg_entry := self.entity.registry_entry:
            # grab device entry
            if reg_entry.device_id:
                dev_reg = dr.async_get(hass)
                device = dev_reg.async_get(reg_entry.device_id)
                manufacturer = device.manufacturer
                model = device.model
        self._attr_device_info = DeviceInfo(manufacturer=manufacturer, model=model)
        self._attr_powered = False
        self._attr_current_url = ""
        self._attr_elapsed_time = 0
        self.on_update()

    @property
    def name(self) -> str:
        """Return player name."""
        if reg_entry := self.entity.registry_entry:
            return reg_entry.name or self.entity.name
        return self.entity_id

    @property
    def support_power(self) -> bool:
        """Return if this player supports power commands."""
        return bool(self.entity.supported_features & SUPPORT_TURN_ON) and bool(
            self.entity.supported_features & SUPPORT_TURN_OFF
        )

    @property
    def powered(self) -> bool:
        """Return bool if this player is currently powered on."""
        if not self.available:
            return False
        if self._attr_use_mute_as_power:
            return not self.volume_muted
        if self.support_power:
            return self.entity.state not in OFF_STATES
        return self._attr_powered

    @property
    def elapsed_time(self) -> float:
        """Return elapsed time of current playing media in seconds."""
        if not self.available:
            return 0
        # we need to return the corrected time here
        extra_attr = self.entity.extra_state_attributes or {}
        media_position = extra_attr.get(
            "media_position_mass", self.entity.media_position
        )
        last_upd = self.entity.media_position_updated_at
        if last_upd is None or media_position is None:
            return 0
        diff = (utcnow() - last_upd).seconds
        return media_position + diff

    @property
    def current_url(self) -> str:
        """Return URL that is currently loaded in the player."""
        return self.entity.media_content_id or self._attr_current_url

    @property
    def state(self) -> PlayerState:
        """Return current state of player."""
        if not self.available:
            return PlayerState.OFF
        if not self.powered and not self.is_group_leader:
            return PlayerState.OFF
        if self.entity.state in OFF_STATES and self.powered:
            return PlayerState.IDLE
        return STATE_MAPPING.get(self.entity.state, PlayerState.OFF)

    @property
    def volume_level(self) -> int:
        """Return current volume level of player (scale 0..100)."""
        if not self.available:
            return 0
        if self.entity.support_volume_set:
            return (self.entity.volume_level or 0) * 100
        return 100

    @property
    def volume_muted(self) -> bool:
        """Return current mute mode of player."""
        if not self.available:
            return False
        if self.entity.support_volume_mute:
            return self.entity.is_volume_muted
        return self._attr_volume_muted

    @callback
    def on_hass_event(self, event: Event) -> None:
        """Call on Home Assistant event."""
        self.logger.debug("on_hass_event")
        if event.event_type == "state_changed":
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            if old_state and new_state and old_state.state != new_state.state:
                self.on_state_changed(old_state, new_state)
        self.update_state()

    @callback
    def on_state_changed(self, old_state: State, new_state: State) -> None:
        """Call when state changes from HA player."""
        self.logger.debug(
            "state_changed - old: %s - new: %s",
            old_state.state,
            new_state.state,
        )
        if new_state.state in OFF_STATES:
            self._attr_current_url = None
        if old_state.state == STATE_UNAVAILABLE:
            # make sure we're not talking to an orphan entity instance
            # this may happen is the entity's integration is reloaded.
            entity_comp = self.hass.data.get(DATA_INSTANCES, {}).get(MP_DOMAIN)
            self.entity: MediaPlayerEntity = entity_comp.get_entity(self.entity_id)

    def on_child_update(self, player_id: str, changed_keys: set) -> None:
        """Call when one of the child players of a playergroup updates."""
        self.logger.debug("on_child_update [%s] %s", player_id, changed_keys)
        # power off group player if last child player turns off
        if "powered" in changed_keys and self.active_queue.active:
            powered_childs = set()
            for child_player in self.get_child_players(True):
                if child_player.powered:
                    powered_childs.add(child_player.player_id)
            if len(powered_childs) == 0:
                self.mass.create_task(self.set_group_power(False))
        super().on_child_update(player_id, changed_keys)

    @callback
    def on_update(self) -> None:
        """Update attributes of this player."""
        self._attr_available = self.entity.available
        # figure out grouping support
        group_members = []
        if self.entity.group_members:
            # filter out 'None' for group_members
            group_members = [x for x in self.entity.group_members if x is not None]
        self._attr_group_members = group_members

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        # a lot of players do not power on at playback request so send power on from here
        if not self.powered:
            await self.power(True)
        self.logger.debug("play_url: %s", url)
        self._attr_current_url = url
        await self.entity.async_play_media(
            MEDIA_TYPE_MUSIC,
            url,
        )

    async def stop(self) -> None:
        """Send STOP command to player."""
        if self.is_passive:
            self.logger.debug(
                "stop command ignored: player is passive (not the group leader)"
            )
            return
        self.logger.debug("stop command called")
        self._attr_current_url = None
        await self.entity.async_media_stop()

    async def play(self) -> None:
        """Send PLAY/UNPAUSE command to player."""
        if self.is_passive:
            self.logger.debug(
                "play command ignored: player is passive (not the group leader)"
            )
            return
        self.logger.debug("play")
        await self.entity.async_media_play()

    async def pause(self) -> None:
        """Send PAUSE command to player."""
        if self.is_passive:
            self.logger.debug(
                "pause command ignored: player is passive (not the group leader)"
            )
            return
        if not self.entity.support_pause:
            self.logger.warning("pause not supported, sending STOP instead...")
            await self.stop()
            return
        self.logger.debug("pause command called")
        await self.entity.async_media_pause()

    async def power(self, powered: bool) -> None:
        """Send POWER command to player."""
        self.logger.debug("power command called with value: %s", powered)
        # send stop if this player is active queue
        if (
            not powered
            and self.active_queue.queue_id == self.player_id
            and not self.is_passive
        ):
            await self.active_queue.stop()
        if self._attr_use_mute_as_power:
            await self.volume_mute(not powered)
        elif powered and bool(self.entity.supported_features & SUPPORT_TURN_ON):
            # regular turn_on command
            await self.entity.async_turn_on()
        elif not powered and bool(self.entity.supported_features & SUPPORT_TURN_OFF):
            # regular turn_off command
            await self.entity.async_turn_off()
        # player without power (and mute) support just uses a fake power mode
        self._attr_powered = powered
        self.update_state()

    async def volume_set(self, volume_level: int) -> None:
        """Send volume level (0..100) command to player."""
        if not self.entity.support_volume_set:
            self.logger.debug("ignore volume_set as it is not supported")
            return
        self.logger.debug("volume_set command called with value: %s", volume_level)
        await self.entity.async_set_volume_level(volume_level / 100)

    async def volume_mute(self, muted: bool) -> None:
        """Send volume mute command to player."""
        self.logger.debug("volume_mute command called with value: %s", muted)
        supports_mute = bool(self.entity.supported_features & SUPPORT_VOLUME_MUTE)
        if not supports_mute:
            # for players that do not support mute, we fake mute with volume
            await super().volume_mute(muted)
            return
        await self.entity.async_mute_volume(muted)
        # some players do not update when we send mute (e.g. cast)
        # try to handle that here by just setting the local variable
        # for a more or less optimistic state
        # pylint: disable=protected-access
        self.entity._attr_is_volume_muted = muted

    async def next_track(self) -> None:
        """Send next_track command to player."""
        self.logger.debug("next_track command called (on source player directly)")
        await self.entity.async_media_next_track()

    async def previous_track(self) -> None:
        """Send previous_track command to player."""
        self.logger.debug("previous_track command called (on source player directly)")
        await self.entity.async_media_previous_track()


class SlimprotoPlayer(HassPlayer):
    """Representation of Hass player from Squeezebox Local integration."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize player."""
        super().__init__(*args, **kwargs)
        self._unsubs = [
            self.hass.bus.async_listen(SLIMPROTO_EVENT, self.on_squeezebox_event)
        ]

    @property
    def elapsed_time(self) -> float:
        """Return elapsed time of current playing media in seconds."""
        # slimproto has very accurate realtime timestamp, prefer that
        return self.entity.player.elapsed_seconds

    @property
    def max_sample_rate(self) -> int:
        """Return the (default) max supported sample rate."""
        return int(self.entity.player.max_sample_rate)

    @property
    def default_stream_type(self) -> ContentType:
        """Return the default content type to use for streaming."""
        if "flac" in self.entity.player.supported_codecs:
            return ContentType.FLAC
        if "wav" in self.entity.player.supported_codecs:
            return ContentType.WAV
        return ContentType.MP3

    @callback
    def on_remove(self) -> None:
        """Call when player is about to be removed (cleaned up) from player manager."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    @callback
    def on_squeezebox_event(self, event: Event) -> None:
        """Handle special events from squeezebox players."""
        print(event)
        if event.data["entity_id"] != self.entity_id:
            return
        cmd = event.data["command_str"]
        if cmd == "playlist index +1":
            self.hass.create_task(self.active_queue.next())
        if cmd == "playlist index -1":
            self.hass.create_task(self.active_queue.previous())


class ESPHomePlayer(HassPlayer):
    """Representation of Hass player from ESPHome integration."""

    _attr_use_mute_as_power: bool = True

    _attr_max_sample_rate: int = 48000
    _attr_stream_type: ContentType = ContentType.MP3
    _attr_media_pos_updated_at: Optional[datetime] = None

    @property
    def elapsed_time(self) -> float:
        """Return elapsed time of current playing media in seconds."""
        if self.state == PlayerState.PLAYING:
            last_upd = self._attr_media_pos_updated_at
            media_pos = self._attr_elapsed_time
            if last_upd is None or media_pos is None:
                return 0
            diff = (utcnow() - last_upd).seconds
            return media_pos + diff
        if self.state == PlayerState.PAUSED:
            return self._attr_elapsed_time
        return 0

    @callback
    def on_state_changed(self, old_state: State, new_state: State) -> None:
        """Call when state changes from HA player."""
        super().on_state_changed(old_state, new_state)
        # TEMP! This needs to be fixed upstream in the ESPHome integration
        old_state = old_state.state
        new_state = new_state.state
        if old_state == STATE_PAUSED and new_state == STATE_PLAYING:
            self._attr_media_pos_updated_at = utcnow()
        elif new_state == STATE_PAUSED:
            last_upd = self._attr_media_pos_updated_at
            media_pos = self._attr_elapsed_time
            if last_upd is not None and media_pos is not None:
                diff = (utcnow() - last_upd).seconds
                self._attr_elapsed_time = media_pos + diff
        elif old_state != STATE_PLAYING and new_state == STATE_PLAYING:
            self._attr_media_pos_updated_at = utcnow()
            self._attr_elapsed_time = 0

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        await super().play_url(url)
        self._attr_media_pos_updated_at = utcnow()
        self._attr_elapsed_time = 0


class KodiPlayer(HassPlayer):
    """Representation of Hass player from Kodi integration."""

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        if self.mass.streams.base_url not in url:
            # use base implementation if 3rd party url provided...
            await super().play_url(url)
            return

        self.logger.debug("play_url: %s", url)
        if not self.powered:
            await self.power(True)

        if self.state in (PlayerState.PLAYING, PlayerState.PAUSED):
            await self.stop()
        self._attr_current_url = url
        # pylint: disable=protected-access
        await self.entity._kodi.play_item({"file": url})


class CastPlayer(HassPlayer):
    """Representation of Hass player from cast integration."""

    _attr_max_sample_rate: int = 96000
    _attr_stream_type: ContentType = ContentType.FLAC
    _attr_use_mute_as_power = True
    _attr_is_group = False

    @property
    def is_group(self) -> bool:
        """Return bool if this player represents a playergroup(leader)."""
        return self._attr_is_group

    @property
    def powered(self) -> bool:
        """Return power state."""
        if self._attr_is_group:
            return self.group_powered
        return super().powered

    @property
    def group_name(self) -> str:
        """Return name of this grouped player."""
        return self.name

    @property
    def group_leader(self) -> str | None:
        """Return the leader's player_id of this playergroup."""
        if not self._attr_is_group:
            return None
        # pylint:disable=protected-access
        ipaddr = self.entity._cast_info.cast_info.host
        for child_player in self.get_child_players():
            if child_player.entity._cast_info.cast_info.host == ipaddr:
                return child_player.player_id
        return None

    @callback
    def on_update(self) -> None:
        """Update attributes of this player."""
        super().on_update()
        self._attr_group_members = group_members = self._get_group_members()
        # a stereo pair is also detected as google cast group
        # only consider this a group if it actually has members
        self._attr_is_group = is_group = len(group_members) > 0
        self._attr_use_mute_as_power = not is_group

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        if self.mass.streams.base_url not in url:
            # use base implementation if 3rd party url provided...
            await super().play_url(url)
            return
        self._attr_powered = True
        if self._attr_use_mute_as_power:
            await self.volume_mute(False)
        # pylint: disable=import-outside-toplevel,protected-access
        from homeassistant.components.cast.media_player import quick_play

        cast = self.entity._chromecast
        app_data = {
            "media_id": url,
            "media_type": f"audio/{self.active_queue.settings.stream_type.value}",
            "enqueue": False,
            "stream_type": "BUFFERED",
            "title": f" Streaming from {DEFAULT_NAME}",
        }
        await self.hass.async_add_executor_job(
            quick_play, cast, "default_media_receiver", app_data
        )
        # enqueue second item to allow on-player control of next
        # (or shout next track from google assistant)
        await asyncio.sleep(1)
        if self.active_queue.stream and len(self.active_queue.items) < 2:
            return
        enqueue_data = {**app_data}
        enqueue_data["enqueue"] = True
        enqueue_data["media_id"] = self.mass.streams.get_control_url(
            self.active_queue.queue_id
        )
        await self.hass.async_add_executor_job(
            quick_play, cast, "default_media_receiver", enqueue_data
        )

    async def volume_set(self, volume_level: int) -> None:
        """Send volume level (0..100) command to player."""
        if self.is_group:
            # redirect to set_group_volume
            await self.set_group_volume(volume_level)
        else:
            await super().volume_set(volume_level)

    async def power(self, powered: bool) -> None:
        """Send volume level (0..100) command to player."""
        if self.is_group:
            # redirect to set_group_power
            await self.set_group_power(powered)
        else:
            await super().power(powered)

    async def set_group_power(self, powered: bool) -> None:
        """Send power command to the group player."""
        # a cast group player is a dedicated player which we need to power off
        if not powered:
            await self.entity.async_turn_off()
        if powered and not self.group_powered:
            # turn on (all) group clients if none are on now
            await super().set_group_power(True)
        else:
            await super().set_group_power(False)

    def _get_group_members(self) -> List[str]:
        """Get list of group members if this group is a cast group."""
        # pylint: disable=protected-access
        if not self.entity._cast_info.is_audio_group:
            return []
        # this is a bit hacky to get the group members
        # TODO: create PR to add these as state attributes to the cast integration

        mz_mgr = self.entity.mz_mgr
        cast_uuid = self.entity.registry_entry.unique_id
        if not mz_mgr or cast_uuid not in mz_mgr._groups:
            return []

        mz_ctrl = mz_mgr._groups[cast_uuid]["listener"]._mz
        child_players = []
        ent_reg = er.async_get(self.hass)
        for member_uuid in mz_ctrl.members:
            if "-" not in member_uuid:
                # yes this can happen when you add a stereo pair to a cast group ?!
                member_uuid = str(UUID(member_uuid))
            if member_uuid == cast_uuid:
                # filter out itself (happens with stereo pairs)
                continue
            if entity_id := ent_reg.entities.get_entity_id(
                (MP_DOMAIN, CAST_DOMAIN, member_uuid)
            ):
                child_players.append(entity_id)
        return child_players


class SonosPlayer(HassPlayer):
    """Representation of Hass player from Sonos integration."""

    _attr_max_sample_rate: int = 48000
    _attr_stream_type: ContentType = ContentType.FLAC
    _attr_use_mute_as_power: bool = True
    _sonos_paused = False

    @property
    def state(self) -> PlayerState:
        """Return current PlayerState of player."""
        # a sonos player is always either playing or paused
        # consider idle if nothing is playing and we did not pause
        if (
            self.powered
            and self.entity.state == STATE_PAUSED
            and not self._sonos_paused
        ):
            return PlayerState.IDLE
        if not self.powered and self.entity.state == STATE_PAUSED:
            return PlayerState.OFF
        return super().state

    async def play(self) -> None:
        """Send PLAY/UNPAUSE command to player."""
        self._sonos_paused = False
        await super().play()

    async def pause(self) -> None:
        """Send PAUSE command to player."""
        self._sonos_paused = True
        await super().pause()

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        self._sonos_paused = False
        if self.mass.streams.base_url not in url:
            # use base implementation if 3rd party url provided...
            await super().play_url(url)
            return

        self._attr_powered = True
        if self._attr_use_mute_as_power:
            await self.volume_mute(False)

        def _play_url():
            soco = self.entity.coordinator.soco
            ext = url.split(".")[-1]
            meta = (
                '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'
                '<item id="1" parentID="0" restricted="1">'
                "<dc:title>Streaming from Music Assistant</dc:title>"
                "<dc:creator></dc:creator>"
                "<upnp:album></upnp:album>"
                "<upnp:channelName>Music Assistant</upnp:channelName>"
                "<upnp:channelNr>0</upnp:channelNr>"
                "<upnp:class>object.item.audioItem.audioBroadcast</upnp:class>"
                f'<res protocolInfo="http-get:*:audio/{ext}:DLNA.ORG_OP=00;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=0d500000000000000000000000000000">{url}</res>'
                "</item>"
                "</DIDL-Lite>"
            )
            # sonos only supports ICY metadata for mp3 streams...
            soco.play_uri(url, meta=meta, force_radio=ext == "mp3")

        await self.hass.loop.run_in_executor(None, _play_url)
        # right after playback is started, sonos returns None for the media_position
        # until a manual poll_media is done
        self.entity.media.position = 0
        self.entity.media.position_updated_at = utcnow()
        await self.schedule_poll(2)
        await self.schedule_poll(5)

    async def schedule_poll(self, delay: float = 0.5) -> None:
        """Schedule a manual poll task of the Sonos to fix elapsed_time."""

        async def poll():
            if not self.entity.speaker.is_coordinator:
                return
            self.logger.debug("poll_media")
            await self.hass.loop.run_in_executor(None, self.entity.media.poll_media)

        self.hass.loop.call_later(delay, self.hass.create_task, poll())


class DlnaPlayer(HassPlayer):
    """Representation of Hass player from DLNA integration."""

    _attr_max_sample_rate: int = 48000
    _attr_stream_type: ContentType = ContentType.MP3

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        if self.mass.streams.base_url not in url:
            # use base implementation if 3rd party url provided...
            await super().play_url(url)
            return

        if not self.powered:
            await self.power(True)
        # pylint: disable=protected-access
        device = self.entity._device
        ext = url.split(".")[-1]
        didl_metadata = (
            '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'
            '<item id="1" parentID="0" restricted="1">'
            "<dc:title>Streaming from Music Assistant</dc:title>"
            "<dc:creator></dc:creator>"
            "<upnp:album></upnp:album>"
            "<upnp:channelName>Music Assistant</upnp:channelName>"
            "<upnp:channelNr>0</upnp:channelNr>"
            "<upnp:class>object.item.audioItem.audioBroadcast</upnp:class>"
            f'<res protocolInfo="http-get:*:audio/{ext}:DLNA.ORG_OP=00;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=0d500000000000000000000000000000">{url}</res>'
            "</item>"
            "</DIDL-Lite>"
        )
        if device.can_stop:
            await self.entity.async_media_stop()

        # Queue media
        self._attr_current_url = url
        await device.async_set_transport_uri(
            url, "Streaming from Music Assistant", didl_metadata
        )

        if self.state == PlayerState.PLAYING:
            return

        await device.async_wait_for_can_play()
        await self.entity.async_media_play()


class HassGroupPlayer(HassPlayer):
    """Mapping from Home Assistant Grouped Mediaplayer to Music Assistant Player."""

    _attr_max_sample_rate: int = 48000
    _attr_stream_type: ContentType = ContentType.FLAC

    def __init__(self, *args, **kwargs) -> None:
        """Initialize player."""
        self._attr_device_info = DeviceInfo(
            manufacturer="Home Assistant", model="Media Player Group"
        )
        super().__init__(*args, **kwargs)

    @property
    def default_stream_type(self) -> ContentType:
        """Return the default content type to use for streaming."""
        # if any of the players supports FLAC, prefer that
        for child_player in self.get_child_players(False, False):
            if child_player.default_stream_type == ContentType.FLAC:
                return ContentType.FLAC
        # fallback to MP3
        return ContentType.MP3

    @property
    def powered(self) -> bool:
        """Return power state."""
        return self.group_powered

    @property
    def state(self) -> PlayerState:
        """Return the state of the grouped player."""
        if not self.powered:
            return PlayerState.OFF
        if not self.active_queue.active:
            return PlayerState.IDLE
        if group_leader := self.mass.players.get_player(self.group_leader):
            return group_leader.state
        return PlayerState.IDLE

    @property
    def is_group(self) -> bool:
        """Return if this player represents a playergroup or is grouped with other players."""
        return True

    @property
    def group_members(self) -> List[str]:
        """Return list of playergroup members."""
        result = []
        if self.mass is None:
            return []
        # pylint: disable=protected-access
        for entity_id in self.entity._entities:
            # make sure we have a source entity_id
            entity_id = get_source_entity_id(self.hass, entity_id)
            if player := self.mass.players.get_player(entity_id):
                player_id = player.player_id
                if player.is_group and player.is_passive:
                    # make sure we add the master player if someone
                    # added a group member into this universal group
                    player_id = player.group_leader
                if player_id in result:
                    # no duplicates please
                    continue
                result.append(player_id)
        return result

    @property
    def group_leader(self) -> str | None:
        """Return the group leader for this player group."""
        for child_player in self.get_child_players(True):
            # simply return the first (non passive) powered child player
            if child_player.is_passive:
                continue
            if not child_player.current_url:
                continue
            if not (self.active_queue and self.active_queue.stream):
                continue
            if self.active_queue.stream.stream_id not in child_player.current_url:
                continue
            return child_player.player_id
        # fallback to the first player
        return self.group_members[0] if self.group_members else None

    @property
    def is_group_leader(self) -> bool:
        """Return if this player is the leader in a playergroup."""
        return False

    @property
    def is_passive(self) -> bool:
        """
        Return if this player may not accept any playback related commands.

        Usually this means the player is part of a playergroup but not the leader.
        """
        return False

    @property
    def group_name(self) -> str:
        """Return name of this grouped player."""
        return self.name

    @property
    def current_url(self) -> str:
        """Return the current_url of the grouped player."""
        return self._attr_current_url

    @property
    def elapsed_time(self) -> float:
        """Return the corrected/precise elsapsed time of the grouped player."""
        if group_leader := self.mass.players.get_player(self.group_leader):
            return group_leader.elapsed_time
        return 0

    async def set_group_power(self, powered: bool) -> None:
        """Send power command to the group player."""
        self.logger.debug("set_group_power command called with value: %s", powered)
        if not powered:
            await self.stop()
        if powered and not self.group_powered:
            # turn on (all) group clients if none are on now
            await super().set_group_power(True)
        else:
            await super().set_group_power(False)

    async def volume_set(self, volume_level: int) -> None:
        """Send volume level (0..100) command to player."""
        # redirect to groupchilds
        await self.set_group_volume(volume_level)

    async def power(self, powered: bool) -> None:
        """Send volume level (0..100) command to player."""
        # redirect to set_group_power
        await self.set_group_power(powered)

    async def stop(self) -> None:
        """Send STOP command to player."""
        # redirect command to all child players, filter out any passive group childs
        await asyncio.gather(
            *[x.stop() for x in self.get_child_players(True) if not x.is_passive]
        )

    async def play(self) -> None:
        """Send PLAY/UNPAUSE command to player."""
        self._attr_powered = True
        # redirect command to all child players, filter out any passive group childs
        await asyncio.gather(
            *[x.play() for x in self.get_child_players(True) if not x.is_passive]
        )

    async def pause(self) -> None:
        """Send PAUSE command to player."""
        # redirect command to all child players, filter out any passive group childs
        await asyncio.gather(
            *[x.pause() for x in self.get_child_players(True) if not x.is_passive]
        )

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        # redirect command to all child players, filter out any passive group childs
        powered_members = self.get_child_players(True)
        if len(powered_members) == 0:
            self.logger.warning("Ignore play_url - no group members are powered")
            return
        self._attr_current_url = url
        self._attr_powered = True
        self.update_state()
        stream_clients = [x for x in powered_members if not x.is_passive]
        # tell stream task how many clients are expected
        self.active_queue.stream.expected_clients = len(stream_clients)
        # execute the call on group members
        await asyncio.gather(*[x.play_url(url) for x in stream_clients])

    def on_child_update(self, player_id: str, changed_keys: set) -> None:
        """Call when one of the child players of a playergroup updates."""
        if (
            "powered" in changed_keys
            and self.active_queue.active
            and self.state in (PlayerState.PLAYING, PlayerState.PAUSED)
        ):

            if child_player := self.mass.players.get_player(player_id):
                # resume queue if a child player turns on while this queue is playing
                if child_player.powered:
                    self.mass.create_task(self.active_queue.resume())
                # make sure that stop is called on the player
                else:
                    self.mass.create_task(child_player.stop())

        super().on_child_update(player_id, changed_keys)


class VolumioPlayer(HassPlayer):
    """Representation of Hass player from Volumio integration."""

    _attr_stream_type: ContentType = ContentType.MP3

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        # a lot of players do not power on at playback request so send power on from here
        if not self.powered:
            await self.power(True)
        self.logger.debug("play_url: %s", url)
        self._attr_current_url = url
        await self.entity.async_play_media(
            MEDIA_TYPE_MUSIC,
            {
                "service": "webradio",
                "type": "webradio",
                "title": DEFAULT_NAME,
                "uri": url,
            },
        )


PLAYER_MAPPING = {
    CAST_DOMAIN: CastPlayer,
    DLNA_DOMAIN: DlnaPlayer,
    SLIMPROTO_DOMAIN: SlimprotoPlayer,
    ESPHOME_DOMAIN: ESPHomePlayer,
    SONOS_DOMAIN: SonosPlayer,
    GROUP_DOMAIN: HassGroupPlayer,
    KODI_DOMAIN: KodiPlayer,
    VOLUMIO_DOMAIN: VolumioPlayer,
}


async def async_register_player_control(
    hass: HomeAssistant, mass: MusicAssistant, entity_id: str
) -> HassPlayer | None:
    """Register hass media_player entity as player control on Music Assistant."""

    # check for existing player first if already registered
    if player := mass.players.get_player(entity_id):
        player.update_state()
        return player

    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(MP_DOMAIN)
    if not entity_comp:
        return None
    entity: MediaPlayerEntity = entity_comp.get_entity(entity_id)
    if not entity:
        return None

    player = None
    # Integration specific player controls
    entry_platform = entity.platform.platform_name
    if entry_platform == DOMAIN:
        # this is already a Music assistant player
        return None
    if entry_platform in BLACKLIST_DOMAINS:
        return None

    # load player specific mapping or generic one
    try:
        player_cls = PLAYER_MAPPING.get(entry_platform, HassPlayer)
        player = player_cls(hass, entity_id)
        # register player in player manager
        await mass.players.register_player(player)
        # if this is a grouped player, make sure to register all childs too
        for group_member in player.group_members:
            group_member = get_source_entity_id(hass, group_member)
            if group_member == entity_id:
                continue
            hass.create_task(async_register_player_control(hass, mass, group_member))
        return player
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.error("Error while registering player %s", entity_id, exc_info=err)
        return None


async def async_register_player_controls(
    hass: HomeAssistant, mass: MusicAssistant, entry: ConfigEntry
):
    """Register hass entities as player controls on Music Assistant."""
    allowed_entities = entry.options.get(CONF_PLAYER_ENTITIES, [])

    async def async_hass_state_event(event: Event) -> None:
        """Handle hass state-changed events to update registered PlayerControls."""
        entity_id: str = event.data[ATTR_ENTITY_ID]

        if not entity_id.startswith(MP_DOMAIN):
            return

        # handle existing source player
        if source_player := mass.players.get_player(entity_id):
            source_player.on_hass_event(event)
            return
        # entity not (yet) registered
        if entity_id in allowed_entities:
            await async_register_player_control(hass, mass, entity_id)

    # register event listener
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, async_hass_state_event)
    )

    # register all current entities
    def register_all():
        for entity in hass.states.async_all(MEDIA_PLAYER_DOMAIN):
            if entity.entity_id not in allowed_entities:
                continue
            hass.create_task(
                async_register_player_control(hass, mass, entity.entity_id)
            )

    register_all()
    # schedule register a few minutes after startup to catch any slow loading platforms
    hass.loop.call_later(30, register_all)
    hass.loop.call_later(120, register_all)
