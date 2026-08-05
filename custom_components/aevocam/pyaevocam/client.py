"""Async HTTP client for the Aevocam ingest API."""

from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession

from .exceptions import (
    AevocamConnectionError,
    AevocamInvalidCredentials,
    AevocamTimeoutError,
    AevocamUploadError,
)

INGEST_UPLOAD_ENDPOINT = "https://ingest-http.aevocam.com/upload"
DEFAULT_UPLOAD_TIMEOUT_SECONDS = 30

_AUTH_REJECTED_STATUSES = frozenset({401, 403})


def build_upload_url(feed_id: str, *, test_auth: bool = False) -> str:
    """Build the Aevocam HTTPS upload URL for a feed.

    When ``test_auth`` is true, the ingest service ignores the body and
    responds solely based on whether the credentials are valid.
    """

    params: dict[str, str] = {"feed": feed_id}
    if test_auth:
        params["test-auth"] = "true"
    return f"{INGEST_UPLOAD_ENDPOINT}?{urlencode(params)}"


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

    @property
    def feed_id(self) -> str:
        """Return the feed ID this client uploads to."""

        return self._feed_id

    async def async_validate_credentials(self) -> None:
        """Verify credentials via the upload endpoint with ``test-auth=true``.

        Same request shape as ``async_upload_image``; only differences are an
        empty body and the ``test-auth=true`` query parameter.

        * 2xx → credentials accepted
        * 401 / 403 → ``AevocamInvalidCredentials``
        * other / network → connection errors
        """

        try:
            await self.async_upload_image(
                b"",
                "application/octet-stream",
                test_auth=True,
            )
        except AevocamUploadError as err:
            if err.status in _AUTH_REJECTED_STATUSES:
                raise AevocamInvalidCredentials(
                    "Aevocam rejected the feed credentials"
                ) from err
            raise AevocamConnectionError(
                "Unexpected response while validating Aevocam "
                f"credentials (HTTP {err.status}): {err.response_preview}"
            ) from err

    async def async_upload_image(
        self,
        image_bytes: bytes,
        content_type: str,
        *,
        test_auth: bool = False,
    ) -> None:
        """Upload raw image bytes to Aevocam.

        When ``test_auth`` is true, the server ignores the body and responds
        based only on credential validity.

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
                    build_upload_url(self._feed_id, test_auth=test_auth),
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
