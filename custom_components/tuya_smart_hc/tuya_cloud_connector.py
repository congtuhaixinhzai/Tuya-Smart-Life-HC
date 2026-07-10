import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util.ssl import get_default_context
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components import persistent_notification

from .tuya_connector import TuyaOpenAPI, TuyaOpenPulsar, TuyaCloudPulsarTopic
from .tuya_cloud_bridge import TuyaPulsarBridge
from .tuya_cloud_api import TuyaClimateAPI, TuyaGenericAPI, TuyaSensorAPI
from .tuya_cloud_const import (
    TUYA_API_ENDPOINTS,
    TUYA_PULSAR_ENDPOINTS,
    CONF_ENABLE_PULSAR,
    DEFAULT_ENABLE_PULSAR
)
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENDPOINT,
)

_LOGGER = logging.getLogger(__package__)

class TuyaConnector:
    """Manages Tuya Cloud connections, lifecycles, and API instances."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the connector."""
        self.hass = hass
        self.entry = entry
        
        self.api_client = None
        self.pulsar_client = None
        self.pulsar_bridge = None
        
        self.climate_api = None
        self.generic_api = None
        self.sensor_api = None

    async def async_setup_connections(self) -> None:
        """Set up and connect the API and Pulsar clients, and initialize APIs."""
        cloud_api = self.entry.options.get("cloud_api", {})
        endpoint = cloud_api.get(CONF_ENDPOINT, "")
        enable_pulsar = self.entry.options.get(CONF_ENABLE_PULSAR, DEFAULT_ENABLE_PULSAR)
        session = async_get_clientsession(self.hass)

        _LOGGER.debug("[%s] Setting up Tuya Cloud connections and APIs...", self.entry.title)

        self.api_client = TuyaOpenAPI(
            endpoint=endpoint,
            access_id=cloud_api.get(CONF_CLIENT_ID, ""),
            access_secret=cloud_api.get(CONF_CLIENT_SECRET, ""),
            session=session
        )

        res = await self.api_client.connect()
        if not res.get("success"):
            _LOGGER.error("[%s] Tuya Hub Login Error: %s", self.entry.title, res.get("msg"))
            await self.api_client.close()
            raise ConfigEntryAuthFailed(f"Tuya authentication failed: {res.get('msg')}")

        if enable_pulsar:
            # We don't have country mapping for pulsar in this logic, but we can guess it or just skip pulsar for now.
            # Wait, TuyaOpenPulsar uses wss://mqe.tuyaus.com:8285/ etc. We can map from endpoint.
            pulsar_endpoint = endpoint.replace("https://openapi", "wss://mqe") + ":8285/"
            self.pulsar_client = TuyaOpenPulsar(
                ws_endpoint=pulsar_endpoint,
                access_id=cloud_api.get(CONF_CLIENT_ID, ""),
                access_secret=cloud_api.get(CONF_CLIENT_SECRET, ""),
                topic=TuyaCloudPulsarTopic.PROD,
                session=session,
                ssl_context=get_default_context()
            )
            self.pulsar_bridge = TuyaPulsarBridge(self.hass, self.pulsar_client)
            await self.pulsar_client.start()
            self.hass.async_create_task(self.async_check_pulsar_connection())

        self.climate_api = TuyaClimateAPI(self.hass, client=self.api_client, log_prefix=f"[{self.entry.title}]")
        self.generic_api = TuyaGenericAPI(self.hass, client=self.api_client, log_prefix=f"[{self.entry.title}]") 
        self.sensor_api = TuyaSensorAPI(self.hass, client=self.api_client, log_prefix=f"[{self.entry.title}]")

    async def async_close_connections(self) -> None:
        """Close all connections."""
        _LOGGER.debug("[%s] Closing Tuya Cloud connections.", self.entry.title)
        
        if self.api_client:
            try:
                await self.api_client.close()
            except Exception as e:
                _LOGGER.debug("[%s] Error closing API client: %s", self.entry.title, e)

        if self.pulsar_client:
            try:
                await self.pulsar_client.stop()
            except Exception as e:
                _LOGGER.debug("[%s] Error stopping Pulsar client: %s", self.entry.title, e)

    async def async_check_pulsar_connection(self) -> bool:
        """Check Pulsar connection status at startup and notify if inactive."""
        if not self.pulsar_client:
            return False

        await asyncio.sleep(30)

        for _ in range(10):
            if self.pulsar_client.is_connected():
                return True
            await asyncio.sleep(3)

        if not self.pulsar_client.is_connected():
            persistent_notification.async_create(
                self.hass,
                title=f"Tuya Smart IR AC [{self.entry.title}]: Tuya Pulsar Stream Inactive",
                message=(
                    f"The **{self.entry.title}** integration established a network connection, but Home Assistant is receiving no data from the Tuya Pulsar stream.\n\n"
                    "This is usually caused by an incomplete configuration on your **Tuya Developer Platform**. "
                    "Please verify the following settings:\n\n"
                    "### 1. Enable the Message Service\n"
                    "* Go to **Cloud** -> **Development** -> Open your project -> **Message Service** tab.\n"
                    "* Ensure that the main Message Service toggle switch at the top is turned **ON (Enabled)**.\n\n"
                    "### 2. Configure the PRODUCTION Environment\n"
                    "* Make sure you select the **Production Environment** tab. *Home Assistant completely ignores the Test Environment*.\n"
                    "* Under the **Messaging Rules / Subscriptions** section, ensure you have explicitly enabled the following message types (**BizCode**):\n"
                    "  * `devicePropertyMessage` (Device Property Message)\n"
                    "  * `statusReport` (Status Report)\n"
                    "  * `deviceEventMessage` (Device Event Message)\n"
                    "  * `deviceActionResponseMessage` (Device Action Response Message)\n\n"
                    "**Note:** If these are already checked but the stream is still silent, try unchecking them, saving, and re-checking them to force Tuya to rebuild the routing rules.\n\n"
                    "The integration will automatically start processing data as soon as the cloud stream becomes active."
                ),
                notification_id=f"tuya_pulsar_connection_status_{self.entry.title.lower().replace(' ', '_')}"
            )

        return True
