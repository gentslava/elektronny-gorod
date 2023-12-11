# Home Assistant Elektronny Gorod Integration

This is a custom integration for Home Assistant that allows you to integrate with the Elektronny Gorod (Novotelecom) service.

## Installation

Copy the `custom_components/electronic_city` directory to your Home Assistant `config/custom_components` directory.

```bash
git clone https://github.com/gentslava/elektronny-gorod.git
cp -r elektronny-gorod YOUR_HASS_CONFIG_DIR/custom_components/
```

Restart Home Assistant.

## Adding the Integration

1. Go to the Home Assistant UI.
2. Navigate to Configuration -> Integrations.
3. Click the "+" button to add a new integration.
4. Search for "Elektronny Gorod" and select it.
5. Follow the on-screen instructions to complete the integration setup.

## Features

- View available contracts and select one.
- Request and input SMS code for authentication.
- Control Elektronny Gorod devices.

## Issues and Contributions

If you encounter any issues or have suggestions for improvements, please [open an issue](https://github.com/gentslava/elektronny-gorod/issues) on GitHub.

Feel free to contribute to the project by forking the repository and creating pull requests.

## License

This integration is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
