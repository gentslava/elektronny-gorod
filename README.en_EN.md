[English](/README.en_EN.md) | [Русский](/README.md)

<p>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5" alt="HACS Custom"/></a>
  <img src="https://img.shields.io/github/v/release/gentslava/elektronny-gorod?label=release&color=blue" alt="Release"/>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.10%2B-blue?logo=home-assistant" alt="Home Assistant"/>
  <img src="https://img.shields.io/github/license/gentslava/elektronny-gorod?color=green" alt="License"/>
  <img src="https://img.shields.io/badge/Custom%20Integration-orange" alt="Custom Integration"/>
  <img src="https://img.shields.io/badge/Elektronny%20Gorod-API-green" alt="Elektronny Gorod API"/>
  <img src="https://img.shields.io/badge/Dom.ru-API-red" alt="Dom.ru API"/>
  <img src="https://img.shields.io/badge/Intercoms,%20Cameras,%20Locks,%20Doorbell-lightgrey" alt="Devices"/>
  <img src="https://img.shields.io/badge/English-yes-blue" alt="English language"/>
  <a href="https://boosty.to/gentslava"><img src="https://img.shields.io/badge/Boosty-Support-FF6F31" alt="Support on Boosty"/></a>
</p>

# Home Assistant Elektronny Gorod & Dom.ru Integration

<table>
  <tr>
    <td align="center">
      <a href="https://2090000.ru/domofony/"><img src="https://domconnect.ru/uploads/2434555b0__domconnect.ru.png" alt="Elektronny Gorod (Novotelecom) logo" height="120"/></a>
    </td>
    <td align="center">
      <a href="https://play.google.com/store/apps/details?id=ru.inetra.intercom"><img src="https://play-lh.googleusercontent.com/eCp35NcuGq1V0igXhGrPE6tprf7wGg00dY6TuVvRrqRSiEMTS6yQePuWxEIx3G0EMJ0l=w240-h480-rw" alt="My Home app logo" height="120"/></a>
    </td>
  </tr>
  <tr>
    <td align="center">
      <a href="https://dom.ru/domofon"><img src="https://internet-domru.ru/assets/images/logo.png" alt="Dom.ru logo" height="120"/></a>
    </td>
    <td align="center">
      <a href="https://play.google.com/store/apps/details?id=com.ertelecom.smarthome"><img src="https://play-lh.googleusercontent.com/dN4M3FlqpX9a_HacE8jx4QQpnYH8u869U6_SaTaCSY-oZFeI17Zw4ZNlpWxRbe4DxSM=w240-h480-rw" alt="Umnyy Dom.ru app logo" height="120"/></a>
    </td>
  </tr>
</table>

This is a custom integration for Home Assistant that allows you to integrate with the Elektronny Gorod (Novotelecom) and Dom.ru services. It implements the APIs of the My Home – Elektronny Gorod and Umnyy Dom.ru applications.

Add your **intercoms, cameras and locks** to Home Assistant: watch video and hear audio, open doors and — **in real time** — receive **doorbell call events** (FCM push) for notifications and automations.

