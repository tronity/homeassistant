"""The Tronity integration."""
from __future__ import annotations
import json
from cachetools import TTLCache
from typing import Any
import aiohttp
import asyncio
from datetime import timedelta
import logging


from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_VEHICLE_ID,
    CONF_CLIENT_SECRET,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    CONF_AUTH_URL,
    CONF_DATA_COORDINATOR,
    CONF_VEHICLES_URL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
]

token_cache = TTLCache(maxsize=32, ttl=300)


class AuthFailedDuringFetch(UpdateFailed):
    """Raised when vehicle data fetch fails due to invalid authentication."""


async def _safe_json_response(response: aiohttp.ClientResponse, context: str) -> dict[str, Any]:
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
        raise UpdateFailed(
            f"Invalid API response while reading {context}: HTTP {response.status}"
        ) from err

    if not isinstance(payload, dict):
        raise UpdateFailed(f"Invalid API response while reading {context}: expected object")

    return payload

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tronity from a config entry."""

    client_id = entry.data[CONF_CLIENT_ID]
    client_secret = entry.data[CONF_CLIENT_SECRET]
    vehicle_id = entry.data[CONF_VEHICLE_ID]
    auth_url = CONF_AUTH_URL
    vehicle_url = CONF_VEHICLES_URL

    cache_key = entry.entry_id
    poll_interval_value = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )
    try:
        poll_interval = int(poll_interval_value)
    except (TypeError, ValueError):
        poll_interval = DEFAULT_POLL_INTERVAL
    poll_interval = max(MIN_POLL_INTERVAL, min(MAX_POLL_INTERVAL, poll_interval))

    async def get_bearer_token(client_id: str, client_secret: str) -> str:
        """Get bearer token for authentication."""

        if cache_key in token_cache:
            return token_cache[cache_key]

        try:
            session = async_get_clientsession(hass)
            async with session.post(
                auth_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "app",
                },
                timeout=10,
            ) as response:
                if response.status in (401, 403):
                    raise ConfigEntryAuthFailed(
                        "Authentication failed with provided credentials"
                    )
                if response.status not in (200, 201):
                    raise UpdateFailed(f"Failed to authenticate: {response.status}")
                response_json = await _safe_json_response(response, "authentication")
                bearer_token = response_json.get("access_token")
                if not bearer_token:
                    raise ConfigEntryAuthFailed(
                        "Authentication failed: missing access token in response"
                    )
                token_cache[cache_key] = bearer_token
                return bearer_token
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise UpdateFailed("Error while communicating with authentication API") from exc

    async def async_update_data():
        """Fetch data from Tronity API."""
        async def fetch_last_record(token: str) -> dict[str, Any]:
            headers = {"Authorization": f"Bearer {token}"}
            session = async_get_clientsession(hass)
            async with session.get(
                vehicle_url + vehicle_id + "/last_record",
                headers=headers,
            ) as response:
                if response.status in (401, 403):
                    raise AuthFailedDuringFetch(
                        "Authentication failed while fetching vehicle data"
                    )
                if response.status >= 400:
                    raise UpdateFailed(f"Failed to fetch vehicle data: {response.status}")

                data = await _safe_json_response(response, "vehicle last_record")
                _LOGGER.debug(
                    "Tronity update vehicle=%s raw values: charging=%r plugged=%r timestamp=%r",
                    vehicle_id,
                    data.get("charging"),
                    data.get("plugged"),
                    data.get("time") or data.get("timestamp") or data.get("createdAt"),
                )
                return data

        try:
            async with asyncio.timeout(60):
                bearer_token = await get_bearer_token(client_id, client_secret)
                try:
                    return await fetch_last_record(bearer_token)
                except AuthFailedDuringFetch:
                    token_cache.pop(cache_key, None)
                    refreshed_token = await get_bearer_token(client_id, client_secret)
                    try:
                        return await fetch_last_record(refreshed_token)
                    except AuthFailedDuringFetch as exc:
                        raise ConfigEntryAuthFailed(
                            "Authentication failed with provided credentials"
                        ) from exc

        except asyncio.TimeoutError as exc:
            raise UpdateFailed("Timeout while communicating with API") from exc
        except aiohttp.ClientError as exc:
            raise UpdateFailed("Error while communicating with vehicle API") from exc

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=poll_interval),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {CONF_DATA_COORDINATOR: coordinator}

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class TronityEntity(CoordinatorEntity):
    """Defines a base Tronity entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self.vehicle_id = entry.data[CONF_VEHICLE_ID]
        self.display_name = entry.title

    @property
    def data(self):
        """Shortcut to access coordinator data for the entity."""
        return self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return metadata for Home Assistant device registry grouping."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.vehicle_id)},
            name=self.display_name,
            manufacturer="Tronity",
            model="Connected Vehicle",
        )
