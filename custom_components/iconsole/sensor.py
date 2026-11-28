"""Sensor platform for iConsole+ (ChangYow) integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IConsoleConfigEntry
from .const import (
    CONNECTION_STATUS_OPTIONS,
    KEY_CALORIES,
    KEY_CONNECTION_STATUS,
    KEY_DISTANCE,
    KEY_HEART_RATE,
    KEY_INCLINE,
    KEY_SPEED,
    KEY_TIME_ELAPSED,
    KEY_TRAINING_STATUS,
    TRAINING_STATUS_OPTIONS,
)
from .entity import IConsoleEntity

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=KEY_CONNECTION_STATUS,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:bluetooth-connect",
        options=CONNECTION_STATUS_OPTIONS,
    ),
    SensorEntityDescription(
        key=KEY_SPEED,
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_DISTANCE,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=KEY_CALORIES,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=KEY_HEART_RATE,
        icon="mdi:heart-pulse",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_INCLINE,
        icon="mdi:angle-acute",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_TIME_ELAPSED,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=KEY_TRAINING_STATUS,
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:run",
        options=TRAINING_STATUS_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IConsoleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iConsole+ sensor entities."""
    async_add_entities(
        IConsoleSensorEntity(entry=entry, description=desc)
        for desc in SENSOR_DESCRIPTIONS
    )


class IConsoleSensorEntity(IConsoleEntity, SensorEntity):
    """Representation of an iConsole+ sensor."""

    def __init__(
        self,
        entry: IConsoleConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(entry, description)
        self._attr_native_value = self.client.data.get(self.key)

    @property
    def available(self) -> bool:
        if self.key == KEY_CONNECTION_STATUS:
            return True
        return super().available

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data and self.key in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[self.key]
        self.async_write_ha_state()
