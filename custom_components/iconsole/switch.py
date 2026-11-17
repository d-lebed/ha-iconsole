"""Switch platform for iConsole+ (ChangYow) integration."""

from __future__ import annotations

import logging
from typing import Any, override

from bleak.exc import BleakError
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import STATE_OFF, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IConsoleConfigEntry
from .entity import IConsoleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IConsoleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iConsole+ Bluetooth connection switch."""
    async_add_entities(
        [
            IConsoleConnectionSwitch(
                entry=entry,
                description=SwitchEntityDescription(
                    key="connection",
                    device_class=SwitchDeviceClass.SWITCH,
                    entity_category=EntityCategory.CONFIG,
                ),
            )
        ]
    )


class IConsoleConnectionSwitch(IConsoleEntity, SwitchEntity, RestoreEntity):
    """Switch allowing the user to enable/disable the Bluetooth connection (e.g. to use the mobile app)."""

    @override
    async def async_added_to_hass(self) -> None:
        state = await self.async_get_last_state()
        self._attr_is_on = True

        if state is not None and state.state == STATE_OFF:
            await self.client.disconnect()
            self._attr_is_on = False

        await super().async_added_to_hass()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        self.client.need_connect = True
        self._attr_is_on = True
        self.async_write_ha_state()
        try:
            await self.client.connect()
        except BleakError as err:
            _LOGGER.debug(
                "iConsole+ not reachable right now (%s); will auto-connect on next BLE advertisement",
                err,
            )
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.disconnect()
        self._attr_is_on = False
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        return True
