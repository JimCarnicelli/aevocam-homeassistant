"""Aevocam integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_FEED_ID, CONF_PASSCODE, PLATFORMS
from .pyaevocam import (
    AevocamClient,
    AevocamConnectionError,
    AevocamInvalidCredentials,
    AevocamTimeoutError,
)

type AevocamConfigEntry = ConfigEntry[AevocamClient]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AevocamConfigEntry,
) -> bool:
    """Set up Aevocam from a config entry."""

    client = AevocamClient(
        async_get_clientsession(hass),
        feed_id=entry.data[CONF_FEED_ID],
        passcode=entry.data[CONF_PASSCODE],
    )

    try:
        await client.async_validate_credentials()
    except AevocamInvalidCredentials as err:
        raise ConfigEntryAuthFailed("Invalid Aevocam credentials") from err
    except (AevocamConnectionError, AevocamTimeoutError) as err:
        raise ConfigEntryNotReady("Could not connect to Aevocam") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AevocamConfigEntry,
) -> bool:
    """Unload an Aevocam config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
