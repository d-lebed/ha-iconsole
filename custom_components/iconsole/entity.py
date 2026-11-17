"""Base entity for the iConsole+ (ChangYow) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import IConsoleConfigEntry, IConsoleRuntimeData
from .client import IConsoleClient


class IConsoleEntity(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], Entity
):
    """Base entity for iConsole+ devices."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: IConsoleConfigEntry,
        description: EntityDescription,
    ) -> None:
        self.entity_description = description
        self._data: IConsoleRuntimeData = entry.runtime_data
        self._attr_unique_id = f"{self._data.unique_id}-{description.key}"
        self._attr_device_info = self._data.device_info
        self._attr_translation_key = description.key

        super().__init__(self._data.coordinator)

    @property
    def key(self) -> str:
        return self.entity_description.key

    @property
    def client(self) -> IConsoleClient:
        return self._data.client

    @property
    def available(self) -> bool:
        return self.client.is_connected and super().available

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
