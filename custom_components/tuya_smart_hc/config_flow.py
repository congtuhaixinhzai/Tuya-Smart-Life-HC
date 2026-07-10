from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import TuyaMobileApiError, TuyaSmartLifeMobileApi
from .api import TuyaMobileApiError, TuyaSmartLifeMobileApi
from .const import (
    CONF_APP_ID,
    CONF_APP_RN_VERSION,
    CONF_APP_SECRET,
    CONF_API_REGION,
    CONF_APP_VERSION,
    CONF_BMP_KEY,
    CONF_CERT_SHA256,
    CONF_CHANNEL,
    CONF_CH_KEY,
    CONF_COUNTRY_CODE,
    CONF_CP,
    CONF_DEVICE_CORE_VERSION,
    CONF_ET,
    CONF_MOBILE_APP,
    CONF_NATIVE_KEY_TEXT,
    CONF_ND,
    CONF_OS_SYSTEM,
    CONF_PACKAGE_NAME,
    CONF_PLATFORM,
    CONF_SDK_VERSION,
    CONF_SELECTED_HOME_IDS,
    DEFAULT_API_REGION,
    DEFAULT_MOBILE_APP,
    CONF_TTID,
    DOMAIN,
    MOBILE_APP_SMART_LIFE,
    MOBILE_APP_TUYA,
    mobile_app_profile,
    ENTRY_RUNTIME,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_TEMP_MIN,
    CONF_TEMP_MAX,
    CONF_TEMP_STEP,
    CONF_HVAC_POWER_ON,
    CONF_TEMP_POWER_ON,
    CONF_FAN_POWER_ON,
    CONF_CUSTOM_POWER_ON,
    POWER_ON_NEVER,
    POWER_ON_ALWAYS,
    POWER_ON_ONLY_OFF,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENDPOINT,
    CONF_USER_ID,
    CONF_INFRARED_ID,
    CONF_DEVICE_ID,
    DEVICE_TYPE_CLIMATES,
)
from .models import TuyaHome, TuyaMobileConfig

_LOGGER = logging.getLogger(__name__)


def mobile_config_from_data(data: dict[str, Any]) -> TuyaMobileConfig:
    mobile_app = data.get(CONF_MOBILE_APP, DEFAULT_MOBILE_APP)
    profile = mobile_app_profile(mobile_app)

    return TuyaMobileConfig(
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        mobile_app=mobile_app,
        country_code=data.get(CONF_COUNTRY_CODE, profile[CONF_COUNTRY_CODE]),
        api_region=data.get(CONF_API_REGION, DEFAULT_API_REGION),
        app_id=data.get(CONF_APP_ID, profile[CONF_APP_ID]),
        app_secret=data.get(CONF_APP_SECRET) or profile.get(CONF_APP_SECRET),
        cert_sha256=data.get(CONF_CERT_SHA256) or profile.get(CONF_CERT_SHA256),
        bmp_key=data.get(CONF_BMP_KEY) or profile.get(CONF_BMP_KEY),
        native_key_text=data.get(CONF_NATIVE_KEY_TEXT) or profile[CONF_NATIVE_KEY_TEXT],
        package_name=data.get(CONF_PACKAGE_NAME, profile[CONF_PACKAGE_NAME]),
        app_version=data.get(CONF_APP_VERSION, profile[CONF_APP_VERSION]),
        app_rn_version=data.get(CONF_APP_RN_VERSION, profile[CONF_APP_RN_VERSION]),
        sdk_version=data.get(CONF_SDK_VERSION, profile[CONF_SDK_VERSION]),
        device_core_version=data.get(
            CONF_DEVICE_CORE_VERSION, profile[CONF_DEVICE_CORE_VERSION]
        ),
        os_system=data.get(CONF_OS_SYSTEM, profile[CONF_OS_SYSTEM]),
        ch_key=data.get(CONF_CH_KEY, profile[CONF_CH_KEY]),
        ttid=data.get(CONF_TTID, profile[CONF_TTID]),
        et=data.get(CONF_ET, profile[CONF_ET]),
        platform=data.get(CONF_PLATFORM, profile[CONF_PLATFORM]),
        channel=data.get(CONF_CHANNEL, profile[CONF_CHANNEL]),
        cp=data.get(CONF_CP, profile[CONF_CP]),
        nd=data.get(CONF_ND, profile[CONF_ND]),
    )


def user_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    values = user_input or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_MOBILE_APP,
                default=values.get(CONF_MOBILE_APP, DEFAULT_MOBILE_APP),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": MOBILE_APP_TUYA, "label": "Tuya"},
                        {
                            "value": MOBILE_APP_SMART_LIFE,
                            "label": "Smart Life",
                        },
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_EMAIL, default=values.get(CONF_EMAIL, "")): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


