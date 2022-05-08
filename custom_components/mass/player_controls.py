"""Support Home Assistant media_player entities to be used as Players for Music Assistant."""
from __future__ import annotations

from typing import Dict

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
)
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SERVICE_PLAY_MEDIA,
    SUPPORT_PLAY_MEDIA,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import Event
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow
from music_assistant import MusicAssistant
from music_assistant.models.player import DeviceInfo, Player, PlayerGroup, PlayerState

from .const import (
    ATTR_SOURCE_ENTITY_ID,
    CONF_MUTE_POWER_PLAYERS,
    CONF_PLAYER_ENTITIES,
    DOMAIN,
    SLIMPROTO_DOMAIN,
    SLIMPROTO_EVENT,
)

OFF_STATES = [STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN, STATE_STANDBY]
UNAVAILABLE_STATES = [STATE_UNAVAILABLE, STATE_UNKNOWN]
CAST_DOMAIN = "cast"
CAST_MULTIZONE_MANAGER_KEY = "cast_multizone_manager"


GROUP_DOMAIN = "group"


STATE_MAPPING = {
    STATE_OFF: PlayerState.OFF,
    STATE_ON: PlayerState.IDLE,
    STATE_UNKNOWN: PlayerState.OFF,
    STATE_UNAVAILABLE: PlayerState.OFF,
    STATE_IDLE: PlayerState.IDLE,
    STATE_PLAYING: PlayerState.PLAYING,
    STATE_PAUSED: PlayerState.PAUSED,
    STATE_STANDBY: PlayerState.OFF,
}


class HassPlayer(Player):
    """Mapping from Home Assistant Mediaplayer to Music Assistant Player."""

    def __init__(
        self, hass: HomeAssistantType, entity_id: str, mute_as_power: bool
    ) -> None:
        """Initialize player."""
        self.hass = hass
        # use the (source) entity_id as player_id for now, to be improved later with unique_id ?
        self.player_id = entity_id
        self.entity_id = entity_id
        self._mute_as_power = mute_as_power
        self._is_muted = False
        self.ent_reg = er.async_get(hass)

        manufacturer = "Home Assistant"
        model = entity_id
        if entry := self.ent_reg.async_get(entity_id):
            if entry.device_id:
                dev_reg = dr.async_get(hass)
                device = dev_reg.async_get(entry.device_id)
                manufacturer = device.manufacturer
                model = device.model
        self._attr_device_info = DeviceInfo(manufacturer=manufacturer, model=model)
        self.update_attributes()

    @property
    def elapsed_time(self) -> float:
        """Return elapsed time of current playing media in seconds."""
        # we need to return the corrected time here
        if state := self.hass.states.get(self.entity_id):
            elapsed_time = state.attributes.get(ATTR_MEDIA_POSITION, 0)
            last_upd = state.attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT, utcnow())
            diff = (utcnow() - last_upd).seconds
            return elapsed_time + diff
        return 0

    @property
    def powered(self) -> bool:
        """Return bool if this player is currently powered on."""
        if self._mute_as_power:
            return not self._is_muted
        return self._attr_powered

    @property
    def state(self) -> PlayerState:
        """Return current state of player."""
        if not self._attr_available:
            return PlayerState.OFF
        if not self.powered:
            return PlayerState.OFF
        if self._attr_state == PlayerState.OFF and self.powered:
            return PlayerState.IDLE
        return self._attr_state

    @callback
    def on_hass_event(self, event: Event) -> None:
        """Call on Home Assistant event."""
        self.update_attributes()
        self.update_state()

    @callback
    def update_attributes(self) -> None:
        """Update attributes of this player."""
        hass_state = self.hass.states.get(self.entity_id)
        self._attr_name = hass_state.name
        self._attr_powered = hass_state.state not in OFF_STATES
        self._is_muted = hass_state.attributes.get(
            ATTR_MEDIA_VOLUME_MUTED, self._is_muted
        )
        self._attr_current_url = hass_state.attributes.get(ATTR_MEDIA_CONTENT_ID)
        self._attr_state = STATE_MAPPING.get(hass_state.state, PlayerState.OFF)
        self._attr_available = hass_state.state not in UNAVAILABLE_STATES
        self._attr_current_url = hass_state.attributes.get(ATTR_MEDIA_CONTENT_ID)
        self._attr_volume_level = int(
            hass_state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL, 0) * 100
        )

    async def play_url(self, url: str) -> None:
        """Play the specified url on the player."""
        await self.hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: url,
                "entity_id": self.entity_id,
            },
        )

    async def stop(self) -> None:
        """Send STOP command to player."""
        await self.hass.services.async_call(
            MP_DOMAIN, SERVICE_MEDIA_STOP, {"entity_id": self.entity_id}
        )

    async def play(self) -> None:
        """Send PLAY/UNPAUSE command to player."""
        await self.hass.services.async_call(
            MP_DOMAIN, SERVICE_MEDIA_PLAY, {"entity_id": self.entity_id}
        )

    async def pause(self) -> None:
        """Send PAUSE command to player."""
        await self.hass.services.async_call(
            MP_DOMAIN, SERVICE_MEDIA_PAUSE, {"entity_id": self.entity_id}
        )

    async def power(self, powered: bool) -> None:
        """Send POWER command to player."""
        if not powered and self.active_queue.queue_id == self.player_id:
            if self.state == PlayerState.PLAYING:
                await self.active_queue.stop()

        # handle mute-as-power workaround
        if self._mute_as_power:
            await self.hass.services.async_call(
                MP_DOMAIN,
                SERVICE_VOLUME_MUTE,
                {"entity_id": self.entity_id, ATTR_MEDIA_VOLUME_MUTED: not powered},
            )
            self._is_muted = not powered
            self.update_state()
            return
        # regular turn_on service call
        cmd = SERVICE_TURN_ON if powered else SERVICE_TURN_OFF
        await self.hass.services.async_call(
            MP_DOMAIN, cmd, {"entity_id": self.entity_id}
        )

    async def volume_set(self, volume_level: int) -> None:
        """Send volume level (0..100) command to player."""
        await self.hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            {"entity_id": self.entity_id, ATTR_MEDIA_VOLUME_LEVEL: volume_level / 100},
        )


