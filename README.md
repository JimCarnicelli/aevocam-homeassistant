# Aevocam Home Assistant Integration

Custom [Home Assistant](https://www.home-assistant.io/) integration that uploads camera snapshots to [Aevocam](https://www.aevocam.com).

## Installation

### HACS (recommended)

1. Open HACS → Integrations.
2. Add this repository as a custom repository (category: Integration), or install it once it is listed in HACS.
3. Install **Aevocam**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for **Aevocam**.

### Manual

1. Copy `custom_components/aevocam/` from this repository into your Home Assistant `config/custom_components/aevocam/` directory.
2. Restart Home Assistant.
3. Add the **Aevocam** integration from the UI.

## Configuration

During setup you will be asked for:

- An Aevocam feed ID and passcode (or a combined device code)
- The Home Assistant camera entity to snapshot

Press the upload button entity to capture a frame from that camera and send it to your Aevocam feed.

## Support

- Documentation: https://www.aevocam.com
- Issues: https://github.com/JimCarnicelli/aevocam-homeassistant/issues
