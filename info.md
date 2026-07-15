[![version](https://img.shields.io/github/manifest-json/v/gentslava/elektronny-gorod/master?filename=custom_components%2Felektronny_gorod%2Fmanifest.json&color=slateblue
)](https://github.com/gentslava/elektronny-gorod/releases/latest)
![GitHub all releases](https://img.shields.io/github/downloads/gentslava/elektronny-gorod/total)
![GitHub issues](https://img.shields.io/github/issues/gentslava/elektronny-gorod)
[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg?logo=HomeAssistantCommunityStore&logoColor=white)](https://github.com/hacs/integration)

![Logo](https://brands.home-assistant.io/elektronny_gorod/icon.png)

# Elektronny Gorod & Dom.ru for Home Assistant

Custom integration for the My Home — Elektronny Gorod (Novotelecom) and
Umnyy Dom.ru mobile services.

## Features

- Add multiple available contracts using SMS or password authentication.
- View intercom/private/public camera previews and live streams with optional
  go2rtc audio and lower latency.
- Open intercom doors from Home Assistant.
- Receive real-time doorbell events through FCM for notifications and
  automations.
- Answer and hang up SIP calls, watch and hear the visitor, and talk through a
  browser microphone using the ready-to-use `eg-intercom-call-card`.
- Browse answered and missed call history with date/device filters, pagination,
  and combined timelines for multiple places or accounts.
- Use new accepted/missed-call events in automations. Camera-motion history is
  available through a disabled-by-default entity that polls only when enabled.
- Monitor balance, blocked status and days until blocking.
- Control do-not-disturb settings for intercom and management-company calls.

The upcoming 4.0.0 release adds call answering, two-way audio and event history.
Existing config entries do not need to be recreated, and there are no breaking
changes. See the full [README](README.en_EN.md) and [4.0.0 release
notes](docs/releases/4.0.0.md).

## Configuration
- Use this button:<br>
<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=elektronny_gorod" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up a new integration." /></a>
<br>or:
  - Add the **Elektronny gorod** integration in Settings -> Devices & Services -> Add Integration
  - Select **Elektronny gorod** from the list
  - Confirm form submission
