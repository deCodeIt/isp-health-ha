import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_EXTERNAL_TARGETS,
    CONF_ISPS,
    CONF_PING_TIMEOUT,
    CONF_POLL_INTERVAL,
    DEFAULT_EXTERNAL_TARGETS,
    DEFAULT_PING_TIMEOUT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import ISPHealthCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    isps = entry.data.get(CONF_ISPS, [])
    coordinator = ISPHealthCoordinator(
        hass,
        isps=isps,
        poll_interval=entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        ping_timeout=entry.data.get(CONF_PING_TIMEOUT, DEFAULT_PING_TIMEOUT),
        external_targets=entry.data.get(
            CONF_EXTERNAL_TARGETS, DEFAULT_EXTERNAL_TARGETS
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
