"""Credential parsing helpers for Aevocam device codes."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import AevocamInvalidCredentials


@dataclass(frozen=True, slots=True)
class AevocamCredentials:
    """Normalized Aevocam feed credentials."""

    feed_id: str
    upload_token: str


def normalize_passcode(passcode: str) -> tuple[str | None, str]:
    """Normalize a passcode, accepting a full device code paste.

    Returns (feed_id_from_code_or_none, passcode_only).
    """

    passcode = passcode.strip()

    if "/" not in passcode:
        return None, passcode

    feed_id, stripped = passcode.split("/", 1)
    feed_id = feed_id.strip()
    stripped = stripped.strip()

    if not stripped:
        raise AevocamInvalidCredentials("Passcode is missing")

    return (feed_id or None), stripped


def normalize_credentials(feed_id: str, passcode: str) -> AevocamCredentials:
    """Normalize feed ID and passcode into credentials."""

    feed_id = feed_id.strip()
    code_feed_id, passcode = normalize_passcode(passcode)

    if code_feed_id and not feed_id:
        feed_id = code_feed_id

    if not feed_id or not passcode:
        raise AevocamInvalidCredentials("Feed ID and passcode are required")

    if "/" in feed_id:
        raise AevocamInvalidCredentials("Feed ID must not contain '/'")

    return AevocamCredentials(feed_id=feed_id, upload_token=passcode)


def parse_device_code(value: str) -> AevocamCredentials:
    """Parse an Aevocam device code of the form feed_id/passcode."""

    value = value.strip()

    if "/" not in value:
        raise AevocamInvalidCredentials(
            "Device code must look like feed_id/passcode"
        )

    return normalize_credentials("", value)
