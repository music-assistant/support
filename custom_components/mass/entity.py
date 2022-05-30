"""Base entity model."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity
from music_assistant import MusicAssistant
from music_assistant.models.enums import EventType
from music_assistant.models.event import MassEvent
from music_assistant.models.player import Player

from .const import DEFAULT_NAME, DOMAIN


class MassBaseEntity(Entity):
    """Base Entity from Music Assistant Player."""

    def __init__(self, mass: MusicAssistant, player: Player) -> None:
        """Initialize MediaPlayer entity."""
        self.mass = mass
        self.player = player
        self.queue = mass.players.get_player_queue(player.player_id)
        self._attr_should_poll = False
        dev_man = player.device_info.manufacturer or DEFAULT_NAME
        dev_mod = player.device_info.model or player.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player.player_id)},
            manufacturer=dev_man,
            model=dev_mod,
            name=player.name,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await self.async_on_update()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update, EventType.PLAYER_UPDATED, self.player.player_id
            )
        )
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update,
                EventType.QUEUE_UPDATED,
            )
        )

    @property
    def unique_id(self) -> str | None:
        """Return unique id for entity."""
        _base = f"mass_{self.player.player_id}"
        if hasattr(self, "entity_description"):
            return f"{_base}_{self.entity_description.key}"
        return _base

    @property
    def available(self) -> bool:
        """Return availability of entity."""
        return self.player.available

    @property
    def name(self) -> str | None:
        """Return default entity name."""
        _base = self.player.name
        if hasattr(self, "entity_description"):
            return f"{_base} {self.entity_description.name}"
        return _base

    async def __on_mass_update(self, event: MassEvent) -> None:
        """Call when we receive an event from MusicAssistant."""
        if event == EventType.QUEUE_UPDATED:
            if event.object_id != self.player.active_queue.queue_id:
                return
        await self.async_on_update()
        self.async_write_ha_state()

    async def async_on_update(self) -> None:
        """Handle player updates."""
