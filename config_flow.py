"""Config flow for Tronity integration."""
from __future__ import annotations

import asyncio
import json
import logging
import aiohttp
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    CONF_AUTH_URL,
    CONF_VEHICLE_ID,
    CONF_VEHICLES_URL,
    CONF_DISPLAY_NAME,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID, default=""): str,
        vol.Required(CONF_CLIENT_SECRET, default=""): str,
        vol.Required(CONF_VEHICLE_ID, default=""): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID, default=""): str,
        vol.Required(CONF_CLIENT_SECRET, default=""): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""

    hub = TronityHub(
        hass, data[CONF_CLIENT_ID], data[CONF_CLIENT_SECRET], data[CONF_VEHICLE_ID]
    )

    bearer_token = await hub.authenticate()
    title = await hub.get_display_name(bearer_token)

    return {"title": title}


def _valid_poll_interval(value: Any) -> bool:
    return isinstance(value, int) and MIN_POLL_INTERVAL <= value <= MAX_POLL_INTERVAL


class TronityHub:
    """Initialize the TronityHub class for API authentication."""

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, vehicle_id: str
    ) -> None:
        """Initialize."""
        self.base_url = CONF_AUTH_URL
        self.vehicle_url = CONF_VEHICLES_URL
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret
        self.vehicle_id = vehicle_id

    async def _safe_json_response(
        self, response: aiohttp.ClientResponse, context: str
    ) -> dict[str, Any]:
        """Read JSON safely even when upstream sends an incorrect content type."""
        try:
            payload = await response.json(content_type=None)
        except (aiohttp.ContentTypeError, json.JSONDecodeError) as err:
            _LOGGER.warning(
                "Tronity returned invalid JSON for %s (status=%s, content-type=%s)",
                context,
                response.status,
                response.headers.get("Content-Type"),
            )
            raise CannotConnect from err

        if not isinstance(payload, dict):
            raise CannotConnect

        return payload

    async def get_bearer_token(self) -> str:
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                self.base_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "app",
                },
                timeout=10,
            ) as response:
                if response.status in (401, 403):
                    raise InvalidAuth
                if response.status >= 400:
                    raise CannotConnect

                response_json = await self._safe_json_response(response, "authentication")
                bearer_token = response_json.get("access_token")
                if not bearer_token:
                    raise InvalidAuth
                return bearer_token
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect from err

    async def get_display_name(self, bearer_token: str) -> str:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                self.vehicle_url + self.vehicle_id,
                headers=headers,
                timeout=10,
            ) as response:
                if response.status in (401, 403):
                    raise InvalidAuth
                if response.status >= 400:
                    raise CannotConnect

                data = await self._safe_json_response(response, "vehicle details")
                display_name = data.get("displayName")
                if not display_name:
                    raise CannotConnect
                return display_name
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect from err

    async def authenticate(self) -> str:
        return await self.get_bearer_token()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tronity."""

    VERSION = 1
    _reauth_entry: ConfigEntry | None = None

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry):
        """Create the options flow."""
        return TronityOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not _valid_poll_interval(user_input.get(CONF_POLL_INTERVAL)):
                errors["base"] = "invalid_poll_interval"
                return self.async_show_form(
                    step_id="user", data_schema=DATA_SCHEMA, errors=errors
                )

            await self.async_set_unique_id(user_input[CONF_VEHICLE_ID])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                entry_data = {**user_input, CONF_DISPLAY_NAME: info["title"]}
                return self.async_create_entry(title=info["title"], data=entry_data)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle config entry reauth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm and save new credentials for reauth."""
        errors: dict[str, str] = {}

        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            updated_data = {
                **self._reauth_entry.data,
                CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
            }

            try:
                info = await validate_input(self.hass, updated_data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    title=info["title"],
                    data={**updated_data, CONF_DISPLAY_NAME: info["title"]},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA,
                {
                    CONF_CLIENT_ID: self._reauth_entry.data.get(CONF_CLIENT_ID, ""),
                    CONF_CLIENT_SECRET: self._reauth_entry.data.get(
                        CONF_CLIENT_SECRET, ""
                    ),
                },
            ),
            errors=errors,
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotConnect(HomeAssistantError):
    """Error to indicate there was a connection problem."""


class TronityOptionsFlow(config_entries.OptionsFlow):
    """Handle Tronity options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            if not _valid_poll_interval(user_input.get(CONF_POLL_INTERVAL)):
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_POLL_INTERVAL,
                                default=self.config_entry.options.get(
                                    CONF_POLL_INTERVAL,
                                    self.config_entry.data.get(
                                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                                    ),
                                ),
                            ): int,
                        }
                    ),
                    errors={"base": "invalid_poll_interval"},
                )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL,
                            self.config_entry.data.get(
                                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                            ),
                        ),
                    ): int,
                }
            ),
        )
