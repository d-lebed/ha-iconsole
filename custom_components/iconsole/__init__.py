"""The iConsole+ (ChangYow) integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import IConsoleClient
from .const import CONF_DEVICE_INFO, DOMAIN

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IConsoleRuntimeData:
    """Runtime data for an iConsole+ config entry."""

    entry_id: str
    unique_id: str
    device_info: dr.DeviceInfo
    client: IConsoleClient
    coordinator: DataUpdateCoordinator[dict[str, Any]]


type IConsoleConfigEntry = ConfigEntry[IConsoleRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: IConsoleConfigEntry) -> bool:
    """Set up iConsole+ (ChangYow) from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    cached_info: dict[str, str] = dict(
        entry.data.get(CONF_DEVICE_INFO)
        or {
            "manufacturer": "ChangYow",
            "model": "SI1022",
            "serial_number": "00.D2",
        }
    )

    coordinator: DataUpdateCoordinator[dict[str, Any]] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{address}",
    )

    @callback
    def _on_update(data: dict[str, Any]) -> None:
        coordinator.async_set_updated_data(dict(data))

    @callback
    def _on_disconnect() -> None:
        coordinator.async_set_updated_data(dict(client.data))

    srv_info = bluetooth.async_last_service_info(hass, address)
    client = IConsoleClient(
        address=address,
        name=srv_info.name if srv_info and srv_info.name else entry.title,
        ble_device=srv_info.device if srv_info else None,
        device_info=cached_info,
        on_update=_on_update,
        on_disconnect=_on_disconnect,
    )
    coordinator.data = dict(client.data)

    if srv_info is not None:
        try:
            await client.connect()
        except Exception as exc:
            _LOGGER.info(
                "iConsole+ %s (%s) is currently offline/asleep (%s); entities will be unavailable until it turns on",
                entry.title,
                address,
                exc,
            )

    if client.device_info and client.device_info != cached_info:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_DEVICE_INFO: dict(client.device_info)},
        )

    unique_id = "".join(x for x in address if x.isalnum()).lower()
    device_info = dr.DeviceInfo(
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        identifiers={(DOMAIN, unique_id)},
        name=entry.title,
        manufacturer=client.device_info.get("manufacturer", "ChangYow"),
        model=client.device_info.get("model", "iConsole+"),
        serial_number=client.device_info.get("serial_number"),
        hw_version=client.device_info.get("hw_version"),
        sw_version=client.device_info.get("sw_version"),
    )

    entry.runtime_data = IConsoleRuntimeData(
        entry_id=entry.entry_id,
        unique_id=unique_id,
        device_info=device_info,
        client=client,
        coordinator=coordinator,
    )

    reconnect_task: asyncio.Task[None] | None = None

    async def _async_connect_in_background() -> None:
        try:
            await client.connect()
            if client.device_info and client.device_info != entry.data.get(
                CONF_DEVICE_INFO
            ):
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_DEVICE_INFO: dict(client.device_info)},
                )
        except Exception as err:
            _LOGGER.debug("Background connect to %s failed: %s", address, err)

    @callback
    def _async_on_ble_event(
        info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        nonlocal reconnect_task
        client.set_ble_device(info.device)
        if (
            client.need_connect
            and not client.is_connected
            and not client.is_connecting
            and (reconnect_task is None or reconnect_task.done())
        ):
            reconnect_task = hass.async_create_task(_async_connect_in_background())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_on_ble_event,
            BluetoothCallbackMatcher(address=address),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_hass_stop_handler(_event: Event) -> None:
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_hass_stop_handler)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IConsoleConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.disconnect()
        bluetooth.async_rediscover_address(hass, entry.runtime_data.client.address)
    return unload_ok
