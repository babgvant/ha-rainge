"""Constants for Rainforest EAGLE Local."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "rainforest_eagle_local"
PLATFORMS: Final = ["sensor"]

CONF_PROTOCOL: Final = "protocol"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_CLOUD_ID: Final = "cloud_id"
CONF_INSTALL_CODE: Final = "install_code"

DEFAULT_PROTOCOL: Final = "https"
DEFAULT_VERIFY_SSL: Final = False
DEFAULT_UPDATE_INTERVAL: Final = 10
MIN_UPDATE_INTERVAL: Final = 5
REQUEST_TIMEOUT: Final = 15
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=DEFAULT_UPDATE_INTERVAL)

INTEGRATION_VERSION: Final = "0.1.0"
