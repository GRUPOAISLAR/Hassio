"""Constants for the Local BGH Smart integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "hpa4911"
INTEGRATION_NAME: Final = "Local BGH Smart"

MANUFACTURER: Final = "BGH"
MODEL: Final = "HPA4911 Smart Control Kit"

CONF_DEVICE_TYPE: Final = "device_type"
CONF_INVERT_DIRECTION: Final = "invert_direction"

DEVICE_TYPE_CLIMATE: Final = "climate"
DEVICE_TYPE_COVER: Final = "cover"
DEVICE_TYPES: Final = [DEVICE_TYPE_CLIMATE, DEVICE_TYPE_COVER]

COVER_MANUFACTURER: Final = "Solidmation"
COVER_MODEL: Final = "HPA-4202 Comando Wi-Fi para cortina"

# Window covering commands (HACommand_Constants in the Solidmation apps),
# sent without payload to endpoint 1
CMD_COVER_STOP: Final = 0x22
CMD_COVER_UP: Final = 0x28
CMD_COVER_DOWN: Final = 0x29

# Motor state reported in status type 4 (window covering)
COVER_STATE_STOPPED: Final = 0
COVER_STATE_UP: Final = 1
COVER_STATE_DOWN: Final = 2
