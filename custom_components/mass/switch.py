"""Support for switch platform for Music Assistant config options."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from music_assistant import MusicAssistant
from music_assistant.models.enums import EventType
from music_assistant.models.event import MassEvent

from .const import DOMAIN
from .entity import MassBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicAssistant switch platform."""
    mass: MusicAssistant = hass.data[DOMAIN]
    added_ids = set()

    async def async_add_switch_entities(event: MassEvent) -> None:
        """Add switch entities from Music Assistant PlayerQueue."""
        if event.object_id in added_ids:
            return
        added_ids.add(event.object_id)
        async_add_entities(
            [
                ShuffleEnabledEntity(mass, event.data),
                NormalizeEnabledEntity(mass, event.data),
            ]
        )

    # register listener for new players
    config_entry.async_on_unload(
        mass.subscribe(async_add_switch_entities, EventType.PLAYER_ADDED)
    )

    # add all current items in controller
    for player in mass.players:
        await async_add_switch_entities(
            MassEvent(EventType.PLAYER_ADDED, object_id=player.player_id, data=player)
        )


class ShuffleEnabledEntity(MassBaseEntity, SwitchEntity):
    """Representation of a Switch entity to set shuffle enabled."""

    entity_description = SwitchEntityDescription(
        key="shuffle_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:shuffle",
        entity_category=EntityCategory.CONFIG,
        name="Shuffle enabled",
    )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.queue.settings.shuffle_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.queue.settings.shuffle_enabled = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.queue.settings.shuffle_enabled = False


class NormalizeEnabledEntity(MassBaseEntity, SwitchEntity):
    """Representation of a Switch entity to set volume normalization enabled."""

    entity_description = SwitchEntityDescription(
        key="normalize_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:chart-bar",
        entity_category=EntityCategory.CONFIG,
        name="Volume normalization enabled",
    )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.queue.settings.volume_normalization_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.queue.settings.volume_normalization_enabled = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.queue.settings.volume_normalization_enabled = False
