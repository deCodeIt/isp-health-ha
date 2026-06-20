import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ISP_ENABLED, CONF_ISP_IP, CONF_ISP_NAME, CONF_ISPS, DOMAIN
from .coordinator import ISPHealthCoordinator

_LOGGER = logging.getLogger(__name__)


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
        entities.append(ISPEnabledSwitch(hass, entry, coordinator, isp))
    async_add_entities(entities)


class ISPEnabledSwitch(SwitchEntity):
    _attr_icon = "mdi:toggle-switch"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: ISPHealthCoordinator,
        isp: dict,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._isp_name = isp[CONF_ISP_NAME]
        self._isp_ip = isp[CONF_ISP_IP]
        slug = self._isp_name.lower().replace(" ", "_")
        self._attr_unique_id = f"isp_health_{slug}_enabled"
        self._attr_name = "Enabled"
        self._attr_device_info = _device_info(self._isp_name, self._isp_ip)
        self._attr_is_on = isp.get(CONF_ISP_ENABLED, True)

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, enabled: bool) -> None:
        self._attr_is_on = enabled
        isps = list(self._entry.data.get(CONF_ISPS, []))
        for isp in isps:
            if isp[CONF_ISP_NAME] == self._isp_name:
                isp[CONF_ISP_ENABLED] = enabled
                break
        for isp in self._coordinator.isps:
            if isp[CONF_ISP_NAME] == self._isp_name:
                isp[CONF_ISP_ENABLED] = enabled
                break
        new_data = {**self._entry.data, CONF_ISPS: isps}
        self._hass.config_entries.async_update_entry(self._entry, data=new_data)
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()
