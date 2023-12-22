import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
)
from homeassistant.const import CONF_NAME
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
        self.api: ElektronnyGorodAPI = ElektronnyGorodAPI()
        self.entry: ConfigEntry | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.operator_id: int = 1
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
            if CONF_PHONE in user_input:
                self.phone = user_input[CONF_PHONE]
                LOGGER.info("Phone is %s", self.phone)

            if CONF_ACCESS_TOKEN in user_input:
                self.access_token = user_input[CONF_ACCESS_TOKEN]
                LOGGER.info("Access token is %s", self.access_token)

            if self.access_token is not None:
                return await self.async_step_sms()

            # Query list of contracts for the given phone number
            contracts = await self.api.query_contracts(self.phone)
            LOGGER.info("Contracts is %s", contracts)

            if not contracts:
                errors[CONF_PHONE] = "no_contracts"
            else:
                self.contracts = contracts
                return await self.async_step_contract()


        if self.show_advanced_options:
            data_schema = vol.Schema({
                vol.Optional(CONF_PHONE): str,
                vol.Optional(CONF_ACCESS_TOKEN): str,
            })
        else:
            data_schema = vol.Schema({
                vol.Required(CONF_PHONE): str,
            })

        return self.async_show_form(
            step_id = "user",
            data_schema = data_schema,
            errors = errors
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
            step_id = "contract",
            data_schema = vol.Schema({vol.Required(CONF_CONTRACT): vol.In(contract_choices)}),
            errors = errors,
        )

    async def async_step_sms(
        self,
        user_input: dict[str] | None = None
    ) -> FlowResult:
        """Step to input SMS code."""
        errors = {}

        if user_input is not None or self.access_token is not None:
            if self.access_token is None:
                code = user_input[CONF_SMS]
                auth = await self.api.verify_sms_code(self.contract, code)
                self.access_token = auth["accessToken"]
                self.refresh_token = auth["refreshToken"]
                self.operator_id = auth["operatorId"]

            # Verify the SMS code
            if self.access_token:
                # If code is verified, create config entry
                name = await self.get_name()
                return self.async_create_entry(
                    title = name,
                    data = {
                        CONF_NAME: name,
                        CONF_ACCESS_TOKEN: self.access_token,
                        CONF_REFRESH_TOKEN: self.refresh_token,
                        CONF_OPERATOR_ID: self.operator_id
                    }
                )

            # Authentication failed
            errors[CONF_SMS] = "invalid_code"

        return self.async_show_form(
            step_id = "sms",
            data_schema = vol.Schema({vol.Required(CONF_SMS): str}),
            errors = errors
        )

    async def get_name(self) -> str:
        await self.api.update_access_token(self.access_token)
        profile = await self.api.query_profile()
        subscriber = profile["subscriber"]
        return f"{subscriber['name']} (Account ID: {subscriber['accountId']})"
