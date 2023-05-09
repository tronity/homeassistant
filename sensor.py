from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.typing import StateType

from . import TronityEntity
from .const import DOMAIN, CONF_DATA_COORDINATOR


SENSOR_ENTITIES = [
    SensorEntityDescription(
        key="odometer",
        name="Odometer",
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DATA_COORDINATOR]

    entities: list[SensorEntity] = []

    for description in SENSOR_ENTITIES:
        entities.append(TronitySensorEntity(coordinator, description))

    async_add_entities(entities)


class TronitySensorEntity(SensorEntity, TronityEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description) -> None:
        """Initialize Tronity sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = "test"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return (self.coordinator.data["odometer"],)
