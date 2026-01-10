import json
import voluptuous as vol

from typing import Any
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
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
        """Initialize."""
        self.user_agent = UserAgent()
        self.api: ElektronnyGorodAPI = ElektronnyGorodAPI(self.user_agent)
        self.entry: ConfigEntry | None = None
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.operator_id: str = "null"
        self.phone: str | None = None
        self.contract: dict[str, Any] | None = None
        self.contracts: list | None = None

        self._entry_data: dict | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step to gather the user's input."""
        errors = {}

        if user_input:
            if CONF_ACCESS_TOKEN in user_input:
                self.access_token = user_input[CONF_ACCESS_TOKEN]
                LOGGER.debug(f"Access token is {self.access_token}")
                try:
                    return await self.get_account()
                except ValueError as e:
                    errors[CONF_PHONE] = str(e)

            if CONF_PHONE in user_input:
                self.phone = user_input[CONF_PHONE]
                assert self.phone is not None
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
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )

    async def async_step_password(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step to input password."""
        errors = {}

        # Password auth
        if user_input:
            password = user_input[CONF_PASSWORD]
            time = Time()
            hash1 = hash_password(password)
            phone = self.phone
            if not phone:
                errors[CONF_PASSWORD] = "missing_phone"
                return self.async_show_form(
                    step_id="password",
                    data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
                    errors=errors,
                )

            hash2 = hash_password_timestamp(phone, password, time.get_simpletime())
            try:
                auth = await self.api.verify_password(time.get_timestamp(), hash1, hash2)
                self.access_token = auth["accessToken"]
                self.refresh_token = auth["refreshToken"]
                operator_id = auth["operatorId"]
                self.operator_id = str(operator_id) if operator_id is not None else "null"
                self.user_agent.operator_id = self.operator_id

                # If password is verified, create config entry
                if self.access_token:
                    return await self.get_account()
                # Authentication failed
                errors[CONF_PASSWORD] = "invalid_password"
            except ValueError as e:
                errors[CONF_PASSWORD] = str(e)

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors
        )

    async def async_step_contract(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step to select a contract."""
        errors = {}

        contracts = self.contracts
        if not contracts:
            return self.async_abort(reason="no_contracts")

        # Prepare contract choices for user
        contract_choices = {
            str(contract["subscriberId"]): f'{contract["address"]} (Account ID: {contract["accountId"]})'
            for contract in contracts
        }

        if user_input is not None:
            # Save the selected contract ID
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
                    LOGGER.debug(
                        "Selected contract is %s. Contract object is %s",
                        selected_id,
                        contract,
                    )

                    # Request SMS code for the selected contract
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
        """Step to input SMS code."""
        errors = {}

        contract = self.contract
        if contract is None:
            return self.async_abort(reason="missing_contract")

        # Verify the SMS code
        if user_input:
            code = user_input[CONF_SMS]
            try:
                auth = await self.api.verify_sms_code(contract, code)
                self.access_token = auth["accessToken"]
                self.refresh_token = auth["refreshToken"]
                self.operator_id = auth["operatorId"]
                self.user_agent.operator_id = self.operator_id

                # If code is verified, create config entry
                if self.access_token:
                    return await self.get_account()
                # Authentication failed
                errors[CONF_SMS] = "invalid_code"
            except ValueError as e:
                errors[CONF_SMS] = str(e)

        return self.async_show_form(
            step_id="sms",
            data_schema=vol.Schema({vol.Required(CONF_SMS): str}),
            errors=errors
        )

    async def get_account(self) -> ConfigFlowResult:
        self.api.http.access_token = self.access_token
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

        # existing / reauth logic
        for entry in self._async_current_entries():
            if data[CONF_ACCESS_TOKEN] == entry.data.get(CONF_ACCESS_TOKEN):
                LOGGER.info(f"Entry {entry.data} already exists")
                return self.async_abort(reason="already_configured")

            if (
                data[CONF_NAME] == entry.data.get(CONF_NAME)
                and data[CONF_ACCOUNT_ID] == entry.data.get(CONF_ACCOUNT_ID)
                and data[CONF_SUBSCRIBER_ID] == entry.data.get(CONF_SUBSCRIBER_ID)
            ):
                LOGGER.info(f"Reauth entry {entry.data} with params {data}")
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        self._entry_data = data
        return await self.async_step_go2rtc_menu()

    async def async_step_go2rtc_menu(self, user_input=None) -> ConfigFlowResult:
        """Мини-шаг выбора: настроить go2rtc или пропустить."""
        return self.async_show_menu(
            step_id="go2rtc_menu",
            menu_options=["go2rtc", "skip_go2rtc"],
        )

    async def async_step_skip_go2rtc(self, user_input=None) -> ConfigFlowResult:
        """Создаём entry без go2rtc."""
        assert self._entry_data is not None
        data = {**self._entry_data, CONF_USE_GO2RTC: False}
        return self.async_create_entry(title=data[CONF_NAME], data=data)

    async def async_step_go2rtc(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Настройка go2rtc (форма + валидация)."""
        assert self._entry_data is not None
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
        return ElektronnyGorodOptionsFlowHandler(config_entry)


class ElektronnyGorodOptionsFlowHandler(OptionsFlow):
    """Options flow for Elektronny Gorod integration (go2rtc settings)."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            use_go2rtc = bool(user_input.get(CONF_USE_GO2RTC, False))

            # Нормализуем строки (даже если выключено — ок)
            base_url = (user_input.get(CONF_GO2RTC_BASE_URL) or "").strip().rstrip("/")

            # Если включили go2rtc — поля обязательны и валидируем
            if use_go2rtc:
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
