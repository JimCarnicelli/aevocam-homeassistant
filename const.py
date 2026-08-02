"""Constants for the Aevocam integration."""

from __future__ import annotations

from urllib.parse import urlencode

DOMAIN = "aevocam"

PLATFORMS = ["button"]

CONF_CAMERA_ENTITY_ID = "camera_entity_id"
CONF_DEVICE_CODE = "device_code"
CONF_FEED_ID = "feed_id"
CONF_FEED_NAME = "feed_name"
CONF_PASSCODE = "passcode"
CONF_UPLOAD_TOKEN = "upload_token"

DEFAULT_FEED_NAME = "Aevocam feed"

INGEST_UPLOAD_ENDPOINT = "https://ingest-http.aevocam.com/upload"


def build_upload_url(feed_id: str) -> str:
    """Build the Aevocam HTTPS upload URL for a feed."""

    return f"{INGEST_UPLOAD_ENDPOINT}?{urlencode({'feed': feed_id})}"
