from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import ElektronnyGorodUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elektronny Gorod Balance Sensor based on a config entry."""
    coordinator: ElektronnyGorodUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get balances info
    balances_info = await coordinator.get_balances_info()

    # Create balance sensor entities
    async_add_entities(
        ElektronnyGorodBalanceSensor(coordinator, balance_info)
        for balance_info in balances_info
    )


class ElektronnyGorodBalanceSensor(SensorEntity):
    """Representation of a balance sensor."""

    def __init__(
        self, coordinator: ElektronnyGorodUpdateCoordinator, balance_info: dict
    ) -> None:
        """Initialize the balance sensor."""
        LOGGER.debug(f"ElektronnyGorodBalanceSensor init {balance_info}")
        super().__init__()
        self._coordinator = coordinator
        self._balance = balance_info["balance"]
        self._place_id = balance_info["place_id"]
        self._attr_name = f"Баланс аккаунта"
        self._attr_icon = "mdi:cash-multiple"
        self._attr_unique_id = f"{DOMAIN}_{self._place_id}_balance"

    @property
    def native_value(self) -> float:
        """Return state of the sensor."""
        if self._balance is not None:
            return round(self._balance, 2)
        return self._balance

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement the value is expressed in."""
        if self._balance is None:
            return None
        return "₽"

    async def async_update(self) -> None:
        """Fetch the latest balance from the API."""
        try:
            LOGGER.info("Fetching balance from Elektronny Gorod API")
            balance_info = await self._coordinator.update_balance_state(self._place_id)
            self._balance = balance_info["balance"]
        except Exception as e:
            LOGGER.error(f"Failed to fetch balance: {e}")
            self._balance = None
