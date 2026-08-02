"""Button platform for Aevocam."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientError, ClientSession

from homeassistant.components.button import ButtonEntity
from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CAMERA_ENTITY_ID,
    CONF_FEED_ID,
    CONF_FEED_NAME,
    CONF_UPLOAD_TOKEN,
    DOMAIN,
    build_upload_url,
)

_LOGGER = logging.getLogger(__name__)

UPLOAD_TIMEOUT_SECONDS = 30


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Aevocam button."""

    async_add_entities([AevocamUploadButton(hass, entry)])


async def async_upload_image(
    session: ClientSession,
    *,
    upload_url: str,
    upload_token: str,
    feed_id: str,
    content_type: str,
    image_bytes: bytes,
) -> None:
    """Upload raw image bytes to Aevocam.

    Isolated so the HTTP contract can be adjusted in one place.
    """

    headers = {
        "Authorization": f"Bearer {upload_token}",
        "Content-Type": content_type,
        "X-Aevocam-Feed-ID": feed_id,
    }

    async with asyncio.timeout(UPLOAD_TIMEOUT_SECONDS):
        async with session.post(
            upload_url,
            data=image_bytes,
            headers=headers,
        ) as response:
            if 200 <= response.status < 300:
                return

            response_preview = (await response.text())[:500]

            _LOGGER.debug(
                "Aevocam upload failure. Status: %s. Response: %s",
                response.status,
                response_preview,
            )

            raise HomeAssistantError(
                "Aevocam rejected the snapshot "
                f"with HTTP status {response.status}"
            )


class AevocamUploadButton(ButtonEntity):
    """Button that uploads a camera snapshot to Aevocam."""

    _attr_has_entity_name = True
    _attr_translation_key = "upload_snapshot"
    _attr_icon = "mdi:camera"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
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
        upload_token = self._entry.data[CONF_UPLOAD_TOKEN]
        upload_url = build_upload_url(feed_id)

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

        session = async_get_clientsession(self.hass)

        try:
            await async_upload_image(
                session,
                upload_url=upload_url,
                upload_token=upload_token,
                feed_id=feed_id,
                content_type=image.content_type,
                image_bytes=image.content,
            )
        except HomeAssistantError:
            raise
        except TimeoutError as err:
            raise HomeAssistantError("The Aevocam upload timed out") from err
        except ClientError as err:
            raise HomeAssistantError("Could not connect to Aevocam") from err

        _LOGGER.info(
            "Uploaded snapshot from %s to Aevocam feed %s",
            camera_entity_id,
            feed_id,
        )
