"""Exceptions raised by the Aevocam client library."""

from __future__ import annotations


class AevocamError(Exception):
    """Base error for Aevocam client failures."""


class AevocamInvalidCredentials(AevocamError, ValueError):
    """Raised when feed credentials or a device code are invalid."""


class AevocamConnectionError(AevocamError):
    """Raised when the Aevocam service cannot be reached."""


class AevocamUploadError(AevocamError):
    """Raised when Aevocam rejects an upload."""

    def __init__(self, status: int, response_preview: str = "") -> None:
        self.status = status
        self.response_preview = response_preview
        super().__init__(f"Aevocam rejected the snapshot with HTTP status {status}")


class AevocamTimeoutError(AevocamError):
    """Raised when an Aevocam request times out."""
