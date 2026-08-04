"""Aevocam API client library.

This package is structured as a future standalone PyPI dependency. While the
Home Assistant integration is still a custom component, it is vendored here
under ``custom_components/aevocam/pyaevocam/``.

When publishing to Core:

1. Move this package to its own repository.
2. Publish it to PyPI (e.g. ``pyaevocam``).
3. Change integration imports from ``.pyaevocam`` to ``pyaevocam``.
4. Add ``"requirements": ["pyaevocam==X.Y.Z"]`` to ``manifest.json``.
"""

from __future__ import annotations

from .client import AevocamClient, build_upload_url
from .credentials import (
    AevocamCredentials,
    normalize_credentials,
    parse_device_code,
)
from .exceptions import (
    AevocamConnectionError,
    AevocamError,
    AevocamInvalidCredentials,
    AevocamTimeoutError,
    AevocamUploadError,
)

__all__ = [
    "AevocamClient",
    "AevocamConnectionError",
    "AevocamCredentials",
    "AevocamError",
    "AevocamInvalidCredentials",
    "AevocamTimeoutError",
    "AevocamUploadError",
    "build_upload_url",
    "normalize_credentials",
    "parse_device_code",
]

__version__ = "0.1.0"
