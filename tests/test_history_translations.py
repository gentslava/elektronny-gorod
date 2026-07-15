"""Translation coverage for durable history EventEntity types."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.elektronny_gorod.const import DOMAIN


_INTEGRATION = (
    Path(__file__).parents[1]
    / "custom_components"
    / DOMAIN
)


@pytest.mark.parametrize(
    "relative_path",
    ["strings.json", "translations/ru.json", "translations/en.json"],
)
def test_history_event_types_have_translations(relative_path: str) -> None:
    """Every declared history event type is present in all locale sources."""
    payload = json.loads((_INTEGRATION / relative_path).read_text())
    event = payload["entity"]["event"]

    assert set(
        event["access_history"]["state_attributes"]["event_type"]["state"]
    ) == {"call_accepted", "call_missed"}
    assert set(
        event["account_history"]["state_attributes"]["event_type"]["state"]
    ) == {"call_accepted", "call_missed"}
    assert set(
        event["camera_history"]["state_attributes"]["event_type"]["state"]
    ) == {"motion"}
