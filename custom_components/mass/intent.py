"""Intents for the client integration."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from . import DOMAIN, LOGGER
from .helpers import get_mass
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
    slot_schema = {vol.Optional("query"): cv.string, vol.Optional("name"): cv.string}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        loaded_config_entry = None
        config_entries = hass.config_entries.async_entries(DOMAIN)
        for config_entry in config_entries:
            if config_entry.state == ConfigEntryState.LOADED:
                loaded_config_entry = config_entry
                break
        agent_id = loaded_config_entry.data.get("openai_agent_id")
        mass: MusicAssistantClient = get_mass(hass)
        service_data: dict[str, Any] = {}
        slots = self.async_validate_slots(intent_obj.slots)

        query: str = slots.get("query", {}).get("value")
        LOGGER.info(query)
        service_data["agent_id"] = agent_id
        if query is not None:
            service_data["text"] = query

        ai_response = await self.get_query_result(hass, service_data, intent_obj)
        json_payload = json.loads(ai_response["response"]["speech"]["plain"]["speech"])
        media_id = json_payload.get("media_id")
        media_type = json_payload.get("media_type")
        name: str = slots.get("name", {}).get("value")
        best_match_player = None
        if name is not None:
            players = await mass.players.get_players()
            for player in players:
                if player.name.casefold() == name.casefold():
                    best_match_player = player
                    break

        if best_match_player is not None:
            player_id = best_match_player.player_id
            actual_player = MassPlayer(mass, player_id)
            actual_player.async_play_media(media_id=media_id, media_type=media_type)

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.ACTION_DONE
        response.async_set_speech(f"Playing selection on {best_match_player.name}")
        return response

    async def get_query_result(
        self, hass: HomeAssistant, service_data: dict[str, Any], intent_obj: intent.Intent
    ) -> str:
        """Get the result from the query."""
        return await hass.services.async_call(
            CONVERSATION_DOMAIN,
            CONVERSATION_SERVICE,
            {**service_data},
            blocking=True,
            context=intent_obj.context,
            return_response=True,
        )
