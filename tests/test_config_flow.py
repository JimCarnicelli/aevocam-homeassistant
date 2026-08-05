"""Tests for the Aevocam config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aevocam.config_flow import (
    _connection_flow_error,
    async_validate_aevocam_credentials,
    suggested_feed_name,
)
from custom_components.aevocam.const import (
    CONF_CAMERA_ENTITY_ID,
    CONF_DEVICE_CODE,
    CONF_FEED_ID,
    CONF_FEED_NAME,
    CONF_PASSCODE,
    DOMAIN,
)
from custom_components.aevocam.pyaevocam import (
    AevocamConnectionError,
    AevocamInvalidCredentials,
    AevocamTimeoutError,
)

from .conftest import (
    TEST_CAMERA_ENTITY_ID,
    TEST_DEVICE_CODE,
    TEST_ENTRY_DATA,
    TEST_FEED_ID,
    TEST_FEED_NAME,
    TEST_PASSCODE,
    TEST_UNIQUE_ID,
)


async def _start_user_menu(hass: HomeAssistant) -> dict:
    """Initialize the user config flow and assert the credential menu."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert set(result["menu_options"]) == {"device_code", "credentials"}
    return result


async def _choose_menu_option(hass: HomeAssistant, flow_id: str, option: str) -> dict:
    """Select a menu option and return the next flow result."""

    return await hass.config_entries.flow.async_configure(
        flow_id,
        {"next_step_id": option},
    )


async def _complete_details_and_name(
    hass: HomeAssistant,
    flow_id: str,
    *,
    camera_entity_id: str = TEST_CAMERA_ENTITY_ID,
    feed_name: str = TEST_FEED_NAME,
) -> dict:
    """Finish the details and name steps of a user flow."""

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_CAMERA_ENTITY_ID: camera_entity_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "name"

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_NAME: feed_name},
    )


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_full_flow_device_code(hass: HomeAssistant) -> None:
    """Test a full user flow using a device code."""

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "device_code")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"

    result = await _complete_details_and_name(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FEED_NAME
    assert result["data"] == TEST_ENTRY_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_full_flow_credentials(hass: HomeAssistant) -> None:
    """Test a full user flow using separate feed ID and passcode fields."""

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "credentials")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"

    result = await _complete_details_and_name(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FEED_NAME
    assert result["data"] == TEST_ENTRY_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_device_code_invalid_then_recover(hass: HomeAssistant) -> None:
    """Test invalid device code can be corrected."""

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "device_code")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: "not-a-device-code"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_code"
    assert result["errors"] == {CONF_DEVICE_CODE: "invalid_device_code"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"


async def test_device_code_errors_then_recover(
    hass: HomeAssistant,
    mock_validate_credentials: AsyncMock,
) -> None:
    """Test device-code validation errors can be recovered from."""

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "device_code")

    mock_validate_credentials.side_effect = AevocamInvalidCredentials("bad")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    assert result["errors"] == {"base": "invalid_credentials"}

    mock_validate_credentials.side_effect = AevocamConnectionError("offline")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = AevocamTimeoutError("slow")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    assert result["errors"] == {"base": "unknown"}

    mock_validate_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"
    assert result["errors"] == {}

    result = await _complete_details_and_name(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_credentials_errors_then_recover(
    hass: HomeAssistant,
    mock_validate_credentials: AsyncMock,
) -> None:
    """Test credentials-step validation errors can be recovered from."""

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "credentials")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_ID: "", CONF_PASSCODE: ""},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_credentials"}

    mock_validate_credentials.side_effect = AevocamInvalidCredentials("bad")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_ID: TEST_FEED_ID, CONF_PASSCODE: TEST_PASSCODE},
    )
    assert result["errors"] == {"base": "invalid_credentials"}

    mock_validate_credentials.side_effect = AevocamConnectionError("offline")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_ID: TEST_FEED_ID, CONF_PASSCODE: TEST_PASSCODE},
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = AevocamTimeoutError("slow")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_ID: TEST_FEED_ID, CONF_PASSCODE: TEST_PASSCODE},
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_ID: TEST_FEED_ID, CONF_PASSCODE: TEST_PASSCODE},
    )
    assert result["errors"] == {"base": "unknown"}

    mock_validate_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_ID: TEST_FEED_ID, CONF_PASSCODE: TEST_PASSCODE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"

    result = await _complete_details_and_name(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_details_blank_camera_then_recover(hass: HomeAssistant) -> None:
    """Test blank camera selection can be corrected.

    EntitySelector rejects blank values before the step runs, so exercise the
    defensive empty-camera branch by calling the step directly.
    """

    from custom_components.aevocam.config_flow import AevocamConfigFlow

    flow = AevocamConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_details({CONF_CAMERA_ENTITY_ID: "   "})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"
    assert result["errors"] == {"base": "invalid_configuration"}

    result = await flow.async_step_details(
        {CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "name"


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_name_blank_then_recover(hass: HomeAssistant) -> None:
    """Test a blank feed name can be corrected."""

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "device_code")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID},
    )
    assert result["step_id"] == "name"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_NAME: "   "},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "name"
    assert result["errors"] == {"base": "invalid_configuration"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FEED_NAME: TEST_FEED_NAME},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_duplicate_entry_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test configuring the same feed+camera pair aborts."""

    mock_config_entry.add_to_hass(hass)

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "device_code")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    result = await _complete_details_and_name(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_suggested_feed_name_uses_camera_friendly_name(
    hass: HomeAssistant,
) -> None:
    """Test the feed name suggestion uses the camera friendly name when present."""

    hass.states.async_set(
        TEST_CAMERA_ENTITY_ID,
        "idle",
        {"friendly_name": "Porch Cam"},
    )

    result = await _start_user_menu(hass)
    result = await _choose_menu_option(hass, result["flow_id"], "device_code")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CODE: TEST_DEVICE_CODE},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "name"
    assert suggested_feed_name(hass, TEST_CAMERA_ENTITY_ID) == (
        "Photo from Porch Cam to Aevocam"
    )


def test_suggested_feed_name_without_state(hass: HomeAssistant) -> None:
    """Test the feed name suggestion falls back to the entity id."""

    assert suggested_feed_name(hass, "camera.back_yard") == (
        "Photo from Back Yard to Aevocam"
    )
    assert suggested_feed_name(hass, "camera.") == "Photo from Camera to Aevocam"


def test_connection_flow_error_mapping() -> None:
    """Test connection error helper maps known and unknown exceptions."""

    assert _connection_flow_error(AevocamConnectionError()) == "cannot_connect"
    assert _connection_flow_error(AevocamTimeoutError()) == "cannot_connect"
    assert _connection_flow_error(RuntimeError("boom")) == "unknown"


async def test_async_validate_aevocam_credentials(hass: HomeAssistant) -> None:
    """Test the credential validation helper constructs a client."""

    mock_client = MagicMock()
    mock_client.async_validate_credentials = AsyncMock()

    with (
        patch(
            "custom_components.aevocam.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.aevocam.config_flow.AevocamClient",
            return_value=mock_client,
        ) as mock_client_cls,
    ):
        await async_validate_aevocam_credentials(
            hass,
            feed_id=TEST_FEED_ID,
            passcode=TEST_PASSCODE,
        )

    mock_client_cls.assert_called_once()
    mock_client.async_validate_credentials.assert_awaited_once_with()


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_reconfigure_device_code_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure via device code updates the entry."""

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await _choose_menu_option(
        hass, result["flow_id"], "reconfigure_device_code"
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_device_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: "camera.garage",
            CONF_FEED_NAME: "Garage feed",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_CAMERA_ENTITY_ID: "camera.garage",
        CONF_FEED_NAME: "Garage feed",
        CONF_FEED_ID: TEST_FEED_ID,
        CONF_PASSCODE: TEST_PASSCODE,
    }
    assert mock_config_entry.unique_id == f"{TEST_FEED_ID}_camera.garage"
    assert mock_config_entry.title == "Garage feed"


