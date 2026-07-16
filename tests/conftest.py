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

# firebase-messaging — manifest-requirement интеграции, но в test-CI manifest-deps
# не устанавливаются (как turbojpeg). Мок на уровне sys.modules — чтобы ленивый
# импорт в fcm.py и `patch("firebase_messaging.*")` в фикстуре ниже работали без
# реальной библиотеки. Если она установлена (local dev) — setdefault no-op.
sys.modules.setdefault("firebase_messaging", MagicMock())


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


@pytest.fixture(autouse=True)
def mock_remove_entry_api() -> Generator[MagicMock, None, None]:
    """async_remove_entry строит реальный ElektronnyGorodAPI для отвязки push-токена.

    В HA-test-харнессе это создаёт реальную aiohttp-сессию → висячий aiodns-поток,
    который `verify_cleanup` ловит на min-HA (тот же класс проблемы, что fix c9ffc94).
    Мокаем API в namespace `__init__` (единственный потребитель — async_remove_entry),
    чтобы удаление entry не делало реальный HTTP. Реальный unregister/DELETE покрыт
    отдельно в test_api_push.py (там — fake session).
    """
    with patch("custom_components.elektronny_gorod.ElektronnyGorodAPI") as mock_cls:
        mock_cls.return_value.unregister_push_device = AsyncMock(return_value=True)
        yield mock_cls


@pytest.fixture(autouse=True)
def mock_go2rtc_clientsession() -> Generator[MagicMock, None, None]:
    """Avoid a real aiohttp resolver thread in integration setup tests.

    ``async_setup_entry`` constructs the per-entry ``Go2RtcClient`` from HA's
    shared session. On the legacy HA 2024.10/PHC test stack, merely creating
    that session can leave aiohttp's ``_run_safe_shutdown_loop`` daemon thread
    alive long enough for the strict ``verify_cleanup`` fixture to fail.

    HTTP behaviour is covered with explicit fake sessions in the focused
    go2rtc client tests; setup/lifecycle tests only need a transport object.
    """
    session = MagicMock()
    with patch(
        "custom_components.elektronny_gorod.async_get_clientsession",
        return_value=session,
    ):
        yield session


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
