# Rule: Coordinator pattern

**Применимо к:** `custom_components/elektronny_gorod/coordinator.py`, `camera.py`, `lock.py`, `sensor.py`.

## Правило

Все entity, использующие данные из `ElektronnyGorodUpdateCoordinator`, **должны** наследовать `CoordinatorEntity[ElektronnyGorodUpdateCoordinator]` и получать обновления через `_handle_coordinator_update`, а не через собственный `async_update`.

## Целевая структура

```python
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class ElektronnyGorodBalanceSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CURRENCY_RUBLE

    def __init__(self, coordinator, place_id):
        super().__init__(coordinator)
        self._place_id = place_id
        self._attr_unique_id = f"{DOMAIN}_{place_id}_balance"
        self._attr_device_info = DeviceInfo(...)

    @property
    def native_value(self):
        return self.coordinator.data["balances"].get(self._place_id, {}).get("balance")
```

## Coordinator контракт

```python
class ElektronnyGorodUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, *, entry):
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),  # см. ADR-0003
        )

    async def _async_update_data(self) -> dict:
        # Возвращаем dict — entity берут оттуда свои данные.
        return {
            "places": ...,
            "balances": {place_id: {...}},
            "cameras": {camera_id: {...}},
            "locks": {lock_key: {...}},
        }
```

## Что запрещено

- 🔴 Свой `async_update` в entity (кроме on-demand snapshot/stream).
- 🔴 Прямой вызов `coordinator.update_*_state` из entity (это означает, что coordinator не координатор).
- 🔴 In-memory state в entity, дублирующий coordinator.data.

## Когда исключение допустимо

- Camera snapshot / stream — on-demand, по UI requests. Это **не** периодическое обновление, а action.

## Связь

- [ADR-0002](../../docs/decisions/0002-coordinator-pattern.md)
- [ADR-0003](../../docs/decisions/0003-iot-class-strategy.md)
- audit A-08, A-09, A-44
- Roadmap Итерация 2
