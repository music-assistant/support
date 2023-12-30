"""Intents for the client integration."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from . import DOMAIN
from .media_player import MassPlayer

if TYPE_CHECKING:
    pass
if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient


INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER = "MassPlayMediaOnMediaPlayerNameEn"
CONVERSATION_DOMAIN = "conversation"
CONVERSATION_SERVICE = "process"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the climate intents."""
    intent.async_register(hass, MassPlayMediaOnMediaPlayerNameEn())


class MassPlayMediaOnMediaPlayerNameEn(intent.IntentHandler):
    """Handle PlayMediaOnMediaPlayer intents."""

    intent_type = INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER
    slot_schema = {vol.Any("name", "area"): cv.string, vol.Optional("query"): cv.string}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        service_data: dict[str, Any] = {}
        slots = self.async_validate_slots(intent_obj.slots)

        query: str = slots.get("query", {}).get("value")
        if query is not None:
            config_entry = await self.get_loaded_config_entry(hass)
            service_data["agent_id"] = config_entry.data.get("openai_agent_id")
            service_data["text"] = query

        # Look up area first to fail early
        area_name = slots.get("area", {}).get("value")
        area: ar.AreaEntry | None = None
        if area_name is not None:
            areas = ar.async_get(hass)
            area = areas.async_get_area(area_name) or areas.async_get_area_by_name(area_name)
            if area is None:
                raise intent.IntentHandleError(f"No area named {area_name}")

        name: str = slots.get("name", {}).get("value")
        if name is not None:
            media_id, media_type = await self.get_media_id_and_media_type_from_query_result(
                hass, service_data, intent_obj
            )
            mass: MusicAssistantClient = hass.data[DOMAIN][config_entry.entry_id].mass
            players = await mass.players.get_players()
            for player in players:
                if player.name.casefold() == name.casefold():
                    actual_player = MassPlayer(mass, player.player_id)
                    break

        if actual_player is None:
            raise intent.IntentHandleError(f"No Mass media player found for name {name}")
        await actual_player.async_play_media(
            media_id=media_id, media_type=media_type, extra={"radio_mode": False}
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
        media_id = json_payload.get("media_id")
        media_type = json_payload.get("media_type")
        return media_id, media_type

    async def get_loaded_config_entry(self, hass: HomeAssistant) -> str:
        """Get the correct config entry."""
        config_entries = hass.config_entries.async_entries(DOMAIN)
        for config_entry in config_entries:
            if config_entry.state == ConfigEntryState.LOADED:
                return config_entry
        return None
