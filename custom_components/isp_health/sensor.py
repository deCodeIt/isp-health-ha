from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    entities: list[SensorEntity] = []
    for isp in coordinator.isps:
        entities.append(ISPLatencySensor(coordinator, isp["isp_name"], isp["isp_ip"]))
    entities.append(ISPSelectedSensor(coordinator))
    async_add_entities(entities)


class ISPLatencySensor(CoordinatorEntity[ISPHealthCoordinator], SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ISPHealthCoordinator, isp_name: str, isp_ip: str) -> None:
        super().__init__(coordinator)
        self._isp_name = isp_name
        slug = isp_name.lower().replace(" ", "_")
        self._attr_unique_id = f"isp_health_{slug}_latency"
        self._attr_name = "Latency"
        self._attr_device_info = _device_info(isp_name, isp_ip)

    @property
    def native_value(self) -> float | None:
        data: ISPHealthData = self.coordinator.data
        if data is None or self._isp_name not in data.statuses:
            return None
        return data.statuses[self._isp_name].latency_ms


class ISPSelectedSensor(CoordinatorEntity[ISPHealthCoordinator], SensorEntity):
    _attr_icon = "mdi:wan"

    def __init__(self, coordinator: ISPHealthCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "isp_health_selected"
        self._attr_name = "ISP Selected"

    @property
    def native_value(self) -> str | None:
        data: ISPHealthData = self.coordinator.data
        if data is None or data.selected_isp is None:
            return "No healthy ISP"
        return data.selected_isp

    @property
    def extra_state_attributes(self) -> dict:
        data: ISPHealthData = self.coordinator.data
        if data is None:
            return {}
        attrs = {}
        if data.selected_ip:
            attrs["ip"] = data.selected_ip
        for name, status in data.statuses.items():
            attrs[f"{name}_device"] = status.device_reachable
            attrs[f"{name}_internet"] = status.internet_reachable
        return attrs
