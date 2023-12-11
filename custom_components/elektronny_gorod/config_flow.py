import logging
import voluptuous as vol
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

_LOGGER = logging.getLogger(__name__)

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

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            phone = user_input[CONF_PHONE]

            _LOGGER.info("Elekrony gorod: Phone is %s", phone)
            pass

        _LOGGER.info("Elekrony gorod: Failed to get phone")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PHONE): str
            }),
            errors=errors
        )
