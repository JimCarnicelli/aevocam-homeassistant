"""Button platform for Aevocam."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.components.camera import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AevocamConfigEntry
from .const import (
    CONF_CAMERA_ENTITY_ID,
    CONF_FEED_ID,
    CONF_FEED_NAME,
    DOMAIN,
)
from .pyaevocam import (
    AevocamConnectionError,
    AevocamTimeoutError,
    AevocamUploadError,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AevocamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Aevocam button."""

    async_add_entities([AevocamUploadButton(hass, entry)])


class AevocamUploadButton(ButtonEntity):
    """Button that uploads a camera snapshot to Aevocam."""

    _attr_has_entity_name = True
    _attr_translation_key = "upload_snapshot"
    _attr_icon = "mdi:camera"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AevocamConfigEntry,
    ) -> None:
        """Initialize the button."""

        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_upload_snapshot"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data[CONF_FEED_NAME],
            "manufacturer": "Aevocam",
            "model": "Snapshot uploader",
        }
        self._upload_lock = asyncio.Lock()

    async def async_press(self) -> None:
        """Capture and upload a camera snapshot."""

        if self._upload_lock.locked():
            raise HomeAssistantError("An Aevocam upload is already in progress")

        async with self._upload_lock:
            await self._async_capture_and_upload()

    async def _async_capture_and_upload(self) -> None:
        """Capture the configured camera and upload it."""

        camera_entity_id = self._entry.data[CONF_CAMERA_ENTITY_ID]
        feed_id = self._entry.data[CONF_FEED_ID]
        client = self._entry.runtime_data

        try:
            image = await async_get_image(self.hass, camera_entity_id)
        except HomeAssistantError as err:
            raise HomeAssistantError(
                f"Could not obtain a snapshot from {camera_entity_id}"
            ) from err
        except Exception as err:
            raise HomeAssistantError(
                f"Could not obtain a snapshot from {camera_entity_id}"
            ) from err

        try:
            await client.async_upload_image(image.content, image.content_type)
        except AevocamUploadError as err:
            _LOGGER.debug(
                "Aevocam upload failure. Status: %s. Response: %s",
                err.status,
                err.response_preview,
            )
            raise HomeAssistantError(str(err)) from err
        except AevocamTimeoutError as err:
            raise HomeAssistantError(str(err)) from err
        except AevocamConnectionError as err:
            raise HomeAssistantError(str(err)) from err

        _LOGGER.info(
            "Uploaded snapshot from %s to Aevocam feed %s",
            camera_entity_id,
            feed_id,
        )
