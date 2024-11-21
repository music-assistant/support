"""Base entity model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo, Entity
from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent

from .const import DOMAIN

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient
    from music_assistant_models.player import Player


class MusicAssistantBaseEntity(Entity):
    """Base Entity from Music Assistant Player."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, mass: MusicAssistantClient, player_id: str) -> None:
        """Initialize MediaPlayer entity."""
        self.mass = mass
        self.player_id = player_id
        player = mass.players.get(player_id)
        provider = self.mass.get_provider(player.provider, True)
        if TYPE_CHECKING:
            assert provider is not None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player_id)},
            manufacturer=self.player.device_info.manufacturer or provider.name,
            model=self.player.device_info.model or self.player.name,
            name=self.player.display_name,
            configuration_url=f"{mass.server_url}/#/settings/editplayer/{player_id}",
            sw_version=self.player.device_info.software_version,
            model_id=self.player.device_info.model_id,
        )
        if self.player.device_info.mac_address:
            self._attr_device_info["connections"] = {
                ("mac", self.player.device_info.mac_address),
            }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await self.async_on_update()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update, EventType.PLAYER_UPDATED, self.player_id
            )
        )
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update,
                EventType.QUEUE_UPDATED,
            )
        )

    @property
    def player(self) -> Player:
        """Return the Mass Player attached to this HA entity."""
        return self.mass.players[self.player_id]

    @property
    def unique_id(self) -> str | None:
        """Return unique id for entity."""
        _base = f"mass_{self.player_id}"
        if hasattr(self, "entity_description"):
            return f"{_base}_{self.entity_description.key}"
        return _base

    @property
    def available(self) -> bool:
        """Return availability of entity."""
        return self.player.available and self.mass.connection.connected

    async def __on_mass_update(self, event: MassEvent) -> None:
        """Call when we receive an event from MusicAssistant."""
        if event.event == EventType.QUEUE_UPDATED and event.object_id not in (
            self.player.active_source,
            self.player.active_group,
            self.player.player_id,
        ):
            return
        await self.async_on_update()
        self.async_write_ha_state()

    async def async_on_update(self) -> None:
        """Handle player updates."""
