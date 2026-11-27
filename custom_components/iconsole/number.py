"""Number platform for iConsole+ (ChangYow) integration."""

from __future__ import annotations

import dataclasses as dc

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IConsoleConfigEntry
from .const import DOMAIN, KEY_TARGET_INCLINE, KEY_TARGET_SPEED
from .entity import IConsoleEntity

_INCLINE_DESCRIPTION = NumberEntityDescription(
    key=KEY_TARGET_INCLINE,
    icon="mdi:angle-acute",
    native_unit_of_measurement="%",
    native_min_value=0.0,
    native_max_value=15.0,
    native_step=1.0,
)

_SPEED_DESCRIPTION = NumberEntityDescription(
    key=KEY_TARGET_SPEED,
    device_class=NumberDeviceClass.SPEED,
    native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    native_min_value=1.0,
    native_max_value=16.0,
    native_step=0.1,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IConsoleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iConsole+ number entities based on verified protocol capabilities."""
    client = entry.runtime_data.client
    unique_prefix = entry.runtime_data.unique_id
    ent_reg = er.async_get(hass)

    entities: list[IConsoleNumberEntity] = []

    if client.protocol.supports_target_incline:
        incline_desc = dc.replace(
            _INCLINE_DESCRIPTION,
            native_min_value=client.min_incline,
            native_max_value=client.max_incline,
        )
        entities.append(IConsoleNumberEntity(entry=entry, description=incline_desc))
    elif ent_id := ent_reg.async_get_entity_id(
        "number", DOMAIN, f"{unique_prefix}-{KEY_TARGET_INCLINE}"
    ):
        ent_reg.async_remove(ent_id)

    if client.protocol.supports_target_speed:
        speed_desc = dc.replace(
            _SPEED_DESCRIPTION,
            native_min_value=max(0.5, client.min_speed),
            native_max_value=client.max_speed,
        )
        entities.append(IConsoleNumberEntity(entry=entry, description=speed_desc))
    elif ent_id := ent_reg.async_get_entity_id(
        "number", DOMAIN, f"{unique_prefix}-{KEY_TARGET_SPEED}"
    ):
        ent_reg.async_remove(ent_id)

    if entities:
        async_add_entities(entities)


class IConsoleNumberEntity(IConsoleEntity, NumberEntity):
    """Representation of an iConsole+ target setting."""

    def __init__(
        self,
        entry: IConsoleConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        super().__init__(entry, description)
        self._attr_native_value = self.client.data.get(self.key, 0.0)

    async def async_set_native_value(self, value: float) -> None:
        if self.key == KEY_TARGET_INCLINE:
            await self.client.async_set_incline(value)
        elif self.key == KEY_TARGET_SPEED:
            await self.client.async_set_speed(value)

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data and self.key in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[self.key]
        self.async_write_ha_state()
