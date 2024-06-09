"""Intents for the client integration."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol
from homeassistant.components.conversation import ATTR_AGENT_ID, ATTR_TEXT
from homeassistant.components.conversation import (
    SERVICE_PROCESS as CONVERSATION_SERVICE,
)
from homeassistant.components.conversation.const import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from . import DOMAIN
from .const import CONF_OPENAI_AGENT_ID
from .media_player import ATTR_MEDIA_ID, ATTR_MEDIA_TYPE, ATTR_RADIO_MODE, MassPlayer

INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER = "MassPlayMediaOnMediaPlayer"
NAME_SLOT = "name"
AREA_SLOT = "area"
QUERY_SLOT = "query"
SLOT_VALUE = "value"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the Music Assistant intents."""
    intent.async_register(hass, MassPlayMediaOnMediaPlayerHandler())


class MassPlayMediaOnMediaPlayerHandler(intent.IntentHandler):
    """Handle PlayMediaOnMediaPlayer intents."""

    intent_type = INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER
    slot_schema = {
        vol.Any(NAME_SLOT, AREA_SLOT): cv.string,
        vol.Optional(QUERY_SLOT): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        config_entry = await self._get_loaded_config_entry(intent_obj.hass)

        query: str = slots.get(QUERY_SLOT, {}).get(SLOT_VALUE)
        if query is not None:
            service_data: dict[str, Any] = {}
            service_data[ATTR_AGENT_ID] = config_entry.data.get(CONF_OPENAI_AGENT_ID)
            service_data[ATTR_TEXT] = query

        name: str | None = slots.get(NAME_SLOT, {}).get(SLOT_VALUE)
        if name == "all":
            # Don't match on name if targeting all entities
            name = None
        # Look up area first to fail early
        area: str | None = None
        if AREA_SLOT in slots:
            area = slots[AREA_SLOT][SLOT_VALUE]

        state = await self._get_matched_state(intent_obj, name, area)
        actual_player = MassPlayer(
            intent_obj.hass.data[DOMAIN][config_entry.entry_id].mass,
            state.attributes.get("mass_player_id"),
        )
        if actual_player is None:
            raise intent.IntentHandleError(
                f"No entities matched for: name={name}, area={area}"
            )

        return await self._parse_query_and_return_appropriate_response(
            intent_obj.hass, service_data, intent_obj, actual_player
        )

    async def _parse_query_and_return_appropriate_response(
        self,
        hass: HomeAssistant,
        service_data: dict[str, Any],
        intent_obj: intent.Intent,
        actual_player: MassPlayer,
    ) -> intent.IntentResponse:
        """Get  from the query."""
        ai_response = await hass.services.async_call(
            CONVERSATION_DOMAIN,
            CONVERSATION_SERVICE,
            {**service_data},
            blocking=True,
            context=intent_obj.context,
            return_response=True,
        )
        response = intent_obj.create_response()

        try:
            json_payload = json.loads(
                ai_response["response"]["speech"]["plain"]["speech"]
            )
            media_id = json_payload.get(ATTR_MEDIA_ID)
            media_type = json_payload.get(ATTR_MEDIA_TYPE)
            await actual_player.async_play_media(
                media_type=media_type,
                media_id=media_id,
                enqueue=None,
                extra={ATTR_RADIO_MODE: False},
            )
            response.response_type = intent.IntentResponseType.ACTION_DONE
            response.async_set_speech("Okay")
        except json.decoder.JSONDecodeError:
            clarification_response = ai_response["response"]["speech"]["plain"][
                "speech"
            ]
            response.response_type = intent.IntentResponseType.PARTIAL_ACTION_DONE
            response.async_set_speech(clarification_response)

        return response

    async def _get_loaded_config_entry(self, hass: HomeAssistant) -> str:
        """Get the correct config entry."""
        config_entries = hass.config_entries.async_entries(DOMAIN)
        for config_entry in config_entries:
            if config_entry.state == ConfigEntryState.LOADED:
                return config_entry
        return None

    async def _get_matched_state(
        self, intent_obj: intent.Intent, name: str | None, area: str | None
    ) -> State:
        mass_states: set[str] = set()
        initial_states = intent_obj.hass.states.async_all()
        for state in initial_states:
            if state.attributes.get("mass_player_id") is not None:
                mass_states.add(state)

        states = list(
            intent.async_match_states(
                intent_obj.hass,
                name=name,
                area_name=area,
                states=mass_states,
            )
        )

        if not states:
            raise intent.IntentHandleError(
                f"No entities matched for: name={name}, area={area}"
            )

        if len(states) > 1:
            raise intent.IntentHandleError(
                f"Multiple entities matched for: name={name}, area={area}"
            )

        return states[0]