async def test_reconfigure_device_code_errors_then_recover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
) -> None:
    """Test reconfigure device-code errors can be recovered from."""

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await _choose_menu_option(
        hass, result["flow_id"], "reconfigure_device_code"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: "bad",
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {CONF_DEVICE_CODE: "invalid_device_code"}

    mock_validate_credentials.side_effect = AevocamInvalidCredentials("bad")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "invalid_credentials"}

    mock_validate_credentials.side_effect = AevocamConnectionError("offline")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = AevocamTimeoutError("slow")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: "   ",
        },
    )
    assert result["errors"] == {"base": "invalid_configuration"}

    mock_validate_credentials.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "unknown"}

    mock_validate_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_reconfigure_credentials_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure via credentials updates the entry."""

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await _choose_menu_option(
        hass, result["flow_id"], "reconfigure_credentials"
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_credentials"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: "3.1",
            CONF_PASSCODE: "999888777666",
            CONF_CAMERA_ENTITY_ID: "camera.driveway",
            CONF_FEED_NAME: "Driveway feed",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_CAMERA_ENTITY_ID: "camera.driveway",
        CONF_FEED_NAME: "Driveway feed",
        CONF_FEED_ID: "3.1",
        CONF_PASSCODE: "999888777666",
    }
    assert mock_config_entry.unique_id == "3.1_camera.driveway"


async def test_reconfigure_credentials_errors_then_recover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
) -> None:
    """Test reconfigure credentials errors can be recovered from."""

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await _choose_menu_option(
        hass, result["flow_id"], "reconfigure_credentials"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: "",
            CONF_PASSCODE: "",
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "invalid_credentials"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: "   ",
        },
    )
    assert result["errors"] == {"base": "invalid_configuration"}

    mock_validate_credentials.side_effect = AevocamInvalidCredentials("bad")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "invalid_credentials"}

    mock_validate_credentials.side_effect = AevocamConnectionError("offline")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = AevocamTimeoutError("slow")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_validate_credentials.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["errors"] == {"base": "unknown"}

    mock_validate_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_reconfigure_unique_id_collision(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when another entry already owns the unique id."""

    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        data={
            CONF_CAMERA_ENTITY_ID: "camera.garage",
            CONF_FEED_NAME: "Other",
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: "111222333444",
        },
        unique_id=f"{TEST_FEED_ID}_camera.garage",
    )
    other.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await _choose_menu_option(
        hass, result["flow_id"], "reconfigure_credentials"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FEED_ID: TEST_FEED_ID,
            CONF_PASSCODE: TEST_PASSCODE,
            CONF_CAMERA_ENTITY_ID: "camera.garage",
            CONF_FEED_NAME: "Collision",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_validate_credentials")
async def test_reconfigure_device_code_empty_defaults(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure device-code form with incomplete stored credentials."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Incomplete",
        data={
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
        unique_id="incomplete",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await _choose_menu_option(
        hass, result["flow_id"], "reconfigure_device_code"
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_device_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_CODE: TEST_DEVICE_CODE,
            CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
            CONF_FEED_NAME: TEST_FEED_NAME,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
