import logging
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
)
from .const import (
  DOMAIN,
  LOGGER,
  CONF_ACCESS_TOKEN,
  CONF_REFRESH_TOKEN,
  CONF_PHONE,
  CONF_CONTRACT,
  CONF_SMS,
  CONF_OPERATOR_ID
)
from .api import ElektronnyGorodAPI
from .helpers import find

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

    async def async_step_user(
        self,
        user_input: dict[str] | None = None
    ) -> FlowResult:
        """Step to gather the user's input."""
        errors = {}

        if user_input is not None:
            self.phone = user_input[CONF_PHONE]
            LOGGER.info("Phone is %s", self.phone)

            self.api = ElektronnyGorodAPI()
            # Query list of contracts for the given phone number
            contracts = await self.api.query_contracts(self.phone)
            LOGGER.info("Contracts is %s", contracts)

            if not contracts:
                errors[CONF_PHONE] = "no_contracts"
            else:
                self.contracts = contracts
                return await self.async_step_contract()

        LOGGER.info("Failed to get phone")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PHONE): str
            }),
            errors=errors
        )

    async def async_step_contract(
        self,
        user_input: dict[str] | None = None
    ) -> FlowResult:
        """Step to select a contract."""
        errors = {}

        # Prepare contract choices for user
        contract_choices = {
            str(contract["subscriberId"]): f"{contract['address']} (Account ID: {contract['accountId']})"
            for contract in self.contracts
        }

        if user_input is not None:
            # Save the selected contract ID
            self.contract = find(
                self.contracts,
                lambda contract: str(contract["subscriberId"]) == user_input[CONF_CONTRACT]
            )
            LOGGER.info("Selected contract is %s. Contract object is %s", user_input[CONF_CONTRACT], self.contract)

            # Request SMS code for the selected contract
            try:
                await self.api.request_sms_code(self.contract)
                return await self.async_step_sms()
            except:
                errors[CONF_CONTRACT] = "limit_exceeded"

        return self.async_show_form(
            step_id="contract",
            data_schema=vol.Schema({vol.Required(CONF_CONTRACT): vol.In(contract_choices)}),
            errors=errors,
        )

    async def async_step_sms(
        self,
        user_input: dict[str] | None = None
    ) -> FlowResult:
        """Step to input SMS code."""
        errors = {}

        if user_input is not None:
            code = user_input[CONF_SMS]

            auth = await self.api.verify_sms_code(self.contract, code)
            # Verify the SMS code
            if auth:
                # If code is verified, create config entry
                return self.async_create_entry(
                    title=f"Electronic City ({self.contract})",
                    data={
                        CONF_ACCESS_TOKEN: auth["accessToken"],
                        CONF_REFRESH_TOKEN: auth["refreshToken"],
                        CONF_OPERATOR_ID: auth["operatorId"]
                    }
                )

            # SMS code verification failed
            errors[CONF_SMS] = "invalid_code"

        return self.async_show_form(
            step_id="sms",
            data_schema=vol.Schema({vol.Required(CONF_SMS): str}),
            errors=errors
        )

