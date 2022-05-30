"""Support for number platform for Music Assistant config options."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_SECONDS
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
    """Set up MusicAssistant number platform."""
    mass: MusicAssistant = hass.data[DOMAIN]
    added_ids = set()

    async def async_add_number_entities(event: MassEvent) -> None:
        """Add number entities from Music Assistant Player."""
        if event.object_id in added_ids:
            return
        added_ids.add(event.object_id)
        async_add_entities(
            [
                CrossfadeDurationEntity(mass, event.data),
                VolumeNormalizationTargetEntity(mass, event.data),
            ]
        )

    # register listener for new players
    config_entry.async_on_unload(
        mass.subscribe(async_add_number_entities, EventType.PLAYER_ADDED)
    )

    # add all current items in controller
    for player in mass.players:
        await async_add_number_entities(
            MassEvent(EventType.PLAYER_ADDED, object_id=player.player_id, data=player)
        )


class CrossfadeDurationEntity(MassBaseEntity, NumberEntity):
    """Representation of a number entity to set the crossfade duration."""

    entity_description = NumberEntityDescription(
        key="crossfade_duration",
        icon="mdi:camera-timer",
        entity_category=EntityCategory.CONFIG,
        unit_of_measurement=TIME_SECONDS,
        name="Crossfade duration",
        max_value=10,
        min_value=0,
        step=1,
    )

    @property
    def value(self) -> bool:
        """Return current value."""
        return self.queue.settings.crossfade_duration

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        self.queue.settings.crossfade_duration = int(value)


class VolumeNormalizationTargetEntity(MassBaseEntity, NumberEntity):
    """Representation of a number entity to set the volume normalization target."""

    entity_description = NumberEntityDescription(
        key="volume_normalization_target",
        icon="mdi:chart-bar",
        entity_category=EntityCategory.CONFIG,
        unit_of_measurement=TIME_SECONDS,
        name="Volume normalization target",
        max_value=0,
        min_value=-40,
        step=1,
    )

    @property
    def value(self) -> bool:
        """Return current value."""
        return self.queue.settings.volume_normalization_target

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        self.queue.settings.volume_normalization_target = value
