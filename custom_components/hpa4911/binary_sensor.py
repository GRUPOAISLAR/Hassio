"""Binary sensor platform for HPA4911: AC running, detected by vibration."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import VIBRATION_RUNNING_THRESHOLD
from .coordinator import HPA4911Coordinator
from .entity import HPA4911Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HPA4911 binary sensors."""
    coordinator = config_entry.runtime_data
    mac = config_entry.data["mac"]
    async_add_entities([HPA4911RunningSensor(coordinator, mac)])


class HPA4911RunningSensor(HPA4911Entity, BinarySensorEntity):
    """AC unit running, from the vibration level the kit reports.

    Unlike the climate mode, which is the state the kit believes it sent by IR,
    this reflects whether the unit is actually working.
    """

    def __init__(self, coordinator: HPA4911Coordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_name = "Running"
        self._attr_unique_id = f"{mac}_running"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_is_on = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_data = self.coordinator.get_device_data(self.mac)
        if not device_data:
            return

        device_status = device_data.get("device_status")
        if device_status and device_status.vibration is not None:
            self._attr_is_on = device_status.vibration > VIBRATION_RUNNING_THRESHOLD
            _LOGGER.debug("Updated running sensor to %s (vibration %s)", self._attr_is_on, device_status.vibration)

        super()._handle_coordinator_update()
