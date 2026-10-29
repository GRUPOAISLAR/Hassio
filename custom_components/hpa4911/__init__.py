"""Local BGH Smart integration for Home Assistant."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_CLIMATE, DEVICE_TYPE_COVER
from .coordinator import HPA4911Coordinator, get_coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BY_TYPE = {
    DEVICE_TYPE_CLIMATE: [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR],
    DEVICE_TYPE_COVER: [Platform.COVER, Platform.SENSOR],
}

type HPA4911ConfigEntry = ConfigEntry[HPA4911Coordinator]


def _platforms(entry: ConfigEntry) -> list[Platform]:
    """Return the platforms for the entry's device type (entries without one are HVAC kits)."""
    return PLATFORMS_BY_TYPE[entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_CLIMATE)]

async def async_setup_entry(hass: HomeAssistant, entry: HPA4911ConfigEntry) -> bool:
    """Set up Local BGH Smart from a config entry."""
    # Get or create the shared coordinator
    coordinator = await get_coordinator(hass)
    
    # Add this device to the coordinator
    coordinator.add_device(entry)
    
    # Verify we can connect before proceeding
    try:
        await coordinator._async_setup()
    except Exception as err:
        coordinator.remove_device(entry)
        raise ConfigEntryNotReady(
            f"Unable to connect to device: {err}"
        ) from err
    
    # Store the coordinator reference in runtime_data
    entry.runtime_data = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: HPA4911ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
    if unload_ok:
        coordinator = entry.runtime_data
        # Remove this device from the coordinator
        coordinator.remove_device(entry)
        
        # If no more devices, shutdown the coordinator
        if not coordinator.devices:
            await coordinator.async_shutdown()
    return unload_ok