"""Config flow for Aevocam."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CAMERA_ENTITY_ID,
    CONF_DEVICE_CODE,
    CONF_FEED_ID,
    CONF_FEED_NAME,
    CONF_PASSCODE,
    CONF_UPLOAD_TOKEN,
    DOMAIN,
)
from .pyaevocam import (
    AevocamClient,
    AevocamConnectionError,
    AevocamInvalidCredentials,
    AevocamTimeoutError,
    normalize_credentials,
    parse_device_code,
)


async def async_validate_aevocam_credentials(
    hass: HomeAssistant,
    *,
    feed_id: str,
    upload_token: str,
) -> None:
    """Reach Aevocam and verify credentials are accepted."""

    client = AevocamClient(
        async_get_clientsession(hass),
        feed_id=feed_id,
        upload_token=upload_token,
    )
    await client.async_validate_credentials()


def _connection_flow_error(err: Exception) -> str:
    """Map a connection-related library exception to a config flow error key."""

    if isinstance(err, (AevocamConnectionError, AevocamTimeoutError)):
        return "cannot_connect"
    return "unknown"


def build_credentials_schema(
    defaults: dict[str, str] | None = None,
) -> dict[Any, Any]:
    """Build feed ID and passcode schema fields."""

    defaults = defaults or {}

    return {
        vol.Required(
            CONF_FEED_ID,
            default=defaults.get(CONF_FEED_ID, ""),
        ): TextSelector(),
        vol.Required(
            CONF_PASSCODE,
            default=defaults.get(CONF_PASSCODE, ""),
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }


def build_camera_schema(
    defaults: dict[str, str] | None = None,
) -> vol.Schema:
    """Build the camera selection schema."""

    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_CAMERA_ENTITY_ID,
                default=defaults.get(CONF_CAMERA_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="camera")),
        }
    )


def build_feed_name_schema(default_name: str) -> vol.Schema:
    """Build the feed display name schema."""

    return vol.Schema(
        {
            vol.Required(
                CONF_FEED_NAME,
                default=default_name,
            ): TextSelector(),
        }
    )


def suggested_feed_name(hass: HomeAssistant, camera_entity_id: str) -> str:
    """Build a default feed name from the selected camera."""

    state = hass.states.get(camera_entity_id)
    if state is not None and state.name:
        camera_name = state.name
    else:
        camera_name = (
            camera_entity_id.removeprefix("camera.")
            .replace("_", " ")
            .strip()
            .title()
        ) or "Camera"

    return f"Photo from {camera_name} to Aevocam"


def build_reconfigure_camera_fields(entry_data: dict[str, Any]) -> dict[Any, Any]:
    """Build camera and feed name fields for reconfigure steps."""

    return {
        vol.Required(
            CONF_CAMERA_ENTITY_ID,
            default=entry_data.get(CONF_CAMERA_ENTITY_ID),
        ): EntitySelector(EntitySelectorConfig(domain="camera")),
        vol.Required(
            CONF_FEED_NAME,
            default=entry_data.get(CONF_FEED_NAME, ""),
        ): TextSelector(),
    }


def normalize_entry_data(
    *,
    camera_entity_id: str,
    feed_name: str,
    feed_id: str,
    passcode: str,
) -> dict[str, str]:
    """Normalize and validate stored configuration values."""

    credentials = normalize_credentials(feed_id, passcode)

    data = {
        CONF_CAMERA_ENTITY_ID: camera_entity_id.strip(),
        CONF_FEED_NAME: feed_name.strip(),
        CONF_FEED_ID: credentials.feed_id,
        CONF_UPLOAD_TOKEN: credentials.upload_token,
    }

    if not all(data.values()):
        raise ValueError("All fields are required")

    return data


class AevocamConfigFlow(  # pyright: ignore
    config_entries.ConfigFlow,
    domain=DOMAIN,  # pyright: ignore
):
    """Handle an Aevocam config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""

        self._parsed_credentials: dict[str, str] = {}
        self._camera_entity_id: str | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose how to enter Aevocam credentials."""

        return self.async_show_menu(
            step_id="user",
            menu_options=["device_code", "credentials"],
        )

    async def async_step_device_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect a single Aevocam device code."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                credentials = parse_device_code(str(user_input[CONF_DEVICE_CODE]))
            except AevocamInvalidCredentials:
                errors[CONF_DEVICE_CODE] = "invalid_device_code"
            else:
                try:
                    await async_validate_aevocam_credentials(
                        self.hass,
                        feed_id=credentials.feed_id,
                        upload_token=credentials.upload_token,
                    )
                except AevocamInvalidCredentials:
                    errors["base"] = "invalid_credentials"
                except (AevocamConnectionError, AevocamTimeoutError) as err:
                    errors["base"] = _connection_flow_error(err)
                except Exception:  # noqa: BLE001 - surface unexpected failures in the UI
                    errors["base"] = "unknown"
                else:
                    self._parsed_credentials = {
                        CONF_FEED_ID: credentials.feed_id,
                        CONF_UPLOAD_TOKEN: credentials.upload_token,
                    }
                    return await self.async_step_details()

        return self.async_show_form(
            step_id="device_code",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_CODE): TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect separate feed ID and passcode values."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                credentials = normalize_credentials(
                    str(user_input[CONF_FEED_ID]),
                    str(user_input[CONF_PASSCODE]),
                )
            except AevocamInvalidCredentials:
                errors["base"] = "invalid_credentials"
            else:
                try:
                    await async_validate_aevocam_credentials(
                        self.hass,
                        feed_id=credentials.feed_id,
                        upload_token=credentials.upload_token,
                    )
                except AevocamInvalidCredentials:
                    errors["base"] = "invalid_credentials"
                except (AevocamConnectionError, AevocamTimeoutError) as err:
                    errors["base"] = _connection_flow_error(err)
                except Exception:  # noqa: BLE001 - surface unexpected failures in the UI
                    errors["base"] = "unknown"
                else:
                    self._parsed_credentials = {
                        CONF_FEED_ID: credentials.feed_id,
                        CONF_UPLOAD_TOKEN: credentials.upload_token,
                    }
                    return await self.async_step_details()

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(build_credentials_schema()),
            errors=errors,
        )

    async def async_step_details(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select the Home Assistant camera to upload from."""

        errors: dict[str, str] = {}

        if user_input is not None:
            camera_entity_id = str(user_input[CONF_CAMERA_ENTITY_ID]).strip()
            if not camera_entity_id:
                errors["base"] = "invalid_configuration"
            else:
                self._camera_entity_id = camera_entity_id
                return await self.async_step_name()

        return self.async_show_form(
            step_id="details",
            data_schema=build_camera_schema(),
            errors=errors,
        )

    async def async_step_name(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose a display name for the Aevocam feed."""

        errors: dict[str, str] = {}
        camera_entity_id = self._camera_entity_id
        assert camera_entity_id is not None

        if user_input is not None:
            try:
                data = normalize_entry_data(
                    camera_entity_id=camera_entity_id,
                    feed_name=str(user_input[CONF_FEED_NAME]),
                    feed_id=self._parsed_credentials[CONF_FEED_ID],
                    passcode=self._parsed_credentials[CONF_UPLOAD_TOKEN],
                )
            except (AevocamInvalidCredentials, ValueError):
                errors["base"] = "invalid_configuration"
            else:
                return self.async_create_entry(
                    title=data[CONF_FEED_NAME],
                    data=data,
                )

        return self.async_show_form(
            step_id="name",
            data_schema=build_feed_name_schema(
                suggested_feed_name(self.hass, camera_entity_id)
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose how to reconfigure an existing Aevocam entry."""

        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "reconfigure_device_code",
                "reconfigure_credentials",
            ],
        )

    async def async_step_reconfigure_device_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Reconfigure using a device code."""

        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                parsed = parse_device_code(str(user_input[CONF_DEVICE_CODE]))
            except AevocamInvalidCredentials:
                errors[CONF_DEVICE_CODE] = "invalid_device_code"
            else:
                try:
                    await async_validate_aevocam_credentials(
                        self.hass,
                        feed_id=parsed.feed_id,
                        upload_token=parsed.upload_token,
                    )
                    data = normalize_entry_data(
                        camera_entity_id=str(user_input[CONF_CAMERA_ENTITY_ID]),
                        feed_name=str(user_input[CONF_FEED_NAME]),
                        feed_id=parsed.feed_id,
                        passcode=parsed.upload_token,
                    )
                except AevocamInvalidCredentials:
                    errors["base"] = "invalid_credentials"
                except (AevocamConnectionError, AevocamTimeoutError) as err:
                    errors["base"] = _connection_flow_error(err)
                except ValueError:
                    errors["base"] = "invalid_configuration"
                except Exception:  # noqa: BLE001 - surface unexpected failures in the UI
                    errors["base"] = "unknown"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data=data,
                        title=data[CONF_FEED_NAME],
                    )

        feed_id = str(entry.data.get(CONF_FEED_ID, ""))
        passcode = str(entry.data.get(CONF_UPLOAD_TOKEN, ""))
        device_code = f"{feed_id}/{passcode}" if feed_id and passcode else ""

        return self.async_show_form(
            step_id="reconfigure_device_code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_CODE,
                        default=device_code,
                    ): TextSelector(),
                    **build_reconfigure_camera_fields(dict(entry.data)),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Reconfigure using separate feed ID and passcode fields."""

        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data = normalize_entry_data(
                    camera_entity_id=str(user_input[CONF_CAMERA_ENTITY_ID]),
                    feed_name=str(user_input[CONF_FEED_NAME]),
                    feed_id=str(user_input[CONF_FEED_ID]),
                    passcode=str(user_input[CONF_PASSCODE]),
                )
            except AevocamInvalidCredentials:
                errors["base"] = "invalid_credentials"
            except ValueError:
                errors["base"] = "invalid_configuration"
            else:
                try:
                    await async_validate_aevocam_credentials(
                        self.hass,
                        feed_id=data[CONF_FEED_ID],
                        upload_token=data[CONF_UPLOAD_TOKEN],
                    )
                except AevocamInvalidCredentials:
                    errors["base"] = "invalid_credentials"
                except (AevocamConnectionError, AevocamTimeoutError) as err:
                    errors["base"] = _connection_flow_error(err)
                except Exception:  # noqa: BLE001 - surface unexpected failures in the UI
                    errors["base"] = "unknown"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data=data,
                        title=data[CONF_FEED_NAME],
                    )

        return self.async_show_form(
            step_id="reconfigure_credentials",
            data_schema=vol.Schema(
                {
                    **build_credentials_schema(
                        {
                            CONF_FEED_ID: str(entry.data.get(CONF_FEED_ID, "")),
                            CONF_PASSCODE: str(
                                entry.data.get(CONF_UPLOAD_TOKEN, "")
                            ),
                        }
                    ),
                    **build_reconfigure_camera_fields(dict(entry.data)),
                }
            ),
            errors=errors,
        )