> 🔔 **New:** the integration now catches **doorbell calls** and exposes them as an `event` entity — send a push with a camera snapshot and an "Open door" button. See [Doorbell call event](#-doorbell-call-event-fcm-push).

## Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Features](#features)
- [Camera connection via go2rtc](#camera-connection-via-go2rtc)
- [🔔 Doorbell call event (FCM push)](#-doorbell-call-event-fcm-push)
- [Automation example: balance](#automation-example-balance)
- [Issues and Contributions](#issues-and-contributions)
- [License](#license)

## Installation

### Manually

Copy the `custom_components/elektronny_gorod` directory to your Home Assistant `config/custom_components` directory.

```bash
git clone https://github.com/gentslava/elektronny-gorod.git
cp -r elektronny-gorod/custom_components/elektronny_gorod YOUR_HASS_CONFIG_DIR/custom_components/
```

Restart Home Assistant.


### Via [HACS](https://hacs.xyz/)
<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=gentslava&repository=elektronny-gorod&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

## Configuration
<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=elektronny_gorod" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up a new integration." /></a>

or manually:

1. Go to the Home Assistant UI.
2. Navigate to Configuration -> Integrations.
3. Click the "+" button to add a new integration.
4. Search for "Elektronny Gorod" and select it.
5. Follow the on-screen instructions to complete the integration setup.

## Features

- Integration with Elektronny Gorod and Dom.ru services (works with My Home and Umnyy Dom.ru apps).
- View available contracts and add as much as you need.
- Request and enter an SMS code or password for authentication.
- Add available intercoms, cameras and locks.
- Get previews and streams from intercoms and cameras.
- Manage the opening of locks in real time.
- **Real-time doorbell call events** (FCM push) — an `event` entity for notifications and automations (show the camera, open the door).
- View your account balance.

Entity types created: `camera` (video/preview), `lock` (open the door), `event` (doorbell call), `sensor` (balance and more), `binary_sensor`, `switch`.

> **New:** Now you can connect cameras via [go2rtc](https://github.com/AlexxIT/go2rtc) — this method allows you to get audio from cameras and provides faster and more stable video streaming.

## Camera connection via go2rtc

Integration with [go2rtc](https://github.com/AlexxIT/go2rtc) is supported for Elektronny Gorod and Dom.ru cameras. This method allows you to:
- Get audio stream from cameras.
- Get faster and more stable video stream (low latency, fewer disconnects).

### How to connect

1. Install and configure [go2rtc](https://github.com/AlexxIT/go2rtc) in Home Assistant (via HACS or manually).
2. In the Elektronny Gorod/Dom.ru integration settings, select the stream method via go2rtc (or specify the go2rtc link in the camera settings).
3. After that, cameras will automatically appear in Home Assistant with audio support and improved video.

#### Using with already configured integrations

If you already have cameras set up via the standard integration, just enable go2rtc support in the integration or camera settings — you do not need to re-add devices.

**Note:** For audio and low latency to work, make sure your go2rtc and Home Assistant versions are up to date.

## 🔔 Doorbell call event (FCM push)

The integration receives **doorbell calls in real time** via FCM push — exactly like the mobile app, without cloud polling. For every intercom an `event` entity with device class `doorbell` is created:

- **`event.<intercom>_doorbell_call`** — fires `ring` on an incoming call and `ended` when the call finishes (answered on another device or the answer window timed out).
- Event attributes: `event_type` (`ring`/`ended`), `gate_name` (intercom), `apartment`, `call_id`, `allow_open`, `reason`.

Build automations on top of it: a push with a camera snapshot and an "Open door" button, show the video, unlock the door.

> The channel is private FCM reception (the `firebase-messaging` dependency is installed automatically). The whole FCM flow runs under graceful degradation: if it fails, the rest of the integration (cameras, locks, balance) keeps working.
>
> In the examples, replace `YOUR_INTERCOM` / `YOUR_PHONE` with your own entities (Developer Tools → States, filters `event.` / `notify.mobile_app`). The snapshot and action buttons require the **Home Assistant Companion** app (Android/iOS).

### Example 1. Push on call

```yaml
automation:
  - alias: "Doorbell: call notification"
    mode: parallel
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "🔔 Doorbell call"
          message: "{{ trigger.to_state.attributes.gate_name }} · apt. {{ trigger.to_state.attributes.apartment }}"
```

### Example 2. Push with a camera snapshot and an "Open door" button

```yaml
automation:
  # 1) Notification with a camera preview and an action button
  - alias: "Doorbell: push with camera and open"
    mode: parallel
    triggers:
      - trigger: state
        entity_id: event.YOUR_INTERCOM_doorbell_call
    conditions:
      - "{{ trigger.to_state.attributes.event_type == 'ring' }}"
    actions:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "🔔 Doorbell call"
          message: "{{ trigger.to_state.attributes.gate_name }}"
          data:
            image: "/api/camera_proxy/camera.YOUR_INTERCOM"
            tag: "doorbell"
            actions:
              - action: "OPEN_DOOR"
                title: "🔓 Open door"

  # 2) Button handler: unlock the intercom door
  - alias: "Doorbell: open door from push button"
    triggers:
      - trigger: event
        event_type: mobile_app_notification_action
        event_data:
          action: "OPEN_DOOR"
    actions:
      - action: lock.unlock
        target:
          entity_id: lock.YOUR_INTERCOM
```

## Automation example: balance
Here is an example of automation for low balance notification:

```yaml
automation:
  - alias: "Low balance notification"
    trigger:
      - platform: numeric_state
        entity_id: sensor.elektronny_gorod_balance
        below: 100
    action:
      - service: notify.notify
        data:
          message: "Your account balance in Elektronny Gorod is below 100 rubles."
```

## Issues and Contributions

If you encounter any issues or have suggestions for improvements, please [open an issue](https://github.com/gentslava/elektronny-gorod/issues) on GitHub.

Feel free to contribute to the project by forking the repository and creating pull requests.

## Credits

❤️ **Thank you to all the donors** who supported the integration with a donation — your support motivates further development.

Support development: [![Boosty](https://img.shields.io/badge/Boosty-Support%20the%20project-FF6F31)](https://boosty.to/gentslava)

Apple device types https://gist.github.com/adamawolf/3048717

[go2rtc](https://github.com/AlexxIT/go2rtc) — project for streaming video and audio

## License

This integration is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
