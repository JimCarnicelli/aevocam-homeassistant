# pyaevocam

Async Python client for the Aevocam ingest API.

This package is currently **vendored** inside the Home Assistant custom
component so HACS/local installs keep working without a PyPI dependency.

## Intended Core / PyPI layout

Later, move this directory to its own repository and publish it:

```text
pyaevocam/
  pyproject.toml
  README.md
  pyaevocam/
    __init__.py
    client.py
    credentials.py
    exceptions.py
  tests/
```

Then the Home Assistant integration becomes a thin wrapper:

```python
from pyaevocam import AevocamClient

client = AevocamClient(
    async_get_clientsession(hass),
    feed_id=feed_id,
    upload_token=token,
)
await client.async_upload_image(image_bytes, content_type)
```

And `manifest.json` gains:

```json
"requirements": ["pyaevocam==0.1.0"]
```

## Usage

```python
from aiohttp import ClientSession
from pyaevocam import AevocamClient, parse_device_code

credentials = parse_device_code("feed_id/passcode")

async with ClientSession() as session:
    client = AevocamClient(
        session,
        feed_id=credentials.feed_id,
        upload_token=credentials.upload_token,
    )
    await client.async_upload_image(image_bytes, "image/jpeg")
```
