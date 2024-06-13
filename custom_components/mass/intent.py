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
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from music_assistant.common.models.errors import MusicAssistantError

from . import DOMAIN
from .const import CONF_OPENAI_AGENT_ID
from .media_player import ATTR_MEDIA_ID, ATTR_MEDIA_TYPE, ATTR_RADIO_MODE, MassPlayer

INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER = "MassPlayMediaOnMediaPlayer"
NAME_SLOT = "name"
AREA_SLOT = "area"
QUERY_SLOT = "query"
ARTIST_SLOT = "artist"
TRACK_SLOT = "track"
ALBUM_SLOT = "album"
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
        vol.Optional(ARTIST_SLOT): cv.string,
        vol.Optional(TRACK_SLOT): cv.string,
        vol.Optional(ALBUM_SLOT): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        response = intent_obj.create_response()
        slots = self.async_validate_slots(intent_obj.slots)
        config_entry = await self._get_loaded_config_entry(intent_obj.hass)

        mass_player = await self._async_get_matched_mass_player(
            intent_obj, slots, config_entry
        )

        query = slots.get(QUERY_SLOT, {}).get(SLOT_VALUE)
        if query:
            if not config_entry.data.get(CONF_OPENAI_AGENT_ID):
                raise intent.IntentHandleError(
                    "query requires using a conversation agent"
                )
            ai_response = await self._async_query_ai(intent_obj, query, config_entry)
            try:
                json_payload = json.loads(ai_response)
            except json.decoder.JSONDecodeError:
                response.response_type = intent.IntentResponseType.PARTIAL_ACTION_DONE
                response.async_set_speech(ai_response)
                return response
            media_id = json_payload.get(ATTR_MEDIA_ID)
            media_type = json_payload.get(ATTR_MEDIA_TYPE)
        else:
            artist = slots.get(ARTIST_SLOT, {}).get(SLOT_VALUE, "")
            track = slots.get(TRACK_SLOT, {}).get(SLOT_VALUE, "")
            album = slots.get(ALBUM_SLOT, {}).get(SLOT_VALUE, "")
            if track:
                media_type = "track"
                if artist:
                    media_id = f"{artist} - {track}"
                else:
                    media_id = track
            elif album:
                media_type = "album"
                if artist:
                    media_id = f"{artist} - {album}"
                else:
                    media_id = album
            elif artist:
                media_type = "artist"
                media_id = artist
            else:
                raise intent.IntentHandleError("No media item parsed from query")

        try:
            await mass_player.async_play_media(
                media_type=media_type,
                media_id=media_id,
                enqueue=None,
                extra={ATTR_RADIO_MODE: False},
            )
        except MusicAssistantError as err:
            raise intent.IntentHandleError(err.args[0] if err.args else "") from err

        response.response_type = intent.IntentResponseType.ACTION_DONE
        response.async_set_speech("Okay")
        return response

    async def _async_get_matched_mass_player(
        self,
        intent_obj: intent.Intent,
        slots: intent._SlotsType,
        config_entry: ConfigEntry,
    ) -> MassPlayer:
        name: str | None = slots.get(NAME_SLOT, {}).get(SLOT_VALUE)
        if name == "all":
            # Don't match on name if targeting all entities
            name = None
        area_name = slots.get(AREA_SLOT, {}).get(SLOT_VALUE)
        state = await self._get_matched_state(intent_obj, name, area_name)
        mass_player = MassPlayer(
            intent_obj.hass.data[DOMAIN][config_entry.entry_id].mass,
            state.attributes.get("mass_player_id"),
        )
        if mass_player is None:
            raise intent.IntentHandleError(
                f"No entities matched for: name={name}, area_name={area_name}"
            )
        return mass_player

    async def _async_query_ai(
        self, intent_obj: intent.Intent, query: str, config_entry: ConfigEntry
    ) -> str:
        service_data: dict[str, Any] = {}
        service_data[ATTR_AGENT_ID] = config_entry.data.get(CONF_OPENAI_AGENT_ID)
        service_data[ATTR_TEXT] = query
        ai_response = await intent_obj.hass.services.async_call(
            CONVERSATION_DOMAIN,
            CONVERSATION_SERVICE,
            {**service_data},
            blocking=True,
            context=intent_obj.context,
            return_response=True,
        )
        return ai_response["response"]["speech"]["plain"]["speech"]

    async def _get_loaded_config_entry(self, hass: HomeAssistant) -> ConfigEntry:
        """Get the correct config entry."""
        config_entries = hass.config_entries.async_entries(DOMAIN)
        for config_entry in config_entries:
            if config_entry.state == ConfigEntryState.LOADED:
                return config_entry
        raise intent.IntentHandleError("Music Assistant not loaded")

    async def _get_matched_state(
        self, intent_obj: intent.Intent, name: str | None, area_name: str | None
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
                area_name=area_name,
                states=mass_states,
            )
        )

        if not states:
            raise intent.IntentHandleError(
                f"No entities matched for: name={name}, area_name={area_name}"
            )

        if len(states) > 1:
            raise intent.IntentHandleError(
                f"Multiple entities matched for: name={name}, area_name={area_name}"
            )

        return states[0]
