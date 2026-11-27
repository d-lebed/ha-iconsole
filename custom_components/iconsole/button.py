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

_START_DESCRIPTION = ButtonEntityDescription(key=BUTTON_START, icon="mdi:play")
_PAUSE_DESCRIPTION = ButtonEntityDescription(key=BUTTON_PAUSE, icon="mdi:pause")
_STOP_DESCRIPTION = ButtonEntityDescription(key=BUTTON_STOP, icon="mdi:stop")

_ALL_BUTTON_KEYS: tuple[str, ...] = (BUTTON_START, BUTTON_PAUSE, BUTTON_STOP, "reset")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IConsoleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iConsole+ control buttons based on verified protocol capabilities."""
    client = entry.runtime_data.client
    unique_prefix = entry.runtime_data.unique_id
    ent_reg = er.async_get(hass)

    descriptions: list[ButtonEntityDescription] = []
    if client.protocol.supports_start_pause:
        descriptions.extend((_START_DESCRIPTION, _PAUSE_DESCRIPTION))
    if client.protocol.supports_stop:
        descriptions.append(_STOP_DESCRIPTION)

    active_keys = {desc.key for desc in descriptions}
    for key in _ALL_BUTTON_KEYS:
        if key not in active_keys:
            if ent_id := ent_reg.async_get_entity_id(
                "button", DOMAIN, f"{unique_prefix}-{key}"
            ):
                ent_reg.async_remove(ent_id)

    if descriptions:
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
