from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    # OptionsFlow,
)
from .const import (
  DOMAIN,
  CONF_ACCESS_TOKEN,
  CONF_REFRESH_TOKEN,
  CONF_PHONE,
  CONF_SMS
)
import voluptuous as vol


class ElektronnyGorodConfigFlow(ConfigFlow, domain=DOMAIN):
    """Elektronny Gorod config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.entry: ConfigEntry | None = None
        self.phone: str | None = None
        self.sms: str | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    async def async_step_user(self, info):
        errors = {}

        if info is not None:
            pass  # TODO: process info

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PHONE): str
            }),
            errors=errors
        )
