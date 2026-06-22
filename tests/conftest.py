"""Common fixtures for the Elektronny Gorod tests."""
import sys
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# pytest-homeassistant-custom-component не тянет optional HA-deps вроде
# `turbojpeg` (используется в homeassistant.components.camera.img_util).
# HA импортирует `camera` лениво при async_forward_entry_setups — это
# происходит после загрузки conftest.py, поэтому sys.modules-mock здесь
# успевает применится до реального импорта.
sys.modules.setdefault("turbojpeg", MagicMock())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Auto-enable loading of custom_components in HA core.

    `enable_custom_integrations` приходит из pytest-homeassistant-custom-component;
    без него HA откажется грузить интеграцию из `custom_components/`.
    """
    yield


@pytest.fixture(autouse=True)
def mock_firebase_messaging() -> Generator[MagicMock, None, None]:
    """Не ходить в Google FCM в тестах — мок firebase-messaging (см. fcm.py).

    FCM-listener стартует фоновой задачей в `async_setup_entry`; без этого мока
    тесты делали бы реальный checkin/register к Google. Клиент мокаем: checkin
    отдаёт тестовый токен, start/stop — no-op.
    """
    client = MagicMock()
    client.checkin_or_register = AsyncMock(return_value="TEST_FCM_TOKEN")
    client.start = AsyncMock()
    client.stop = AsyncMock()
    with patch("firebase_messaging.FcmPushClient", return_value=client), patch(
        "firebase_messaging.FcmRegisterConfig"
    ):
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry for config-flow only tests.

    ⚠️ Путь — `custom_components.elektronny_gorod.*` (не `homeassistant.components.*`),
    т.к. это custom integration. Стандартный HA scaffold-stub был неверным.
    """
    with patch(
        "custom_components.elektronny_gorod.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
