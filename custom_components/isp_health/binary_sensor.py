from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ISPHealthCoordinator, ISPHealthData


def _device_info(isp_name: str, isp_ip: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, isp_ip)},
        name=isp_name,
        manufacturer="ISP",
        model="FTTH Terminal",
        configuration_url=f"http://{isp_ip}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ISPHealthCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for isp in coordinator.isps:
        name = isp["isp_name"]
        ip = isp["isp_ip"]
        entities.append(ISPDeviceOnlineSensor(coordinator, name, ip))
        entities.append(ISPInternetOnlineSensor(coordinator, name, ip))
    async_add_entities(entities)


class ISPDeviceOnlineSensor(CoordinatorEntity[ISPHealthCoordinator], BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: ISPHealthCoordinator, isp_name: str, isp_ip: str) -> None:
        super().__init__(coordinator)
        self._isp_name = isp_name
        slug = isp_name.lower().replace(" ", "_")
        self._attr_unique_id = f"isp_health_{slug}_device_online"
        self._attr_name = "Device Online"
        self._attr_device_info = _device_info(isp_name, isp_ip)

    @property
    def is_on(self) -> bool | None:
        data: ISPHealthData = self.coordinator.data
        if data is None or self._isp_name not in data.statuses:
            return None
        return data.statuses[self._isp_name].device_reachable


class ISPInternetOnlineSensor(CoordinatorEntity[ISPHealthCoordinator], BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: ISPHealthCoordinator, isp_name: str, isp_ip: str) -> None:
        super().__init__(coordinator)
        self._isp_name = isp_name
        slug = isp_name.lower().replace(" ", "_")
        self._attr_unique_id = f"isp_health_{slug}_internet_online"
        self._attr_name = "Internet Online"
        self._attr_device_info = _device_info(isp_name, isp_ip)

    @property
    def is_on(self) -> bool | None:
        data: ISPHealthData = self.coordinator.data
        if data is None or self._isp_name not in data.statuses:
            return None
        return data.statuses[self._isp_name].internet_reachable
