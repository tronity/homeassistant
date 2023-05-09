from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.helpers.typing import StateType

from . import TronityEntity
from .const import DOMAIN, CONF_DATA_COORDINATOR


SENSOR_ENTITIES = [
    SensorEntityDescription(
        key="odometer",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="range",
        icon="mdi:gas-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="charging",
        icon="mdi:battery-charging",
    ),
    SensorEntityDescription(
        key="plugged",
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENUM,
        options=[False, True],
    ),
    SensorEntityDescription(
        key="chargerPower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="chargeRemainingTime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DATA_COORDINATOR]

    entities: list[SensorEntity] = [DisplayName(coordinator, config_entry)]

    for description in SENSOR_ENTITIES:
        entities.append(TronitySensorEntity(coordinator, description, config_entry))

    async_add_entities(entities)


class TronitySensorEntity(SensorEntity, TronityEntity):
    """Representation of a Tronity vehicle sensor."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description, config_entry: ConfigEntry) -> None:
        """Initialize Tronity sensor."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.vehicle_id}_{description.key}"

    @property
    def name(self) -> str:
        """Return name of the sensor."""
        return f"tronity.{self.display_name}.{self.entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""

        return self.coordinator.data[self.entity_description.key]


class DisplayName(SensorEntity, TronityEntity):
    """Representation of a Tronity vehicle sensor."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """Initialize Tronity sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{self.vehicle_id}_display_name"
        self._attr_icon = "mdi:car"

    @property
    def name(self) -> str:
        """Return name of the sensor."""
        return "tronity.display_name"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""

        return self.display_name
