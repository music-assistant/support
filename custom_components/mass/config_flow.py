"""Config flow for MusicAssistant integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, selector
from music_assistant.client import MusicAssistantClient
from music_assistant.client.exceptions import CannotConnect, InvalidServerVersion
from music_assistant.common.models.api import ServerInfoMessage

from .const import CONF_ASSIST_AUTO_EXPOSE_PLAYERS, CONF_OPENAI_AGENT_ID, DOMAIN, LOGGER

DEFAULT_URL = "http://mass.local:8095"
DEFAULT_TITLE = "Music Assistant"


def get_manual_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the manual step."""
    default_url = user_input.get(CONF_URL, DEFAULT_URL)
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=default_url): str,
        }
    )


async def get_server_info(hass: HomeAssistant, url: str) -> ServerInfoMessage:
    """Validate the user input allows us to connect."""
    async with MusicAssistantClient(
        url, aiohttp_client.async_get_clientsession(hass)
    ) as client:
        return client.server_info


# ruff: noqa: ARG002


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MusicAssistant."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        self.server_info: ServerInfoMessage | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a manual configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual", data_schema=get_manual_schema({})
            )

        errors = {}
        try:
            self.server_info = await get_server_info(self.hass, user_input[CONF_URL])
            await self.async_set_unique_id(self.server_info.server_id)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidServerVersion:
            errors["base"] = "invalid_server_version"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self._async_create_entry_or_abort()

        return self.async_show_form(
            step_id="manual", data_schema=get_manual_schema(user_input), errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """
        Handle a discovered Mass server.

        This flow is triggered by the Zeroconf component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # abort if discovery info is not what we expect
        if "server_id" not in discovery_info.properties:
            return None
        # abort if we already have exactly this server_id
        # reload the integration if the host got updated
        server_id = discovery_info.properties["server_id"]
        base_url = discovery_info.properties["base_url"]
        await self.async_set_unique_id(server_id)
        self._abort_if_unique_id_configured(
            updates={CONF_URL: base_url},
            reload_on_update=True,
        )
        self.server_info = ServerInfoMessage.from_dict(discovery_info.properties)
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered server."""
        if user_input is not None:
            # Check that we can connect to the address.
            try:
                await get_server_info(self.hass, self.server_info.base_url)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
            return await self._async_create_entry_or_abort()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"url": self.server_info.base_url},
        )

    async def _async_create_entry_or_abort(self) -> FlowResult:
        """Return a config entry for the flow or abort if already configured."""
        assert self.server_info is not None

        for config_entry in self._async_current_entries():
            if config_entry.unique_id != self.server_info.server_id:
                continue
            self.hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    CONF_URL: self.server_info.base_url,
                },
                title=DEFAULT_TITLE,
            )
            await self.hass.config_entries.async_reload(config_entry.entry_id)
            raise AbortFlow("reconfiguration_successful")

        # Abort any other flows that may be in progress
        for progress in self._async_in_progress():
            self.hass.config_entries.flow.async_abort(progress["flow_id"])

        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data={
                CONF_URL: self.server_info.base_url,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Class to handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                # store as data instead of options - adjust this once the reconfigure flow is available
                data={
                    CONF_URL: user_input[CONF_URL],
                    CONF_OPENAI_AGENT_ID: user_input[CONF_OPENAI_AGENT_ID],
                    CONF_ASSIST_AUTO_EXPOSE_PLAYERS: user_input[
                        CONF_ASSIST_AUTO_EXPOSE_PLAYERS
                    ],
                },
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = self.mass_config_option_schema(self.config_entry)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )

    def mass_config_option_schema(
        self, config_entry: config_entries.ConfigEntry
    ) -> vol.Schema:
        """Return a schema for MusicAssistant completion options."""
        return {
            vol.Required(
                CONF_URL,
                default=config_entry.data.get(CONF_URL),
            ): str,
            vol.Optional(
                CONF_OPENAI_AGENT_ID,
                default=config_entry.data.get(CONF_OPENAI_AGENT_ID),
            ): selector.ConversationAgentSelector(
                selector.ConversationAgentSelectorConfig(language="en")
            ),
            vol.Optional(
                CONF_ASSIST_AUTO_EXPOSE_PLAYERS,
                default=(
                    config_entry.data.get(CONF_ASSIST_AUTO_EXPOSE_PLAYERS)
                    if config_entry.data.get(CONF_ASSIST_AUTO_EXPOSE_PLAYERS)
                    is not None
                    else False
                ),
            ): bool,
        }


class FailedConnect(HomeAssistantError):
    """Failed to connect to the MusicAssistant Server."""
