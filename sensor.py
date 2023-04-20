import aiohttp
import asyncio
import async_timeout
from datetime import timedelta
import logging


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)


from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_VEHICLES_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_VEHICLE_ID,
    CONF_DISPLAY_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def get_bearer_token(client_id: str, client_secret: str) -> str:
    base_url = CONF_BASE_URL

    async with aiohttp.ClientSession() as session:
        async with session.post(
            base_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "app",
            },
        ) as response:
            response_json = await response.json()
            bearer_token = response_json.get("access_token")

    return bearer_token


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    async_add_entities(
        [
            Odometer(hass, config_entry),
            Range(hass, config_entry),
            Level(hass, config_entry),
            Charging(hass, config_entry),
            Plugged(hass, config_entry),
            ChargerPower(hass, config_entry),
            ChargeRemainingTime(hass, config_entry),
            DisplayName(hass, config_entry),
        ],
        True,
    )


class TronityCoordinator(DataUpdateCoordinator):
    """Initialize Tronity Coordinator."""

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, vehicle_id: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="tronity",
            update_interval=timedelta(minutes=1),
        )
        self.client_id = client_id
        self.client_secret = client_secret
        self.vehicle_id = vehicle_id
        self.base_url = CONF_VEHICLES_URL

    async def _async_update_data(self):
        bearer_token = await get_bearer_token(self.client_id, self.client_secret)
        headers = {"Authorization": f"Bearer {bearer_token}"}

        try:
            async with async_timeout.timeout(30):
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.base_url + self.vehicle_id + "/last_record",
                        headers=headers,
                    ) as response:
                        data = await response.json(content_type="application/json")
                        return data
        except asyncio.TimeoutError as exc:
            raise UpdateFailed("Timeout while communicating with API") from exc
        except aiohttp.ClientError as err:
            raise _LOGGER(
                f"Error communicating with API: {err}. Retrying in a few seconds"
            ) from err


class Odometer(SensorEntity):
    SCAN_INTERVAL = timedelta(minutes=1)

    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self.coordinator = TronityCoordinator(
            hass,
            client_id=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_ID],
            client_secret=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_SECRET],
            vehicle_id=hass.data[DOMAIN][my_api.entry_id][CONF_VEHICLE_ID],
        )
        self._attr_name = (
            f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.odometer"
        )
        self._attr_device_class = SensorDeviceClass.DISTANCE
        self._attr_native_unit_of_measurement = "km"
        self._attr_native_value = 0

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        self._attr_native_value = data["odometer"]


class Range(SensorEntity):
    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self.coordinator = TronityCoordinator(
            hass,
            client_id=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_ID],
            client_secret=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_SECRET],
            vehicle_id=hass.data[DOMAIN][my_api.entry_id][CONF_VEHICLE_ID],
        )
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.remainig_range"
        self._attr_device_class = SensorDeviceClass.DISTANCE
        self._attr_native_unit_of_measurement = "km"
        self._attr_native_value = 0

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        self._attr_native_value = data["range"]


class Level(SensorEntity):
    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self.coordinator = TronityCoordinator(
            hass,
            client_id=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_ID],
            client_secret=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_SECRET],
            vehicle_id=hass.data[DOMAIN][my_api.entry_id][CONF_VEHICLE_ID],
        )
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.battery_level"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = "%"
        self._attr_native_value = 0

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        self._attr_native_value = data["level"]


class Charging(SensorEntity):
    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self.coordinator = TronityCoordinator(
            hass,
            client_id=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_ID],
            client_secret=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_SECRET],
            vehicle_id=hass.data[DOMAIN][my_api.entry_id][CONF_VEHICLE_ID],
        )
        self._attr_name = (
            f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.charging"
        )
        self._attr_device_class = None
        self._attr_native_value = 0

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        self._attr_native_value = data["charging"]


class Plugged(SensorEntity):
    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self.coordinator = TronityCoordinator(
            hass,
            client_id=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_ID],
            client_secret=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_SECRET],
            vehicle_id=hass.data[DOMAIN][my_api.entry_id][CONF_VEHICLE_ID],
        )
        self._attr_name = (
            f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.plugged"
        )
        self._attr_device_class = None
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [False, True]
        self._attr_native_value = False

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        self._attr_native_value = data["plugged"]


class ChargerPower(SensorEntity):
    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self.coordinator = TronityCoordinator(
            hass,
            client_id=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_ID],
            client_secret=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_SECRET],
            vehicle_id=hass.data[DOMAIN][my_api.entry_id][CONF_VEHICLE_ID],
        )
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.charger_power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = "kW"
        self._attr_native_value = 0

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        self._attr_native_value = data["chargerPower"]


class ChargeRemainingTime(SensorEntity):
    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self.coordinator = TronityCoordinator(
            hass,
            client_id=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_ID],
            client_secret=hass.data[DOMAIN][my_api.entry_id][CONF_CLIENT_SECRET],
            vehicle_id=hass.data[DOMAIN][my_api.entry_id][CONF_VEHICLE_ID],
        )
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.charge_remaining_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "min"
        self._attr_native_value = 0

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        self._attr_native_value = data["chargeRemainingTime"]


class DisplayName(SensorEntity):
    def __init__(self, hass: HomeAssistant, my_api: ConfigEntry) -> None:
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.display_name"
        self._attr_device_class = None
        self._attr_native_value = hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]

