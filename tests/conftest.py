"""Common fixtures for the Elektronny Gorod tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Auto-enable loading of custom_components in HA core.

    `enable_custom_integrations` приходит из pytest-homeassistant-custom-component;
    без него HA откажется грузить интеграцию из `custom_components/`.
    """
    yield


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
