"""Tests for entity_migration._camera_new_uid / _lock_new_uid (A-12, slice 3c).

Чистые unit-тесты — без HA. Интеграционная проверка `er.async_migrate_entries`
(прокладка вокруг этих функций) пойдёт отдельным slice вместе с config-flow
тестами (см. testing/strategy.md).
"""
from __future__ import annotations

import pytest

from custom_components.elektronny_gorod.const import DOMAIN
from custom_components.elektronny_gorod.entity_migration import (
    _camera_new_uid,
    _lock_new_uid,
    lock_unique_id,
)


# ---------------------------------------------------------------------------- #
# camera                                                                       #
# ---------------------------------------------------------------------------- #


CAMERAS = [
    {"id": "111", "name": "Подъезд 1"},
    {"id": "222", "name": None},  # name=None в API → __init__ подставлял id
    {"id": "333", "name": "Двор"},
]


def test_camera_legacy_with_name_migrates_to_stable():
    """Старый формат `{id}_{name}` → `{DOMAIN}_camera_{id}`."""
    assert _camera_new_uid("111_Подъезд 1", CAMERAS) == f"{DOMAIN}_camera_111"
    assert _camera_new_uid("333_Двор", CAMERAS) == f"{DOMAIN}_camera_333"


def test_camera_legacy_with_null_name_migrates():
    """`name=None` → legacy UID был `f"{id}_{id}"` (fallback в old __init__)."""
    assert _camera_new_uid("222_222", CAMERAS) == f"{DOMAIN}_camera_222"


def test_camera_already_new_format_skipped():
    """UID уже в новом формате — миграция не нужна."""
    assert _camera_new_uid(f"{DOMAIN}_camera_111", CAMERAS) is None


def test_camera_unknown_uid_returns_none():
    """UID, который не соответствует ни одной известной camera — оставляем как есть."""
    assert _camera_new_uid("999_phantom", CAMERAS) is None
    assert _camera_new_uid("garbage", CAMERAS) is None


def test_camera_empty_coordinator_data():
    """Coordinator не успел собрать camera — миграции не делаем."""
    assert _camera_new_uid("111_Подъезд 1", []) is None


def test_camera_skips_entries_without_id():
    """Запись без `id` — игнор, не падаем."""
    cameras = [{"id": None, "name": "broken"}, {"id": "111", "name": "ok"}]
    assert _camera_new_uid("111_ok", cameras) == f"{DOMAIN}_camera_111"


# ---------------------------------------------------------------------------- #
# lock                                                                         #
# ---------------------------------------------------------------------------- #


LOCKS = [
    {
        "place_id": "P1",
        "access_control_id": "AC1",
        "entrance_id": "E1",
        "name": "Подъезд 1",
        "openable": True,
    },
    {
        "place_id": "P2",
        "access_control_id": "AC2",
        "entrance_id": None,  # AC без entrances
        "name": "Калитка",
        "openable": True,
    },
]


def test_lock_legacy_with_entrance_migrates():
    """Старый формат `{p}_{ac}_{eid}_{name}` → новый stable."""
    new = _lock_new_uid("P1_AC1_E1_Подъезд 1", LOCKS)
    assert new == lock_unique_id("P1", "AC1", "E1")
    assert new == f"{DOMAIN}_lock_P1_AC1_E1"


def test_lock_legacy_with_none_entrance_migrates():
    """entrance_id=None — в legacy UID отображался как строка `None`.

    После миграции в новом UID `entrance_id` заменяется на `'main'`.
    """
    new = _lock_new_uid("P2_AC2_None_Калитка", LOCKS)
    assert new == lock_unique_id("P2", "AC2", None)
    assert new == f"{DOMAIN}_lock_P2_AC2_main"


def test_lock_already_new_format_skipped():
    assert _lock_new_uid(f"{DOMAIN}_lock_P1_AC1_E1", LOCKS) is None


def test_lock_unknown_uid_returns_none():
    assert _lock_new_uid("P9_AC9_E9_phantom", LOCKS) is None
    assert _lock_new_uid("garbage", LOCKS) is None


