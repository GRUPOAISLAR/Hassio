"""Cover platform for Solidmation HPA-4202 window covering controllers."""
import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_COVER_DOWN,
    CMD_COVER_STOP,
    CMD_COVER_UP,
    CONF_INVERT_DIRECTION,
    COVER_STATE_DOWN,
    COVER_STATE_UP,
)
from .coordinator import HPA4911Coordinator
from .entity import HPA4911Entity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HPA-4202 cover entities."""
    coordinator = config_entry.runtime_data
    mac = config_entry.data["mac"]
    
    async_add_entities([HPA4911Cover(coordinator, mac)])
    _LOGGER.debug("HPA4911 cover entity setup completed for %s", config_entry.data["name"])

class HPA4911Cover(HPA4911Entity, CoverEntity):
    """HPA-4202 window covering entity.
    
    The device only reports the motor state (stopped / moving up / moving down),
    not the position, so open/closed is unknown and the state is assumed.
    """
    
    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    
    def __init__(self, coordinator: HPA4911Coordinator, mac: str) -> None:
        """Initialize the cover entity."""
        super().__init__(coordinator, mac)
        
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"{mac}_cover"
        self._attr_is_closed = None
        self._attr_is_opening = False
        self._attr_is_closing = False
        
        # Swap up/down when the motor is wired the other way round
        invert = bool(self.device_config.get(CONF_INVERT_DIRECTION, False))
        self._cmd_open = CMD_COVER_DOWN if invert else CMD_COVER_UP
        self._cmd_close = CMD_COVER_UP if invert else CMD_COVER_DOWN
        self._state_opening = COVER_STATE_DOWN if invert else COVER_STATE_UP
        self._state_closing = COVER_STATE_UP if invert else COVER_STATE_DOWN
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_data = self.coordinator.get_device_data(self.mac)
        if not device_data:
            return
            
        cover_status = device_data.get("cover_status")
        if cover_status:
            self._attr_is_opening = cover_status.state == self._state_opening
            self._attr_is_closing = cover_status.state == self._state_closing
        
        super()._handle_coordinator_update()
    
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        await self.coordinator.async_cover_command(self.mac, self._cmd_open)
    
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        await self.coordinator.async_cover_command(self.mac, self._cmd_close)
    
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.coordinator.async_cover_command(self.mac, CMD_COVER_STOP)
