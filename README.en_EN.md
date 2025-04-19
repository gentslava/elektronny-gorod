[English](/README.md) | [Русский](/README.ru_RU.md)

<a href="https://2090000.ru/domofony/"><img src="https://domconnect.ru/uploads/2434555b0__domconnect.ru.png" alt="Elektronny Gorod (Novotelecom) logo" height="120"/></a>
&nbsp;&nbsp;&nbsp;
<a href="https://play.google.com/store/apps/details?id=ru.inetra.intercom"><img src="https://play-lh.googleusercontent.com/eCp35NcuGq1V0igXhGrPE6tprf7wGg00dY6TuVvRrqRSiEMTS6yQePuWxEIx3G0EMJ0l=w240-h480-rw" alt="My Home app logo" height="120"/></a>

# Home Assistant Elektronny Gorod Integration

This is a custom integration for Home Assistant that allows you to integrate with the Elektronny Gorod (Novotelecom) service. This implements the API of the My Home - Elektronny Gorod application.

Add your intercoms, cameras and locks to Home Assistant.

## Installation

### Manually

Copy the `custom_components/electronic_city` directory to your Home Assistant `config/custom_components` directory.

```bash
git clone https://github.com/gentslava/elektronny-gorod.git
cp -r elektronny-gorod YOUR_HASS_CONFIG_DIR/custom_components/
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

- View available contracts and add as much as you need.
- Request and enter an SMS code or password for authentication.
- Add available intercoms, cameras and locks.
- Get previews and streams from intercoms and cameras.
- Manage the opening of locks in real time.
- View your account balance.

## Issues and Contributions

If you encounter any issues or have suggestions for improvements, please [open an issue](https://github.com/gentslava/elektronny-gorod/issues) on GitHub.

Feel free to contribute to the project by forking the repository and creating pull requests.

## Credits

Apple device types https://gist.github.com/adamawolf/3048717

## License

This integration is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