def homes_schema(
    homes: list[TuyaHome],
    selected: list[str] | None = None,
) -> vol.Schema:
    default = [home.id for home in homes] if selected is None else selected
    return vol.Schema(
        {
            vol.Required(CONF_SELECTED_HOME_IDS, default=default): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": home.id, "label": f"{home.name} ({home.id})"}
                            for home in homes
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            )
        }
    )


def selected_home_ids_from_user_input(user_input: dict[str, Any]) -> list[str]:
    value = user_input.get(CONF_SELECTED_HOME_IDS, [])
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(home_id) for home_id in value]


class TuyaSmartLifeLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._user_data: dict[str, Any] = {}
        self._homes: list[TuyaHome] = []

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                config = mobile_config_from_data(user_input)
                api = TuyaSmartLifeMobileApi(config)
                session, homes = await self.hass.async_add_executor_job(
                    self._login_and_list_homes, api
                )
                await self.async_set_unique_id(
                    f"{user_input[CONF_EMAIL].lower()}:{config.app_id}"
                )
                self._abort_if_unique_id_configured()
                self._user_data = dict(user_input)
                self._homes = homes
                _LOGGER.debug(
                    "Authenticated %s mobile account uid=%s region=%s endpoint=%s homes=%s",
                    config.mobile_app,
                    session.uid,
                    session.region,
                    session.endpoint,
                    len(homes),
                )
                return await self.async_step_select_homes()
            except TuyaMobileApiError as err:
                _LOGGER.warning("Tuya mobile login failed: %s", err)
                errors["base"] = _error_key_from_mobile_error(err)
            except Exception:
                _LOGGER.exception("Unexpected Tuya mobile login error")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=user_schema(user_input),
            errors=errors,
        )

    async def async_step_select_homes(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = selected_home_ids_from_user_input(user_input)
            data = dict(self._user_data)
            data[CONF_SELECTED_HOME_IDS] = selected
            return self.async_create_entry(
                title=f"Tuya Smart Life HC ({self._user_data[CONF_EMAIL]})",
                data=data,
            )

        return self.async_show_form(
            step_id="select_homes",
            data_schema=homes_schema(self._homes),
            errors=errors,
        )

    @staticmethod
    def _login_and_list_homes(
        api: TuyaSmartLifeMobileApi,
    ) -> tuple[Any, list[TuyaHome]]:
        session = api.login()
        homes = api.list_homes(session)
        if not homes:
            raise TuyaMobileApiError("No homes returned by Tuya mobile API")
        return session, homes

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return TuyaSmartLifeLocalOptionsFlow()


def _error_key_from_mobile_error(err: TuyaMobileApiError) -> str:
    message = str(err).upper()
    if "ILLEGAL_CLIENT_ID" in message or "CLIENT" in message:
        return "invalid_client"
    if (
        "PASSWORD" in message
        or "PASSWD" in message
        or "USER_NOT_EXIST" in message
        or "USER_NOT_FOUND" in message
    ):
        return "invalid_auth"
    return "cannot_connect"


class TuyaSmartLifeLocalOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._homes: list[TuyaHome] = []
        self._selected_climate: str | None = None

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["select_homes", "add_climate", "edit_climate", "remove_climate", "backup_climates", "restore_climates", "cloud_api"],
        )

    async def async_step_select_homes(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        data = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            selected = selected_home_ids_from_user_input(user_input)
            new_options = dict(self.config_entry.options)
            new_options[CONF_SELECTED_HOME_IDS] = selected
            return self.async_create_entry(
                title="",
                data=new_options,
            )

        try:
            config = mobile_config_from_data(data)
            api = TuyaSmartLifeMobileApi(config)
            _, homes = await self.hass.async_add_executor_job(
                TuyaSmartLifeLocalConfigFlow._login_and_list_homes,
                api,
            )
            self._homes = homes
        except Exception:
            _LOGGER.exception("Unable to refresh Tuya homes for options flow")
            errors["base"] = "cannot_connect"
            self._homes = [
                TuyaHome(id=str(home_id), name=str(home_id))
                for home_id in data.get(CONF_SELECTED_HOME_IDS, [])
            ]

        selected = list(
            self.config_entry.options.get(
                CONF_SELECTED_HOME_IDS,
                self.config_entry.data.get(CONF_SELECTED_HOME_IDS, []),
            )
        )
        return self.async_show_form(
            step_id="select_homes",
            data_schema=homes_schema(self._homes, selected),
            errors=errors,
        )

    async def async_step_add_climate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            new_options = dict(self.config_entry.options)
            ir_climates = list(new_options.get(DEVICE_TYPE_CLIMATES, []))
            # Just append the new climate
            ir_climates.append(user_input)
            new_options[DEVICE_TYPE_CLIMATES] = ir_climates
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="add_climate",
            data_schema=vol.Schema({
                vol.Required(CONF_INFRARED_ID): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required("name"): str,
            })
        )

    async def async_step_edit_climate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if not self._selected_climate:
            self._next_action = "async_step_edit_climate"
            return await self.async_step_select_climate()

        ir_climates = list(self.config_entry.options.get(DEVICE_TYPE_CLIMATES, []))
        index = next((i for i, c in enumerate(ir_climates) if c.get(CONF_DEVICE_ID) == self._selected_climate), None)
        
        if index is None:
            return self.async_abort(reason="device_not_found")

        climate_options = ir_climates[index]

        if user_input is not None:
            new_options = dict(self.config_entry.options)
            ir_climates[index] = {**climate_options, **user_input}
            new_options[DEVICE_TYPE_CLIMATES] = ir_climates
            self._selected_climate = None
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="edit_climate",
            data_schema=vol.Schema({
                vol.Optional(CONF_TEMPERATURE_SENSOR, default=climate_options.get(CONF_TEMPERATURE_SENSOR, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_HUMIDITY_SENSOR, default=climate_options.get(CONF_HUMIDITY_SENSOR, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
                ),
                vol.Optional(CONF_TEMP_MIN, default=climate_options.get(CONF_TEMP_MIN, 16.0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10.0, max=30.0, step=1.0)
                ),
                vol.Optional(CONF_TEMP_MAX, default=climate_options.get(CONF_TEMP_MAX, 30.0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=16.0, max=40.0, step=1.0)
                ),
                vol.Optional(CONF_TEMP_STEP, default=climate_options.get(CONF_TEMP_STEP, 1.0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.5, max=2.0, step=0.5)
                ),
                vol.Optional(CONF_HVAC_POWER_ON, default=climate_options.get(CONF_HVAC_POWER_ON, POWER_ON_ONLY_OFF)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[POWER_ON_NEVER, POWER_ON_ALWAYS, POWER_ON_ONLY_OFF],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional(CONF_TEMP_POWER_ON, default=climate_options.get(CONF_TEMP_POWER_ON, POWER_ON_ONLY_OFF)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[POWER_ON_NEVER, POWER_ON_ALWAYS, POWER_ON_ONLY_OFF],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional(CONF_FAN_POWER_ON, default=climate_options.get(CONF_FAN_POWER_ON, POWER_ON_ONLY_OFF)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[POWER_ON_NEVER, POWER_ON_ALWAYS, POWER_ON_ONLY_OFF],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional(CONF_CUSTOM_POWER_ON, default=climate_options.get(CONF_CUSTOM_POWER_ON, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="button")
                ),
            }),
        )

    async def async_step_remove_climate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if not self._selected_climate:
            self._next_action = "async_step_remove_climate"
            return await self.async_step_select_climate()

        ir_climates = list(self.config_entry.options.get(DEVICE_TYPE_CLIMATES, []))
        remaining = [c for c in ir_climates if c.get(CONF_DEVICE_ID) != self._selected_climate]
        
        self._selected_climate = None
        new_options = dict(self.config_entry.options)
        new_options[DEVICE_TYPE_CLIMATES] = remaining
        return self.async_create_entry(title="", data=new_options)

    async def async_step_select_climate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        ir_climates = self.config_entry.options.get(DEVICE_TYPE_CLIMATES, [])
        if not ir_climates:
            return self.async_abort(reason="no_ir_climates")

        if user_input is not None:
            self._selected_climate = user_input["climate_id"]
            return await getattr(self, self._next_action)()

        options = [
            {"value": c.get(CONF_DEVICE_ID), "label": f"{c.get('name')} ({c.get(CONF_DEVICE_ID)})"}
            for c in ir_climates
        ]

        return self.async_show_form(
            step_id="select_climate",
            data_schema=vol.Schema({
                vol.Required("climate_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            })
        )

    async def async_step_cloud_api(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        cloud_api_options = self.config_entry.options.get("cloud_api", {})

        if user_input is not None:
            new_options = dict(self.config_entry.options)
            new_options["cloud_api"] = {
                CONF_CLIENT_ID: user_input.get(CONF_CLIENT_ID, "").strip(),
                CONF_CLIENT_SECRET: user_input.get(CONF_CLIENT_SECRET, "").strip(),
                CONF_ENDPOINT: user_input.get(CONF_ENDPOINT, "").strip(),
                CONF_USER_ID: user_input.get(CONF_USER_ID, "").strip(),
            }
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="cloud_api",
            data_schema=vol.Schema({
                vol.Optional(CONF_CLIENT_ID, default=cloud_api_options.get(CONF_CLIENT_ID, "")): str,
                vol.Optional(CONF_CLIENT_SECRET, default=cloud_api_options.get(CONF_CLIENT_SECRET, "")): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_ENDPOINT, default=cloud_api_options.get(CONF_ENDPOINT, "https://openapi.tuyaus.com")): str,
                vol.Optional(CONF_USER_ID, default=cloud_api_options.get(CONF_USER_ID, "")): str,
            }),
            errors=errors,
        )

    async def async_step_backup_climates(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle manual backup of configuration."""
        import json
        
        backup_data = {
            "climates": self.config_entry.options.get(DEVICE_TYPE_CLIMATES, []),
            "cloud_api": self.config_entry.options.get("cloud_api", {})
        }
        
        if not backup_data["climates"] and not backup_data["cloud_api"]:
            return self.async_abort(reason="no_config_to_backup")

        if user_input is not None:
            return self.async_create_entry(title="", data=self.config_entry.options)

        # Perform backup
        backup_path = self.hass.config.path("tuya_smart_hc_config.json")
        try:
            def _write_backup():
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)
            await self.hass.async_add_executor_job(_write_backup)
        except Exception as e:
            _LOGGER.error("Failed to manual backup Tuya config: %s", e)

        return self.async_show_form(
            step_id="backup_climates",
            data_schema=vol.Schema({}),
            description_placeholders={
                "path": backup_path,
                "climates_count": str(len(backup_data["climates"]))
            },
        )

    async def async_step_restore_climates(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle restoring climates - show menu to choose source."""
        return self.async_show_menu(
            step_id="restore_climates",
            menu_options=["restore_from_server", "restore_from_json"],
        )

    async def async_step_restore_from_server(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle restoring configuration from server backup file."""
        import json
        import os
        backup_path = self.hass.config.path("tuya_smart_hc_config.json")
        fallback_path = self.hass.config.path("tuya_smart_hc_climates.json")

        backup_data = None
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
            except Exception as e:
                _LOGGER.error("Failed to read backup file: %s", e)
        elif os.path.exists(fallback_path):
            try:
                with open(fallback_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
            except Exception as e:
                _LOGGER.error("Failed to read backup file: %s", e)

        if not backup_data:
            return self.async_abort(reason="no_backup_found")

        if user_input is not None:
            return self._merge_config(backup_data)

        return self.async_show_form(
            step_id="restore_from_server",
            data_schema=vol.Schema({}),
        )

    async def async_step_restore_from_json(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle restoring climates from pasted JSON content."""
        import json
        errors: dict[str, str] = {}

        if user_input is not None:
            json_text = user_input.get("json_content", "").strip()
            if json_text:
                try:
                    backup_data = json.loads(json_text)
                    if isinstance(backup_data, list) and len(backup_data) > 0:
                        return self._merge_config(backup_data)
                    elif isinstance(backup_data, dict):
                        return self._merge_config(backup_data)
                    else:
                        errors["base"] = "invalid_json"
                except json.JSONDecodeError:
                    errors["base"] = "invalid_json"
            else:
                errors["base"] = "invalid_json"

        return self.async_show_form(
            step_id="restore_from_json",
            data_schema=vol.Schema({
                vol.Required("json_content"): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True,
                        type=selector.TextSelectorType.TEXT,
                    )
                ),
            }),
            errors=errors,
        )

    def _merge_config(self, backup_data: list | dict) -> config_entries.ConfigFlowResult:
        """Merge backup config into current options."""
        backup_climates = []
        backup_cloud_api = {}
        
        if isinstance(backup_data, list):
            backup_climates = backup_data
        elif isinstance(backup_data, dict):
            backup_climates = backup_data.get("climates", [])
            backup_cloud_api = backup_data.get("cloud_api", {})

        current_climates = self.config_entry.options.get(DEVICE_TYPE_CLIMATES, [])
        climates_dict = {}
        for c in current_climates:
            key = c.get("device_id") or c.get("id", "")
            climates_dict[key] = c
        for c in backup_climates:
            key = c.get("device_id") or c.get("id", "")
            if "id" not in c:
                c["id"] = str(uuid.uuid4())
            climates_dict[key] = c

        new_options = {**self.config_entry.options}
        new_options[DEVICE_TYPE_CLIMATES] = list(climates_dict.values())
        
        if backup_cloud_api:
            current_cloud_api = new_options.get("cloud_api", {})
            new_cloud_api = {**current_cloud_api, **backup_cloud_api}
            new_options["cloud_api"] = new_cloud_api

        _LOGGER.warning("MERGE_CONFIG SUCCESS! Options length: %s", len(new_options.get(DEVICE_TYPE_CLIMATES, [])))
        return self.async_create_entry(title="", data=new_options)