def test_lock_skips_entries_with_missing_ids():
    """Lock без place_id или ac_id — игнор."""
    locks = [
        {"place_id": None, "access_control_id": "AC1", "entrance_id": "E1", "name": "broken"},
        {"place_id": "P1", "access_control_id": None, "entrance_id": "E1", "name": "broken2"},
    ]
    assert _lock_new_uid("None_AC1_E1_broken", locks) is None


# ---------------------------------------------------------------------------- #
# golden vectors на формат lock_unique_id (regression guard)                  #
# ---------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "pid,ac,eid,expected",
    [
        ("P1", "AC1", "E1", f"{DOMAIN}_lock_P1_AC1_E1"),
        ("P1", "AC1", None, f"{DOMAIN}_lock_P1_AC1_main"),
        ("12345", "67890", "abc", f"{DOMAIN}_lock_12345_67890_abc"),
    ],
)
def test_lock_unique_id_golden(pid, ac, eid, expected):
    """Изменение формата `lock_unique_id` — breaking change для существующих
    установок (даже после миграции). Этот тест ловит случайные правки.
    """
    assert lock_unique_id(pid, ac, eid) == expected


# ---------------------------------------------------------------------------- #
# перенос идентификаторов в реестре                                            #
# ---------------------------------------------------------------------------- #


async def _registry_with(hass, entries: list[tuple[str, str, str]]):
    """Создать записи реестра: (домен, unique_id, suggested_object_id)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for domain, uid, object_id in entries:
        registry.async_get_or_create(
            domain, DOMAIN, uid, suggested_object_id=object_id, config_entry=entry
        )
    return entry, registry


async def test_legacy_identifier_is_renamed_in_place(hass) -> None:
    """Старый идентификатор переезжает на стабильный, сущность остаётся своей.

    Без переноса пользователь получил бы новую сущность вместо своей — с
    потерей истории, автоматизаций и места на дашборде.
    """
    from custom_components.elektronny_gorod.entity_migration import (
        async_migrate_entity_unique_ids,
    )

    entry, registry = await _registry_with(hass, [("camera", "111_Подъезд 1", "cam")])

    await async_migrate_entity_unique_ids(hass, entry, {"cameras": CAMERAS, "locks": []})

    assert registry.async_get_entity_id("camera", DOMAIN, f"{DOMAIN}_camera_111")
    assert registry.async_get_entity_id("camera", DOMAIN, "111_Подъезд 1") is None


async def test_collision_leaves_the_duplicate_alone(hass) -> None:
    """Две старые записи на один новый идентификатор — переезжает первая.

    Так бывает у переименованной камеры: остаётся сирота со старым именем.
    Уронить весь запуск из-за неё нельзя — Home Assistant просто сообщит про
    неё «сущность не предоставляется интеграцией», и человек удалит её сам.
    """
    from custom_components.elektronny_gorod.entity_migration import (
        async_migrate_entity_unique_ids,
    )

    entry, registry = await _registry_with(
        hass,
        [
            ("camera", f"{DOMAIN}_camera_111", "cam_new"),
            ("camera", "111_Подъезд 1", "cam_legacy"),
        ],
    )

    await async_migrate_entity_unique_ids(hass, entry, {"cameras": CAMERAS, "locks": []})

    assert registry.async_get_entity_id("camera", DOMAIN, "111_Подъезд 1") is not None
    assert registry.async_get_entity_id("camera", DOMAIN, f"{DOMAIN}_camera_111")


async def test_foreign_and_current_entities_are_left_alone(hass) -> None:
    """Чужие сущности и уже переехавшие не трогаются."""
    from custom_components.elektronny_gorod.entity_migration import (
        async_migrate_entity_unique_ids,
    )

    entry, registry = await _registry_with(
        hass,
        [
            ("camera", f"{DOMAIN}_camera_333", "cam_ok"),
            ("sensor", "111_Подъезд 1", "sensor_other"),
        ],
    )

    await async_migrate_entity_unique_ids(hass, entry, {"cameras": CAMERAS, "locks": []})

    assert registry.async_get_entity_id("camera", DOMAIN, f"{DOMAIN}_camera_333")
    assert registry.async_get_entity_id("sensor", DOMAIN, "111_Подъезд 1")
