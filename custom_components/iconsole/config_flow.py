"""Config flow for iConsole+ (ChangYow) integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .client import read_device_info
from .const import CONF_DEVICE_INFO, DOMAIN, FFF0_SERVICE_UUID, ISSC_SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


def _is_iconsole_device(info: BluetoothServiceInfoBleak) -> bool:
    name = (info.name or info.advertisement.local_name or "").lower()
    if "iconsole" in name or "changyow" in name or "zipro" in name:
        return True
    uuids = [u.lower() for u in (info.service_uuids or [])]
    return FFF0_SERVICE_UUID in uuids or ISSC_SERVICE_UUID in uuids


class IConsoleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iConsole+ (ChangYow)."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_fetch_device_info(
        self, srv_info: BluetoothServiceInfoBleak
    ) -> dict[str, str]:
        """Try reading DIS (0x180A) briefly; fall back to defaults if device is busy/asleep."""
        default_info: dict[str, str] = {
            "manufacturer": "ChangYow",
            "model": srv_info.name or "iConsole+",
        }
        try:
            cli = await establish_connection(
                BleakClient,
                srv_info.device,
                srv_info.name or srv_info.address,
                max_attempts=2,
            )
            try:
                dis = await read_device_info(cli)
                if dis:
                    default_info.update(dis)
            finally:
                if cli.is_connected:
                    await cli.disconnect()
        except Exception as err:
            _LOGGER.debug(
                "Could not read DIS during config flow for %s (using defaults): %s",
                srv_info.address,
                err,
            )
        return default_info

    @staticmethod
    def _build_title(
        srv_info: BluetoothServiceInfoBleak, device_info: dict[str, str]
    ) -> str:
        manufacturer = device_info.get("manufacturer", "ChangYow")
        model = device_info.get("model", srv_info.name or "iConsole+")
        serial = device_info.get("serial_number", "")
        if serial:
            return f"{manufacturer} {model} ({serial})"
        return f"{manufacturer} {model}"

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        if user_input is not None:
            device_info = await self._async_fetch_device_info(self._discovery_info)
            title = self._build_title(self._discovery_info, device_info)
            return self.async_create_entry(
                title=title,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_DEVICE_INFO: device_info,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            srv_info = self._discovered_devices[address]
            device_info = await self._async_fetch_device_info(srv_info)
            title = self._build_title(srv_info, device_info)
            return self.async_create_entry(
                title=title,
                data={
                    CONF_ADDRESS: address,
                    CONF_DEVICE_INFO: device_info,
                },
            )

        current_addresses = self._async_current_ids()
        for info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_addresses:
                continue
            if _is_iconsole_device(info):
                self._discovered_devices[info.address] = info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            addr: f"{info.name or 'iConsole+'} ({addr})"
            for addr, info in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )
