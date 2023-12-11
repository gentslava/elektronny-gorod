import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant
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
  CONF_CONTRACT,
  CONF_SMS
)
from .api import ElektronnyGorodAPI
from .helpers import find

_LOGGER = logging.getLogger(__name__)

class ElektronnyGorodConfigFlow(ConfigFlow, domain=DOMAIN):
    """Elektronny Gorod config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.api: object | None = None
        self.entry: ConfigEntry | None = None
        self.phone: str | None = None
        self.contract: object | None = None
        self.contracts: list | None = None
        self.sms: str | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    async def async_step_user(self, user_input=None):
        """Step to gather the user's input."""
        errors = {}

        if user_input is not None:
            self.phone = user_input[CONF_PHONE]
            _LOGGER.info("Phone is %s", self.phone)

            self.api = ElektronnyGorodAPI(base_url="https://myhome.novotelecom.ru", hass=self.hass)
            # Query list of contracts for the given phone number
            contracts = await self.api.query_contracts(self.phone)
            _LOGGER.info("Contracts is %s", contracts)

            if not contracts:
                errors[CONF_PHONE] = "no_contracts"
            else:
                self.contracts = contracts
                # Prepare contract choices for user
                contract_choices = {
                    str(contract["subscriberId"]): f"{contract['address']} (Account ID: {contract['accountId']})"
                    for contract in contracts
                }

                return self.async_show_form(
                    step_id="contract",
                    data_schema=vol.Schema({vol.Required(CONF_CONTRACT): vol.In(contract_choices)}),
                    errors=errors,
                )

        _LOGGER.info("Failed to get phone")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PHONE): str
            }),
            errors=errors
        )

    async def async_step_contract(self, user_input):
        """Step to select a contract."""
        if user_input is not None:
            # Save the selected contract ID
            self.contract = find(
                self.contracts,
                lambda contract: contract["subscriberId"] == user_input[CONF_CONTRACT]
            )
            _LOGGER.info("Selected contract is %s", self.contract)

            # Request SMS code for the selected contract
            await self.api.request_sms_code(self.contract)

            return self.async_show_form(
                step_id="sms",
                data_schema=vol.Schema({vol.Required(CONF_SMS): str}),
            )

        return self.async_abort(reason="unknown")

    async def async_step_sms(self, user_input):
        """Step to input SMS code."""
        if user_input is not None:
            code = user_input[CONF_SMS]

            # Verify the SMS code
            if await self.api.verify_sms_code(code):
                # If code is verified, create config entry
                return self.async_create_entry(title=f"Electronic City ({self.contract})", data={CONF_CONTRACT: self.contract})

            # SMS code verification failed
            return self.async_show_form(
                step_id="sms",
                data_schema=vol.Schema({vol.Required(CONF_SMS): str}),
                errors={CONF_SMS: "invalid_code"},
            )

        return self.async_abort(reason="unknown")

