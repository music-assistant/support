"""Intents for the client integration."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.conversation import ATTR_AGENT_ID, ATTR_TEXT
from homeassistant.components.conversation import SERVICE_PROCESS as CONVERSATION_SERVICE
from homeassistant.components.conversation.const import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent

from . import DOMAIN
from .const import CONF_OPENAI_AGENT_ID
from .media_player import ATTR_MEDIA_ID, ATTR_MEDIA_TYPE, ATTR_RADIO_MODE, MassPlayer

if TYPE_CHECKING:
    pass
if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient


INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER = "MassPlayMediaOnMediaPlayerNameEn"
NAME_SLOT = "name"
AREA_SLOT = "area"
QUERY_SLOT = "query"
SLOT_VALUE = "value"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the climate intents."""
    intent.async_register(hass, MassPlayMediaOnMediaPlayerNameEn())


class MassPlayMediaOnMediaPlayerNameEn(intent.IntentHandler):
    """Handle PlayMediaOnMediaPlayer intents."""

    intent_type = INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER
    slot_schema = {vol.Any(NAME_SLOT, AREA_SLOT): cv.string, vol.Optional(QUERY_SLOT): cv.string}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        service_data: dict[str, Any] = {}
        slots = self.async_validate_slots(intent_obj.slots)
        config_entry = await self.get_loaded_config_entry(hass)
        mass: MusicAssistantClient = hass.data[DOMAIN][config_entry.entry_id].mass

        query: str = slots.get(QUERY_SLOT, {}).get(SLOT_VALUE)
        if query is not None:
            service_data[ATTR_AGENT_ID] = config_entry.data.get(CONF_OPENAI_AGENT_ID)
            service_data[ATTR_TEXT] = query

        # Look up area to fail early
        area_name = slots.get(AREA_SLOT, {}).get(SLOT_VALUE)
        area: ar.AreaEntry | None = None
        if area_name is not None:
            areas = ar.async_get(hass)
            area_name = area_name.casefold()
            area = await self._find_area(area_name, areas)
            if area is None:
                raise intent.IntentHandleError(f"No area named {area_name}")
            media_player_entity = await self._filter_by_area(area, hass, config_entry)
        # Look up name to fail early
        name: str = slots.get(NAME_SLOT, {}).get(SLOT_VALUE)
        if name is not None:
            name = name.casefold()
            media_player_entity = await self.get_entity_from_registry(name, hass, config_entry)

        if media_player_entity is None:
            if name is not None:
                raise intent.IntentHandleError(f"No media player found matching name: {name}")
            if area is not None:
                raise intent.IntentHandleError(f"No media player found matching area: {area_name}")

        actual_player = await self.get_mass_player_from_registry_entry(mass, media_player_entity)
        if actual_player is None:
            raise intent.IntentHandleError(f"No Mass media player found for name {name}")

        media_id, media_type = await self.get_media_id_and_media_type_from_query_result(
            hass, service_data, intent_obj
        )
        await actual_player.async_play_media(
            media_id=media_id, media_type=media_type, extra={ATTR_RADIO_MODE: False}
        )
        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.ACTION_DONE
        response.async_set_speech(f"Playing selection on {name}")
        return response

    async def get_media_id_and_media_type_from_query_result(
        self, hass: HomeAssistant, service_data: dict[str, Any], intent_obj: intent.Intent
    ) -> str:
        """Get  from the query."""
        ai_response = await hass.services.async_call(
            CONVERSATION_DOMAIN,
            CONVERSATION_SERVICE,
            {**service_data},
            blocking=True,
            context=intent_obj.context,
            return_response=True,
        )
        json_payload = json.loads(ai_response["response"]["speech"]["plain"]["speech"])
        media_id = json_payload.get(ATTR_MEDIA_ID)
        media_type = json_payload.get(ATTR_MEDIA_TYPE)
        return media_id, media_type

    async def get_loaded_config_entry(self, hass: HomeAssistant) -> str:
        """Get the correct config entry."""
        config_entries = hass.config_entries.async_entries(DOMAIN)
        for config_entry in config_entries:
            if config_entry.state == ConfigEntryState.LOADED:
                return config_entry
        return None

    async def get_entity_from_registry(
        self, name: str, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> er.RegistryEntry:
        """Get the entity from the registry."""
        entity_registry = er.async_get(hass)
        entity_registry_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for entity_registry_entry in entity_registry_entries:
            if await self._has_name(entity_registry_entry, name):
                return entity_registry_entry
        return None

    async def _has_name(self, entity: er.RegistryEntry | None, name: str) -> bool:
        """Return true if entity name or alias matches."""
        if entity is not None:
            normalised_entity_id = (
                entity.entity_id.replace("_", " ").strip("media player.").casefold()
            )

        if name in normalised_entity_id:
            return True

        # Check name/aliases
        if (entity is None) or (not entity.aliases):
            return False

        return any(name == alias.casefold() for alias in entity.aliases)

    async def get_mass_player_from_registry_entry(
        self, mass: MusicAssistantClient, media_player_entity: er.RegistryEntry
    ) -> MassPlayer:
        """Return the mass player."""
        mass_player = mass.players.get_player(media_player_entity.unique_id.strip("mass_"))
        actual_player = MassPlayer(mass, mass_player.player_id)
        return actual_player

    async def _find_area(self, area_name: str, areas: ar.AreaRegistry) -> ar.AreaEntry | None:
        """Find an area by id or name, checking aliases too."""
        area = areas.async_get_area(area_name) or areas.async_get_area_by_name(area_name)
        if area is not None:
            return area

        # Check area aliases
        for maybe_area in areas.areas.values():
            if not maybe_area.aliases:
                continue

            for area_alias in maybe_area.aliases:
                if area_name == area_alias.casefold():
                    return maybe_area

        return None

    async def _filter_by_area(
        self, area: ar.AreaEntry, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> er.RegistryEntry:
        """Filter state/entity pairs by an area."""
        entity_registry = er.async_get(hass)
        devices = dr.async_get(hass)
        entity_registry_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for entity_registry_entry in entity_registry_entries:
            if entity_registry_entry.area_id == area.id:
                return entity_registry_entry
            elif entity_registry_entry.device_id is not None:
                device = devices.async_get(entity_registry_entry.device_id)
                if device is not None and device.area_id == area.id:
                    return entity_registry_entry
        return None
