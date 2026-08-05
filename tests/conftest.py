"""Shared fixtures for Aevocam integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aevocam.const import (
    CONF_CAMERA_ENTITY_ID,
    CONF_FEED_ID,
    CONF_FEED_NAME,
    CONF_UPLOAD_TOKEN,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"

TEST_FEED_ID = "2.6"
TEST_PASSCODE = "283526884921"
TEST_DEVICE_CODE = f"{TEST_FEED_ID}/{TEST_PASSCODE}"
TEST_CAMERA_ENTITY_ID = "camera.front_door"
TEST_FEED_NAME = "Photo from Front Door to Aevocam"
TEST_UNIQUE_ID = f"{TEST_FEED_ID}_{TEST_CAMERA_ENTITY_ID}"

TEST_ENTRY_DATA: dict[str, str] = {
    CONF_CAMERA_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
    CONF_FEED_NAME: TEST_FEED_NAME,
    CONF_FEED_ID: TEST_FEED_ID,
    CONF_UPLOAD_TOKEN: TEST_PASSCODE,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in tests."""


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the integration from setting up during config-flow tests."""

    with patch(
        "custom_components.aevocam.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_validate_credentials() -> Generator[AsyncMock]:
    """Mock Aevocam credential validation used by the config flow."""

    with patch(
        "custom_components.aevocam.config_flow.async_validate_aevocam_credentials",
        new_callable=AsyncMock,
    ) as mock_validate:
        yield mock_validate


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for Aevocam."""

    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_FEED_NAME,
        data=TEST_ENTRY_DATA,
        unique_id=TEST_UNIQUE_ID,
    )


@pytest.fixture
def user_flow_credentials_input() -> dict[str, Any]:
    """Return credentials step user input."""

    return {
        "feed_id": TEST_FEED_ID,
        "passcode": TEST_PASSCODE,
    }
