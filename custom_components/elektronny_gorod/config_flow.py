import json
import voluptuous as vol

from typing import Any
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    # --- go2rtc ---
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    DEFAULT_GO2RTC_BASE_URL,
    DEFAULT_GO2RTC_RTSP_HOST,
)
from .api import ElektronnyGorodAPI
from .helpers import find, hash_password, hash_password_timestamp
from .user_agent import UserAgent
from .time import Time
from .go2rtc import validate_go2rtc, normalize_base_url


class ElektronnyGorodConfigFlow(ConfigFlow, domain=DOMAIN):
    """Elektronny Gorod config flow."""
    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow state."""
        self.user_agent = UserAgent()
        self.api: ElektronnyGorodAPI = ElektronnyGorodAPI(self.user_agent)
        self.entry: ConfigEntry | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.operator_id: str = "null"
        self.phone: str | None = None
        self.contract: dict[str, Any] | None = None
        self.contracts: list | None = None

        # Prepared entry payload to be created after the final go2rtc decision
        self._entry_data: dict | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect phone or access token and start the authentication flow."""
        errors: dict[str, str] = {}

        if user_input:
            # Advanced mode: user can paste an access token instead of doing SMS/password flow
            if CONF_ACCESS_TOKEN in user_input:
                token = user_input.get(CONF_ACCESS_TOKEN)
                if not isinstance(token, str) or not token.strip():
                    errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
                else:
                    self.access_token = token.strip()
                    LOGGER.debug("Access token is %s", self.access_token)
                    try:
                        return await self.get_account()
                    except ValueError as e:
                        errors[CONF_PHONE] = str(e)

            # Standard mode: phone-based flow
            if CONF_PHONE in user_input:
                phone = user_input.get(CONF_PHONE)
                if not isinstance(phone, str) or not phone.strip():
                    errors[CONF_PHONE] = "invalid_phone"

            if not errors:
                self.phone = phone.strip()
                LOGGER.debug("Phone is %s", self.phone)

                # Fetch contracts for the phone number
                try:
                    res = await self.api.query_contracts(self.phone)

                    # If password is required, go to password step
                    if res.get("password"):
                        return await self.async_step_password()

                    # Otherwise user must choose a contract and confirm via SMS
                    contracts = res.get("contracts")
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
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_password(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for password and complete password-based authentication."""
        errors: dict[str, str] = {}

        # Password authentication
        if user_input:
            password = user_input.get(CONF_PASSWORD)
            if not isinstance(password, str) or not password:
                errors[CONF_PASSWORD] = "invalid_password"
                return self.async_show_form(
                    step_id="password",
                    data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
                    errors=errors,
                )

            phone = self.phone
            if not phone:
                # Should not happen in normal flow, but keep it safe
                return self.async_abort(reason="missing_phone")

            time = Time()
            hash1 = hash_password(password)
            hash2 = hash_password_timestamp(phone, password, time.get_simpletime())

            try:
                auth = await self.api.verify_password(time.get_timestamp(), hash1, hash2)
                self.access_token = auth.get("accessToken")
                self.refresh_token = auth.get("refreshToken")

                operator_id = auth.get("operatorId")
                self.operator_id = str(operator_id) if operator_id is not None else "null"
                self.user_agent.operator_id = self.operator_id

                # If password is verified, proceed to account step
                if self.access_token:
                    return await self.get_account()

                # Authentication failed
                errors[CONF_PASSWORD] = "invalid_password"
            except ValueError as e:
                errors[CONF_PASSWORD] = str(e)

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_contract(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask the user to select a contract and request an SMS code."""
        errors: dict[str, str] = {}

        contracts = self.contracts
        if not contracts:
            return self.async_abort(reason="no_contracts")

        # Build contract choices for the UI
        contract_choices = {
            str(contract["subscriberId"]): f'{contract["address"]} (Account ID: {contract["accountId"]})'
            for contract in contracts
        }

        if user_input is not None:
            # Validate the selected contract id
            selected_id = user_input.get(CONF_CONTRACT)
            if not isinstance(selected_id, str) or not selected_id:
                errors[CONF_CONTRACT] = "invalid_contract"
            else:
                contract = find(
                    contracts,
                    lambda c: str(c["subscriberId"]) == selected_id,
                )

                if contract is None:
                    errors[CONF_CONTRACT] = "invalid_contract"
                else:
                    self.contract = contract
                    LOGGER.debug("Selected contract is %s. Contract object is %s", selected_id, contract)

                    # Request an SMS code for the selected contract
                    try:
                        await self.api.request_sms_code(contract)
                        return await self.async_step_sms()
                    except ValueError as e:
                        errors[CONF_CONTRACT] = str(e)

        return self.async_show_form(
            step_id="contract",
            data_schema=vol.Schema({vol.Required(CONF_CONTRACT): vol.In(contract_choices)}),
            errors=errors,
        )

    async def async_step_sms(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for an SMS code and complete SMS-based authentication."""
        errors: dict[str, str] = {}

        contract = self.contract
        if contract is None:
            return self.async_abort(reason="missing_contract")

        # Verify the SMS code
        if user_input:
            code = user_input.get(CONF_SMS)
            if not isinstance(code, str) or not code:
                errors[CONF_SMS] = "invalid_code"
                return self.async_show_form(
                    step_id="sms",
                    data_schema=vol.Schema({vol.Required(CONF_SMS): str}),
                    errors=errors,
                )

            try:
                auth = await self.api.verify_sms_code(contract, code)
                self.access_token = auth.get("accessToken")
                self.refresh_token = auth.get("refreshToken")

                operator_id = auth.get("operatorId")
                self.operator_id = str(operator_id) if operator_id is not None else "null"
                self.user_agent.operator_id = self.operator_id

                # If the code is verified, proceed to account step
                if self.access_token:
                    return await self.get_account()

                # Authentication failed
                errors[CONF_SMS] = "invalid_code"
            except ValueError as e:
                errors[CONF_SMS] = str(e)

        return self.async_show_form(
            step_id="sms",
            data_schema=vol.Schema({vol.Required(CONF_SMS): str}),
            errors=errors,
        )

    async def get_account(self) -> ConfigFlowResult:
        """Fetch the user profile and finalize entry data (entry is created after go2rtc choice)."""
        token = self.access_token
        if not token:
            return self.async_abort(reason="missing_access_token")

        self.api.http.access_token = token
        profile = await self.api.query_profile()
        subscriber = profile["subscriber"]
        self.user_agent.account_id = subscriber["accountId"]

        data = {
            CONF_NAME: f'{subscriber["name"]} ({subscriber["accountId"]})',
            CONF_ACCOUNT_ID: subscriber["accountId"],
            CONF_SUBSCRIBER_ID: subscriber["id"],
            CONF_ACCESS_TOKEN: self.access_token,
            CONF_REFRESH_TOKEN: self.refresh_token,
            CONF_OPERATOR_ID: self.operator_id,
            CONF_USER_AGENT: json.dumps(self.user_agent.json()),
        }

        # Existing-entry / reauth logic
        for entry in self._async_current_entries():
            if data[CONF_ACCESS_TOKEN] == entry.data.get(CONF_ACCESS_TOKEN):
                LOGGER.info("Entry %s already exists", entry.data)
                return self.async_abort(reason="already_configured")

            if (
                data[CONF_NAME] == entry.data.get(CONF_NAME)
                and data[CONF_ACCOUNT_ID] == entry.data.get(CONF_ACCOUNT_ID)
                and data[CONF_SUBSCRIBER_ID] == entry.data.get(CONF_SUBSCRIBER_ID)
            ):
                LOGGER.info("Reauth entry %s with params %s", entry.data, data)

                prev_use_go2rtc = entry.options.get(CONF_USE_GO2RTC, entry.data.get(CONF_USE_GO2RTC))
                prev_base_url = entry.options.get(CONF_GO2RTC_BASE_URL, entry.data.get(CONF_GO2RTC_BASE_URL))
                prev_rtsp_host = entry.options.get(CONF_GO2RTC_RTSP_HOST, entry.data.get(CONF_GO2RTC_RTSP_HOST))

                merged_data = {
                    **data,
                    CONF_USE_GO2RTC: bool(prev_use_go2rtc) if prev_use_go2rtc is not None else False,
                    CONF_GO2RTC_BASE_URL: prev_base_url if prev_base_url else DEFAULT_GO2RTC_BASE_URL,
                    CONF_GO2RTC_RTSP_HOST: prev_rtsp_host if prev_rtsp_host else DEFAULT_GO2RTC_RTSP_HOST,
                }

                self.hass.config_entries.async_update_entry(
                    entry,
                    data=merged_data,
                    options=entry.options,
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        self._entry_data = data
        return await self.async_step_go2rtc_menu()

    async def async_step_go2rtc_menu(self, user_input=None) -> ConfigFlowResult:
        """Small decision step: configure go2rtc or skip it."""
        return self.async_show_menu(
            step_id="go2rtc_menu",
            menu_options=["go2rtc", "skip_go2rtc"],
        )

    async def async_step_skip_go2rtc(self, user_input=None) -> ConfigFlowResult:
        """Create the entry without go2rtc configuration."""
        if self._entry_data is None:
            return self.async_abort(reason="missing_entry_data")

        data = {**self._entry_data, CONF_USE_GO2RTC: False}
        return self.async_create_entry(title=data[CONF_NAME], data=data)

    async def async_step_go2rtc(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure go2rtc (single form + validation)."""
        if self._entry_data is None:
            return self.async_abort(reason="missing_entry_data")

        errors: dict[str, str] = {}

        if user_input is not None:
            base_url = normalize_base_url(user_input.get(CONF_GO2RTC_BASE_URL))

            if not base_url:
                errors["base"] = "go2rtc_required_fields"
            else:
                session = async_get_clientsession(self.hass)
                result = await validate_go2rtc(base_url, session)
                if not result.ok:
                    errors["base"] = result.error

            if not errors:
                data = {
                    **self._entry_data,
                    CONF_USE_GO2RTC: True,
                    CONF_GO2RTC_BASE_URL: base_url,
                    CONF_GO2RTC_RTSP_HOST: result.rtsp_host,
                }
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        schema = vol.Schema({
            vol.Required(CONF_GO2RTC_BASE_URL, default=DEFAULT_GO2RTC_BASE_URL): str,
        })

        return self.async_show_form(
            step_id="go2rtc",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the options flow handler."""
        return ElektronnyGorodOptionsFlowHandler(config_entry)


class ElektronnyGorodOptionsFlowHandler(OptionsFlow):
    """Options flow for Elektronny Gorod integration (go2rtc settings)."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the options flow state."""
        self.entry = entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Edit go2rtc settings after the integration has been set up."""
        errors: dict[str, str] = {}

        if user_input is not None:
            use_go2rtc = bool(user_input.get(CONF_USE_GO2RTC, False))

            # Normalize strings (even if go2rtc is disabled)
            base_url = normalize_base_url(user_input.get(CONF_GO2RTC_BASE_URL))

            # If go2rtc is enabled, validate the URL
            if use_go2rtc:
                if not base_url:
                    errors["base"] = "go2rtc_required_fields"
                else:
                    session = async_get_clientsession(self.hass)
                    result = await validate_go2rtc(base_url, session)
                    if not result.ok:
                        errors["base"] = result.error

            if not errors:
                data = {
                    CONF_USE_GO2RTC: use_go2rtc,
                    CONF_GO2RTC_BASE_URL: base_url,
                    CONF_GO2RTC_RTSP_HOST: result.rtsp_host,
                }
                return self.async_create_entry(title="", data=data)

        use_go2rtc_default = self.entry.options.get(
            CONF_USE_GO2RTC,
            self.entry.data.get(CONF_USE_GO2RTC, False),
        )
        go2rtc_host_default = self.entry.options.get(
            CONF_GO2RTC_BASE_URL,
            self.entry.data.get(CONF_GO2RTC_BASE_URL, "127.0.0.1"),
        )

        schema = vol.Schema({
            vol.Optional(CONF_USE_GO2RTC, default=bool(use_go2rtc_default)): bool,
            vol.Optional(CONF_GO2RTC_BASE_URL, default=str(go2rtc_host_default)): str,
        })

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
