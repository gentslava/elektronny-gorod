import json
from datetime import datetime
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
    CONF_PASSWORD,
    CONF_CONTRACT,
    CONF_SMS,
    CONF_OPERATOR_ID,
    CONF_ACCOUNT_ID,
    CONF_SUBSCRIBER_ID,
    CONF_USER_AGENT,
)
from .api import ElektronnyGorodAPI
from .helpers import (
    find,
    hash_password,
    hash_password_timestamp,
)
from .user_agent import UserAgent
from .time import Time

class ElektronnyGorodConfigFlow(ConfigFlow, domain=DOMAIN):
    """Elektronny Gorod config flow."""
    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self.user_agent = UserAgent()
        self.api: ElektronnyGorodAPI = ElektronnyGorodAPI(self.user_agent)
        self.entry: ConfigEntry | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.operator_id: str | int = "null"
        self.phone: str | None = None
        self.contract: object | None = None
        self.contracts: list | None = None

    async def async_step_user(
        self,
        user_input: dict[str] | None = None
    ) -> FlowResult:
        """Step to gather the user's input."""
        errors = {}

        if user_input:
            if CONF_ACCESS_TOKEN in user_input:
                self.access_token = user_input[CONF_ACCESS_TOKEN]
                LOGGER.debug(f"Access token is {self.access_token}")
                return await self.get_account()

            if CONF_PHONE in user_input:
                self.phone = user_input[CONF_PHONE]
                LOGGER.debug(f"Phone is {self.phone}")

                # Query list of contracts for the given phone number
                try:
                    res = await self.api.query_contracts(self.phone)
                    # Password required
                    if res["password"]:
                        return await self.async_step_password()

                    # Choose contract
                    contracts = res["contracts"]
                    if not contracts:
                        errors[CONF_PHONE] = "no_contracts"
                    else:
                        self.contracts = contracts
                        return await self.async_step_contract()
                except ValueError as e:
                    errors[CONF_PHONE] = str(e)

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

    async def async_step_password(
        self,
        user_input: dict[str] | None = None
    ) -> FlowResult:
        """Step to input password."""
        errors = {}

        # Password auth
        if user_input:
            password = user_input[CONF_PASSWORD]
            time = Time()
            hash1 = hash_password(password)
            hash2 = hash_password_timestamp(self.phone, password, time.get_simpletime())
            try:
                auth = await self.api.verify_password(time.get_timestamp(), hash1, hash2)
                self.access_token = auth["accessToken"]
                self.refresh_token = auth["refreshToken"]
                self.operator_id = auth["operatorId"]
                self.user_agent.operator_id = self.operator_id

                # If password is verified, create config entry
                if self.access_token:
                    return await self.get_account()

                # Authentication failed
                else:
                    errors[CONF_PASSWORD] = "invalid_password"
            except ValueError as e:
                errors[CONF_PASSWORD] = str(e)

        return self.async_show_form(
            step_id = "password",
            data_schema = vol.Schema({vol.Required(CONF_PASSWORD): str}),
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
            str(contract["subscriberId"]): f"{contract["address"]} (Account ID: {contract["accountId"]})"
            for contract in self.contracts
        }

        if user_input is not None:
            # Save the selected contract ID
            self.contract = find(
                self.contracts,
                lambda contract: str(contract["subscriberId"]) == user_input[CONF_CONTRACT]
            )
            LOGGER.debug(f"Selected contract is {user_input[CONF_CONTRACT]}. Contract object is {self.contract}")

            # Request SMS code for the selected contract
            try:
                await self.api.request_sms_code(self.contract)
                return await self.async_step_sms()
            except ValueError as e:
                errors[CONF_CONTRACT] = str(e)

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

        # Verify the SMS code
        if user_input:
            code = user_input[CONF_SMS]
            try:
                auth = await self.api.verify_sms_code(self.contract, code)
                self.access_token = auth["accessToken"]
                self.refresh_token = auth["refreshToken"]
                self.operator_id = auth["operatorId"]
                self.user_agent.operator_id = self.operator_id

                # If code is verified, create config entry
                if self.access_token:
                    return await self.get_account()

                # Authentication failed
                else:
                    errors[CONF_SMS] = "invalid_code"
            except ValueError as e:
                errors[CONF_SMS] = str(e)

        return self.async_show_form(
            step_id = "sms",
            data_schema = vol.Schema({vol.Required(CONF_SMS): str}),
            errors = errors
        )

    async def get_account(self) -> dict:
        self.api.http.access_token = self.access_token
        profile = await self.api.query_profile()
        subscriber = profile["subscriber"]
        self.user_agent.account_id = subscriber["accountId"]

        data = {
            CONF_NAME: f"{subscriber["name"]} ({subscriber["accountId"]})",
            CONF_ACCOUNT_ID: subscriber["accountId"],
            CONF_SUBSCRIBER_ID: subscriber["id"],
            CONF_ACCESS_TOKEN: self.access_token,
            CONF_REFRESH_TOKEN: self.refresh_token,
            CONF_OPERATOR_ID: self.operator_id,
            CONF_USER_AGENT: json.dumps(self.user_agent.json()),
        }

        for entry in self._async_current_entries():
            if (data[CONF_ACCESS_TOKEN] == entry.data[CONF_ACCESS_TOKEN]):
                LOGGER.info(f"Entry {entry.data} already exists")
                return self.async_abort(reason = "already_configured")
            if (
                data[CONF_NAME] == entry.data[CONF_NAME]
                and data[CONF_ACCOUNT_ID] == entry.data[CONF_ACCOUNT_ID]
                and data[CONF_SUBSCRIBER_ID] == entry.data[CONF_SUBSCRIBER_ID]
            ):
                LOGGER.info(f"Reauth entry {entry.data} with params {data}")
                self.hass.config_entries.async_update_entry(entry, data = data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason = "reauth_successful")

        return self.async_create_entry(title = data[CONF_NAME], data = data)