class HassSqueezeboxPlayer(HassPlayer):
    """Representation of Hass player from Squeezebox Local integration."""

    def __init__(
        self, hass: HomeAssistantType, entity_id: str, squeeze_id: str
    ) -> None:
        """Initialize player."""
        self.squeeze_id = squeeze_id
        self.slimserver = hass.data[SLIMPROTO_DOMAIN]
        self._unsubs = [
            hass.bus.async_listen(SLIMPROTO_EVENT, self.on_squeezebox_event)
        ]
        super().__init__(hass, entity_id, False)

    @callback
    def on_remove(self) -> None:
        """Call when player is about to be removed (cleaned up) from player manager."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    @callback
    def on_squeezebox_event(self, event: Event) -> None:
        """Handle special events from squeezebox players."""
        if event.data["player_id"] != self.squeeze_id:
            return
        cmd = event.data["command_str"]
        if cmd == "playlist index +1":
            self.hass.create_task(self.active_queue.next())
        if cmd == "playlist index -1":
            self.hass.create_task(self.active_queue.previous())


class HassGroupPlayer(PlayerGroup):
    """Mapping from Home Assistant Grouped Mediaplayer to Music Assistant Player."""

    def __init__(self, hass: HomeAssistantType, entity_id: str) -> None:
        """Initialize player."""
        self.hass = hass
        self.player_id = entity_id
        self.entity_id = entity_id
        self._fake_power = False
        self._attr_is_group = True
        self._attr_use_multi_stream = True
        self._attr_current_url = ""
        self._attr_device_info = DeviceInfo(
            manufacturer="Home Assistant", model="Media Player Group"
        )
        self.update_attributes()

    async def power(self, powered: bool) -> None:
        """Send POWER command to player."""
        if not powered and self.active_queue.queue_id == self.player_id:
            if self.state == PlayerState.PLAYING:
                await self.active_queue.stop()

        cmd = SERVICE_TURN_ON if powered else SERVICE_TURN_OFF
        await self.hass.services.async_call(
            MP_DOMAIN, cmd, {"entity_id": self.entity_id}
        )

    @callback
    def on_hass_event(self, event: Event) -> None:
        """Call on Home Assistant event."""
        self.update_attributes()
        self.update_state()

    @callback
    def update_attributes(self) -> None:
        """Call when player state is about to be updated in the player manager."""
        hass_state = self.hass.states.get(self.entity_id)
        self._attr_available = hass_state.state not in UNAVAILABLE_STATES
        self._attr_name = hass_state.name
        self._attr_powered = hass_state.state not in OFF_STATES

        # collect the group childs, be prepared for the usecase where the user actually
        # added a mass player to a group, translate that to the underlying entity.
        group_childs = []
        for entity_id in hass_state.attributes.get(ATTR_ENTITY_ID, []):
            if source_id := self._get_source_entity_id(entity_id):
                group_childs.append(source_id)
        self._attr_group_childs = group_childs

    def _get_source_entity_id(self, entity_id: str) -> str | None:
        """Return source entity_id from child entity_id."""
        if hass_state := self.hass.states.get(entity_id):
            # if entity is actually already mass entity, return the source entity
            if source_id := hass_state.attributes.get(ATTR_SOURCE_ENTITY_ID):
                return source_id
            return entity_id
        return None


class HassCastGroupPlayer(PlayerGroup, HassPlayer):
    """Mapping from Google Cast GroupPlayer to Music Assistant Player."""

    def __init__(self, hass: HomeAssistantType, entity_id: str) -> None:
        """Initialize player."""
        self.ent_reg = er.async_get(hass)
        ent_entry = self.ent_reg.async_get(entity_id)
        self.cast_uuid = ent_entry.unique_id
        self._fake_power = False
        super().__init__(hass, entity_id, False)
        self._attr_is_group = True

    @property
    def powered(self) -> bool:
        """Return bool is this groupplayer is powered on/active."""
        return self._attr_powered or self._fake_power

    async def power(self, powered: bool) -> None:
        """Send POWER command to player."""
        if not powered and self.active_queue.queue_id == self.player_id:
            if self.state == PlayerState.PLAYING:
                await self.active_queue.stop()
        self._fake_power = powered
        self.update_state()
        # cast group players do support turn off (but not on)
        if not powered and self.powered:
            await self.hass.services.async_call(
                MP_DOMAIN, SERVICE_TURN_OFF, {"entity_id": self.entity_id}
            )

    @callback
    def update_attributes(self) -> None:
        """Update attributes of this player."""
        super().update_attributes()
        # this is a bit hacky to get the group members
        # TODO: create PR to add these as state attributes to the cast integration
        # pylint: disable=protected-access
        if CAST_MULTIZONE_MANAGER_KEY not in self.hass.data:
            return
        mz_mgr = self.hass.data[CAST_MULTIZONE_MANAGER_KEY]
        if self.cast_uuid not in mz_mgr._groups:
            return
        mz_ctrl = mz_mgr._groups[self.cast_uuid]["listener"]._mz
        child_players = []
        for cast_uuid in mz_ctrl.members:
            if entity_id := self.ent_reg.entities.get_entity_id(
                (MP_DOMAIN, CAST_DOMAIN, cast_uuid)
            ):
                child_players.append(entity_id)
        self._attr_group_childs = child_players


class HassPlayerControls:
    """Enable Home Assisant entities to be used as Players for MusicAssistant."""

    def __init__(
        self, hass: HomeAssistantType, mass: MusicAssistant, config: dict
    ) -> None:
        """Initialize class."""
        self.hass = hass
        self.mass = mass
        self.config = config
        self._registered_players: Dict[str, HassPlayer] = {}

    async def async_hass_state_event(self, event: Event) -> None:
        """Handle hass state-changed events to update registered PlayerControls."""
        entity_id: str = event.data[ATTR_ENTITY_ID]

        if not entity_id.startswith(MP_DOMAIN):
            return

        if entity_id in self._registered_players:
            self._registered_players[entity_id].on_hass_event(event)
        else:
            # entity not (yet) registered
            await self.async_register_player_control(entity_id)

    async def async_register_player_controls(self):
        """Register hass entities as player controls on Music Assistant."""

        for entity in self.hass.states.async_all(MEDIA_PLAYER_DOMAIN):
            await self.async_register_player_control(entity.entity_id)

    async def async_register_player_control(
        self, entity_id: str, manual=False
    ) -> HassPlayer | None:
        """Register hass entitie as player controls on Music Assistant."""
        allowed_entities = self.config.get(CONF_PLAYER_ENTITIES)
        # allowed_entities not configured = not filter (=all)
        if not (manual or allowed_entities is None or entity_id in allowed_entities):
            return

        if entity_id in self._registered_players:
            return self._registered_players[entity_id]

        entity = self.hass.states.get(entity_id)
        if entity is None or entity.attributes is None:
            return

        if not (entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & SUPPORT_PLAY_MEDIA):
            return

        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        player = None
        # Integration specific player controls
        if ent_entry := ent_reg.async_get(entity_id):
            if ent_entry.platform == DOMAIN:
                # this is already a Music assistant player
                return
            if ent_entry.platform == CAST_DOMAIN:
                if dev_entry := dev_reg.async_get(ent_entry.device_id):
                    if dev_entry.model == "Google Cast Group":
                        player = HassCastGroupPlayer(self.hass, entity_id)
            elif ent_entry.platform == SLIMPROTO_DOMAIN:
                player = HassSqueezeboxPlayer(self.hass, entity_id, ent_entry.unique_id)
            elif ent_entry.platform == GROUP_DOMAIN:
                player = HassGroupPlayer(self.hass, entity_id)

        # handle genric player for all other integrations
        mute_as_power = entity_id in self.config.get(CONF_MUTE_POWER_PLAYERS, [])
        if player is None:
            player = HassPlayer(self.hass, entity_id, mute_as_power)
        self._registered_players[entity_id] = player
        await self.mass.players.register_player(player)
        return player
