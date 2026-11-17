"""Button platform for iConsole+ (ChangYow) integration."""

from __future__ import annotations

from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IConsoleConfigEntry
from .const import DOMAIN
from .entity import IConsoleEntity

BUTTON_START = "start_resume"
BUTTON_PAUSE = "pause"
BUTTON_STOP = "stop"

_D2_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(key=BUTTON_STOP, icon="mdi:stop"),
)

_D5_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(key=BUTTON_START, icon="mdi:play"),
    ButtonEntityDescription(key=BUTTON_PAUSE, icon="mdi:pause"),
    ButtonEntityDescription(key=BUTTON_STOP, icon="mdi:stop"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IConsoleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iConsole+ control buttons based on hardware revision (00.D2 vs 00.D5)."""
    client = entry.runtime_data.client
    unique_prefix = entry.runtime_data.unique_id
    ent_reg = er.async_get(hass)

    if client.protocol.supports_start_pause:
        descriptions = _D5_BUTTON_DESCRIPTIONS
        obsolete_keys = ("reset",)
    else:
        # 00.D2 treadmills require starting from the physical console panel for safety;
        # only Stop is exposed over BLE.
        descriptions = _D2_BUTTON_DESCRIPTIONS
        obsolete_keys = (BUTTON_START, BUTTON_PAUSE, "reset")

    for key in obsolete_keys:
        if ent_id := ent_reg.async_get_entity_id(
            "button", DOMAIN, f"{unique_prefix}-{key}"
        ):
            ent_reg.async_remove(ent_id)

    async_add_entities(
        IConsoleButtonEntity(entry=entry, description=desc)
        for desc in descriptions
    )


class IConsoleButtonEntity(IConsoleEntity, ButtonEntity):
    """Representation of an iConsole+ control button."""

    @override
    async def async_press(self) -> None:
        if self.key == BUTTON_START:
            await self.client.async_start_workout()
        elif self.key == BUTTON_PAUSE:
            await self.client.async_pause_workout()
        elif self.key == BUTTON_STOP:
            await self.client.async_stop_workout()
