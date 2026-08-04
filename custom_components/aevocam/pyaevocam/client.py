"""Async HTTP client for the Aevocam ingest API."""

from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession

from .exceptions import (
    AevocamConnectionError,
    AevocamTimeoutError,
    AevocamUploadError,
)

INGEST_UPLOAD_ENDPOINT = "https://ingest-http.aevocam.com/upload"
DEFAULT_UPLOAD_TIMEOUT_SECONDS = 30


def build_upload_url(feed_id: str) -> str:
    """Build the Aevocam HTTPS upload URL for a feed."""

    return f"{INGEST_UPLOAD_ENDPOINT}?{urlencode({'feed': feed_id})}"


class AevocamClient:
    """Thin client around the Aevocam upload API.

    Accepts an injected ``aiohttp.ClientSession`` so Home Assistant can pass
    its shared session via ``async_get_clientsession(hass)``.
    """

    def __init__(
        self,
        session: ClientSession,
        *,
        feed_id: str,
        upload_token: str,
        upload_timeout: float = DEFAULT_UPLOAD_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the client."""

        self._session = session
        self._feed_id = feed_id
        self._upload_token = upload_token
        self._upload_timeout = upload_timeout
        self._upload_url = build_upload_url(feed_id)

    @property
    def feed_id(self) -> str:
        """Return the feed ID this client uploads to."""

        return self._feed_id

    async def async_upload_image(
        self,
        image_bytes: bytes,
        content_type: str,
    ) -> None:
        """Upload raw image bytes to Aevocam.

        Raises:
            AevocamTimeoutError: Request timed out.
            AevocamConnectionError: Network failure.
            AevocamUploadError: Non-success HTTP response from Aevocam.
        """

        headers = {
            "Authorization": f"Bearer {self._upload_token}",
            "Content-Type": content_type,
            "X-Aevocam-Feed-ID": self._feed_id,
        }

        try:
            async with asyncio.timeout(self._upload_timeout):
                async with self._session.post(
                    self._upload_url,
                    data=image_bytes,
                    headers=headers,
                ) as response:
                    if 200 <= response.status < 300:
                        return

                    response_preview = (await response.text())[:500]
                    raise AevocamUploadError(response.status, response_preview)
        except TimeoutError as err:
            raise AevocamTimeoutError("The Aevocam upload timed out") from err
        except ClientError as err:
            raise AevocamConnectionError("Could not connect to Aevocam") from err
