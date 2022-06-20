"""Config flow for Music Assistant integration."""

import os
from typing import List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player import (
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    MediaPlayerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.entity_component import DATA_INSTANCES

from .const import (
    CONF_CREATE_MASS_PLAYERS,
    CONF_FILE_DIRECTORY,
    CONF_FILE_ENABLED,
    CONF_HIDE_SOURCE_PLAYERS,
    CONF_PLAYER_ENTITIES,
    CONF_QOBUZ_ENABLED,
    CONF_QOBUZ_PASSWORD,
    CONF_QOBUZ_USERNAME,
    CONF_SPOTIFY_ENABLED,
    CONF_SPOTIFY_PASSWORD,
    CONF_SPOTIFY_USERNAME,
    CONF_TUNEIN_ENABLED,
    CONF_TUNEIN_USERNAME,
    DEFAULT_NAME,
    DOMAIN,
)

REQUIRED_FEATURES = (
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PLAY,
    SUPPORT_PAUSE,
)

DEFAULT_CONFIG = {
    CONF_HIDE_SOURCE_PLAYERS: True,
    CONF_CREATE_MASS_PLAYERS: True,
    CONF_PLAYER_ENTITIES: [],
    CONF_SPOTIFY_ENABLED: False,
    CONF_SPOTIFY_USERNAME: "",
    CONF_SPOTIFY_PASSWORD: "",
    CONF_QOBUZ_ENABLED: False,
    CONF_QOBUZ_USERNAME: "",
    CONF_QOBUZ_PASSWORD: "",
    CONF_TUNEIN_ENABLED: False,
    CONF_TUNEIN_USERNAME: "",
    CONF_FILE_ENABLED: False,
    CONF_FILE_DIRECTORY: "",
}


@callback
def hide_player_entities(
    hass: HomeAssistant, entity_ids: List[str], hide: bool
) -> None:
    """Hide/unhide media_player entities that are used as source for Music Assistant."""
    # Hide the wrapped entry if registered
    registry = er.async_get(hass)
    for entity_id in entity_ids:
        entity_entry = registry.async_get(entity_id)
        if entity_entry is None:
            continue
        if entity_entry.hidden and not hide:
            registry.async_update_entity(entity_id, hidden_by=None)
        elif not entity_entry.hidden and hide:
            registry.async_update_entity(
                entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
            )


@callback
def get_players_schema(hass: HomeAssistant, cur_conf: dict) -> vol.Schema:
    """Return player config schema."""
    # filter any non existing device id's from the list to prevent errors
    control_entities = hass.states.async_entity_ids("media_player")
    cur_ids = [
        item for item in cur_conf[CONF_PLAYER_ENTITIES] if item in control_entities
    ]
    # blacklist unsupported and mass entities
    exclude_entities = []
    for entity_id in hass.states.async_entity_ids(MP_DOMAIN):
        entity_comp = hass.data.get(DATA_INSTANCES, {}).get(MP_DOMAIN)
        entity: MediaPlayerEntity = entity_comp.get_entity(entity_id)
        if not entity or entity.platform.domain == DOMAIN:
            exclude_entities.append(entity_id)
            continue
        # require some basic features, most important `play_media`
        if not (
            entity.support_play_media
            and entity.support_play
            and entity.support_volume_set
        ):
            exclude_entities.append(entity_id)

    ent_reg = er.async_get(hass)
    exclude_entities = [
        x.entity_id
        for x in ent_reg.entities.values()
        if x.domain == MP_DOMAIN and x.platform == DOMAIN
    ]

    return vol.Schema(
        {
            vol.Optional(CONF_PLAYER_ENTITIES, default=cur_ids): selector.selector(
                {
                    "entity": {
                        "domain": "media_player",
                        "multiple": True,
                        "exclude_entities": exclude_entities,
                    }
                }
            )
        }
    )


@callback
def get_music_schema(cur_conf: dict):
    """Return music config schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SPOTIFY_ENABLED,
                default=cur_conf[CONF_SPOTIFY_ENABLED],
            ): bool,
            vol.Optional(
                CONF_SPOTIFY_USERNAME,
                default=cur_conf[CONF_SPOTIFY_USERNAME],
            ): str,
            vol.Optional(
                CONF_SPOTIFY_PASSWORD,
                default=cur_conf[CONF_SPOTIFY_PASSWORD],
            ): str,
            vol.Required(
                CONF_QOBUZ_ENABLED, default=cur_conf[CONF_QOBUZ_ENABLED]
            ): bool,
            vol.Optional(
                CONF_QOBUZ_USERNAME, default=cur_conf[CONF_QOBUZ_USERNAME]
            ): str,
            vol.Optional(
                CONF_QOBUZ_PASSWORD, default=cur_conf[CONF_QOBUZ_PASSWORD]
            ): str,
            vol.Required(
                CONF_TUNEIN_ENABLED,
                default=cur_conf[CONF_TUNEIN_ENABLED],
            ): bool,
            vol.Optional(
                CONF_TUNEIN_USERNAME, default=cur_conf[CONF_TUNEIN_USERNAME]
            ): str,
            vol.Required(
                CONF_FILE_ENABLED,
                default=cur_conf[CONF_FILE_ENABLED],
            ): bool,
            vol.Optional(
                CONF_FILE_DIRECTORY, default=cur_conf[CONF_FILE_DIRECTORY]
            ): str,
        }
    )


@callback
def validate_config(user_input: dict) -> dict:
    """Validate config and return dict with any errors."""
    errors = {}
    # check file provider config
    if user_input.get(CONF_FILE_ENABLED):
        # check if music directory is valid
        music_dir = user_input.get(CONF_FILE_DIRECTORY)
        if music_dir and not os.path.isdir(music_dir):
            errors[CONF_FILE_DIRECTORY] = "directory_not_exists"
    return errors


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Music Assistant."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""
        return OptionsFlowHandler(config_entry)

    def __init__(self, *args, **kwargs) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self.data = {**DEFAULT_CONFIG}

    async def async_step_user(self, user_input=None):
        """Handle getting base config from the user."""

        errors = None

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_music()

        return self.async_show_form(
            step_id="user",
            data_schema=get_players_schema(self.hass, self.data),
            last_step=False,
            errors=errors,
        )

    async def async_step_music(self, user_input=None):
        """Handle getting music provider config from the user."""

        errors = None

        if user_input is not None:
            self.data.update(user_input)
            errors = validate_config(user_input)

            if not errors:
                # config complete, store entry
                self.data.update(user_input)
                hide_player_entities(
                    self.hass,
                    self.data[CONF_PLAYER_ENTITIES],
                    self.data[CONF_HIDE_SOURCE_PLAYERS],
                )
                return self.async_create_entry(
                    title=DEFAULT_NAME, data={}, options={**self.data}
                )

        return self.async_show_form(
            step_id="music",
            data_schema=get_music_schema(self.data),
            last_step=True,
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """OptionsFlow handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.data = {**self.config_entry.options}

    async def async_step_init(self, user_input=None):
        """Handle getting base config from the user."""

        if user_input is not None:
            # figure out if any players are removed
            prev_players = set(self.data[CONF_PLAYER_ENTITIES])
            new_players = set(user_input.get(CONF_PLAYER_ENTITIES, []))
            removed_players = prev_players - new_players
            if removed_players:
                hide_player_entities(self.hass, removed_players, False)

            self.data.update(user_input)
            return await self.async_step_music()

        return self.async_show_form(
            step_id="init",
            data_schema=get_players_schema(self.hass, self.data),
            last_step=False,
        )

    async def async_step_music(self, user_input=None):
        """Handle getting music provider config from the user."""

        errors = None

        if user_input is not None:
            self.data.update(user_input)
            errors = validate_config(user_input)

            if not errors:
                return await self.async_step_adv()

        return self.async_show_form(
            step_id="music",
            data_schema=get_music_schema(self.data),
            last_step=False,
            errors=errors,
        )

    async def async_step_adv(self, user_input=None):
        """Handle getting advanced config options from the user."""

        if user_input is not None:
            self.data.update(user_input)
            errors = validate_config(user_input)

            if not errors:
                # config complete, store entry
                self.data.update(user_input)
                hide_player_entities(
                    self.hass,
                    self.data[CONF_PLAYER_ENTITIES],
                    self.data[CONF_HIDE_SOURCE_PLAYERS],
                )
                return self.async_create_entry(title=DEFAULT_NAME, data={**self.data})

        return self.async_show_form(
            step_id="adv",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HIDE_SOURCE_PLAYERS,
                        default=self.data[CONF_HIDE_SOURCE_PLAYERS],
                    ): selector.selector({"boolean": {}}),
                    vol.Required(
                        CONF_CREATE_MASS_PLAYERS,
                        default=self.data[CONF_CREATE_MASS_PLAYERS],
                    ): selector.selector({"boolean": {}}),
                }
            ),
            last_step=True,
        )
