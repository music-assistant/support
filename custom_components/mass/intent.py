"""Intents for the client integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.conversation import ATTR_AGENT_ID, ATTR_TEXT
from homeassistant.components.conversation import (
    SERVICE_PROCESS as CONVERSATION_SERVICE,
)
from homeassistant.components.conversation.const import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers.intent import (
    IntentHandleError,
    MatchTargetsConstraints,
    MatchFailedError,
)
from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import MediaType
from music_assistant_models.errors import MusicAssistantError
from music_assistant_models.media_items import MediaItemType

from . import DOMAIN
from .const import (
    ATTR_MASS_PLAYER_TYPE,
    CONF_OPENAI_AGENT_ID,
    ATTR_MEDIA_ID,
    ATTR_MEDIA_TYPE,
    ATTR_RADIO_MODE,
    SERVICE_PLAY_MEDIA_ADVANCED,
)

if TYPE_CHECKING:
    from . import MusicAssistantConfigEntry

INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER = "MassPlayMediaOnMediaPlayer"
INTENT_PLAY_MEDIA_ASSIST = "MassPlayMediaAssist"
NAME_SLOT = "name"
AREA_SLOT = "area"
QUERY_SLOT = "query"
ARTIST_SLOT = "artist"
TRACK_SLOT = "track"
ALBUM_SLOT = "album"
RADIO_SLOT = "radio"
PLAYLIST_SLOT = "playlist"
RADIO_MODE_SLOT = "radio_mode"
SLOT_VALUE = "value"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the Music Assistant intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_PLAY_MEDIA_ASSIST,
            DOMAIN,
            SERVICE_PLAY_MEDIA_ADVANCED,
            description="Handle Assist Play Media intents.",
            optional_slots={
                (ARTIST_SLOT, ATTR_MEDIA_ID): cv.string,
                (TRACK_SLOT, ATTR_MEDIA_ID): cv.string,
                (ALBUM_SLOT, ATTR_MEDIA_ID): cv.string,
                (RADIO_SLOT, ATTR_MEDIA_ID): cv.string,
                (PLAYLIST_SLOT, ATTR_MEDIA_ID): cv.string,
                (RADIO_MODE_SLOT, ATTR_RADIO_MODE): vol.Coerce(bool),
            },
            required_domains={MEDIA_PLAYER_DOMAIN},
            platforms={MEDIA_PLAYER_DOMAIN},
            device_classes={MediaPlayerDeviceClass},
        ),
    )
    if any(
        config_entry.data.get(CONF_OPENAI_AGENT_ID)
        for config_entry in hass.config_entries.async_entries(DOMAIN)
    ):
        intent.async_register(hass, MassPlayMediaOnMediaPlayerHandler(hass))


class MassPlayMediaOnMediaPlayerHandler(intent.IntentHandler):
    """Handle PlayMediaOnMediaPlayer intents."""

    intent_type = INTENT_PLAY_MEDIA_ON_MEDIA_PLAYER

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize MassPlayMediaOnMediaPlayerHandler."""
        self.hass = hass

    async def _get_loaded_config_entry(self, hass: HomeAssistant) -> ConfigEntry:
        """Get the correct config entry."""
        config_entries = hass.config_entries.async_entries(DOMAIN)
        for config_entry in config_entries:
            if config_entry.state == ConfigEntryState.LOADED:
                return config_entry
        raise intent.IntentHandleError("Music Assistant not loaded")

    async def _async_get_matched_mass_player(
        self, intent_obj: intent.Intent, slots: intent._SlotsType
    ) -> str:
        name: str | None = slots.get(NAME_SLOT, {}).get(SLOT_VALUE)
        if name == "all":
            # Don't match on name if targeting all entities
            name = None
        area_name = slots.get(AREA_SLOT, {}).get(SLOT_VALUE)
        match_constraints = MatchTargetsConstraints(
            name=name,
            area_name=area_name,
            domains={MEDIA_PLAYER_DOMAIN},
        )
        if not match_constraints.has_constraints:
            # Fail if attempting to target all devices in the house
            raise IntentHandleError("Service handler cannot target all devices")
        state = await self._get_matched_state(intent_obj, match_constraints)
        entity_registry = er.async_get(self.hass)
        if entity := entity_registry.async_get(state.entity_id):
            return entity.unique_id.split("mass_", 1)[1]
        raise intent.IntentHandleError(
            f"No entities matched for: name={name}, area_name={area_name}"
        )

    async def _get_media_items(
        self, mass: MusicAssistantClient, media_id: str | list[str], media_type
    ) -> MediaItemType | list[MediaItemType]:
        if isinstance(media_id, list):
            return [
                (
                    await mass.music.get_item_by_name(
                        item, media_type=MediaType(media_type)
                    )
                ).to_dict()
                for item in media_id
            ]
        return await mass.music.get_item_by_name(
            media_id, media_type=MediaType(media_type)
        )

    async def _get_matched_state(
        self, intent_obj: intent.Intent, match_constraints: MatchTargetsConstraints
    ) -> State:
        match_result = intent.async_match_targets(intent_obj.hass, match_constraints)
        if not match_result.is_match:
            raise MatchFailedError(result=match_result, constraints=match_constraints)

        potential_states = [
            state
            for state in match_result.states
            if state.attributes.get(ATTR_MASS_PLAYER_TYPE)
        ]

        if not potential_states:
            raise MatchFailedError(result=match_result, constraints=match_constraints)
        return potential_states[0]

    slot_schema = {
        vol.Optional(NAME_SLOT): cv.string,
        vol.Optional(AREA_SLOT): cv.string,
        vol.Optional(QUERY_SLOT): cv.string,
        vol.Optional(RADIO_MODE_SLOT): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        # pylint: disable=too-many-locals
        response = intent_obj.create_response()
        slots = self.async_validate_slots(intent_obj.slots)
        config_entry: MusicAssistantConfigEntry = await self._get_loaded_config_entry(
            intent_obj.hass
        )
        mass = config_entry.runtime_data.mass
        mass_player_id = await self._async_get_matched_mass_player(intent_obj, slots)
        query = slots.get(QUERY_SLOT, {}).get(SLOT_VALUE)
        radio_mode_text = slots.get(RADIO_MODE_SLOT, {}).get(SLOT_VALUE, "")
        radio_mode = False
        if radio_mode_text:
            radio_mode = True
        if query:
            if not config_entry.data.get(CONF_OPENAI_AGENT_ID):
                raise intent.IntentHandleError(
                    "query requires using a conversation agent "
                    "https://music-assistant.io/integration/voice/#ma-specific-conversation-agent"
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
            media_item = await self._get_media_items(mass, media_id, media_type)
            radio_mode = json_payload.get(ATTR_RADIO_MODE, False)
        if not media_item:
            raise intent.IntentHandleError("No media item found")
        try:
            await mass.player_queues.play_media(
                queue_id=mass_player_id,
                media=(
                    media_item if isinstance(media_item, list) else media_item.to_dict()
                ),
                radio_mode=radio_mode,
            )
        except MusicAssistantError as err:
            raise intent.IntentHandleError(err.args[0] if err.args else "") from err

        response.response_type = intent.IntentResponseType.ACTION_DONE
        response.async_set_speech("Okay")
        return response

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
