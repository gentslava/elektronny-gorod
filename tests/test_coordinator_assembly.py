"""Сборка камер и замков из ответа оператора — формы, которые редко видно.

Домофон без подъездов и камера, привязанная к месту, а не к домофону,
встречаются у реальных абонентов, но в тестовых данных до сих пор не
попадались. Ошибка здесь не падает, а тихо теряет устройство: камеры нет в
списке — и человек не понимает, почему она есть в приложении и нет в Home
Assistant.
"""
from __future__ import annotations

import logging

import pytest

from aiohttp import ClientError
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from test_operator_failures import _make_config_entry


def _coordinator(hass: HomeAssistant, entry, api: MagicMock):
    from custom_components.elektronny_gorod.coordinator import (
        ElektronnyGorodUpdateCoordinator,
    )

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI",
        return_value=api,
    ):
        return ElektronnyGorodUpdateCoordinator(hass, entry=entry)


def _api(**overrides) -> MagicMock:
    api = MagicMock()
    api.http = AsyncMock()
    api.http.user_agent = AsyncMock()
    api.query_places = AsyncMock(return_value=[{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": "1000000", "address": "addr"},
    }])
    api.query_screens_settings = AsyncMock(return_value={})
    api.query_access_controls = AsyncMock(return_value=[])
    api.query_cameras = AsyncMock(return_value=[])
    api.query_public_cameras = AsyncMock(return_value=[])
    api.query_dnd_settings = AsyncMock(return_value=[])
    api.query_balance = AsyncMock(return_value={})
    for key, value in overrides.items():
        setattr(api, key, AsyncMock(return_value=value))
    return api


async def test_intercom_without_entrances_still_gives_a_camera_and_a_lock(
    hass: HomeAssistant,
) -> None:
    """Домофон без списка подъездов — сам себе подъезд.

    Такой домофон обслуживает одну дверь, и оператор не присылает `entrances`
    вовсе. Пропустить эту форму значит потерять и камеру, и кнопку открытия.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_access_controls=[{
        "id": "2000",
        "name": "Калитка",
        "externalCameraId": "CAM-GATE",
        "allowOpen": True,
    }])

    data = await _coordinator(hass, entry, api)._async_update_data()

    assert [c["id"] for c in data["cameras"]] == ["CAM-GATE"]
    assert len(data["locks"]) == 1
    assert data["locks"][0]["access_control_id"] == "2000"


async def test_place_camera_is_taken_by_its_external_id(
    hass: HomeAssistant,
) -> None:
    """Камера места опознаётся по внешнему id, а не по внутреннему.

    Идентификаторы у оператора двух видов, и поток отдаётся по внешнему:
    перепутать их значит показать чёрный прямоугольник.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_cameras=[
        {"id": "internal", "externalCameraId": "CAM-YARD", "name": "Двор"},
    ])

    data = await _coordinator(hass, entry, api)._async_update_data()

    assert [c["id"] for c in data["cameras"]] == ["CAM-YARD"]


async def test_broken_lock_data_does_not_take_the_cameras_down(
    hass: HomeAssistant, caplog
) -> None:
    """Отказ на сборке замков не уносит с собой камеры того же адреса.

    Частичные данные лучше пустых: камеры продолжают работать, а о пропаже
    замков сказано один раз.
    """
    marker = "форма ответа изменилась"
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_access_controls=[{
        "id": "2000",
        "name": "Калитка",
        "externalCameraId": "CAM-GATE",
        "allowOpen": True,
    }])
    coordinator = _coordinator(hass, entry, api)

    with patch.object(
        coordinator, "_collect_locks_for_place", side_effect=ValueError(marker)
    ), caplog.at_level(logging.INFO):
        data = await coordinator._async_update_data()
        await coordinator._async_update_data()

    assert [c["id"] for c in data["cameras"]] == ["CAM-GATE"]
    assert data["locks"] == []
    complaints = [r for r in caplog.records if r.getMessage().startswith("Замки:")]
    assert len(complaints) == 1, "жалоба повторяется на каждом цикле"
    assert marker not in complaints[0].getMessage(), "текст исключения в журнале"

    # Возвращение: без него ключ остаётся в отметках навсегда, и следующая
    # пропажа замков дедуплицируется в тишину.
    caplog.clear()
    with caplog.at_level(logging.INFO):
        data = await coordinator._async_update_data()

    assert [
        r for r in caplog.records if "Замки: данные снова приходят" in r.getMessage()
    ], "возвращение замков должно быть видно"
    assert data["locks"], "замки вернулись в снимок"


async def test_failing_camera_source_is_reported_once_and_on_recovery(
    hass: HomeAssistant, caplog
) -> None:
    """Пропажа камер видна в журнале — один раз, и один раз возвращение.

    Раньше отказ проглатывался в слое API и доходил до координатора как
    «камер нет». Тот считал это успехом: камеры исчезали из интерфейса, а в
    журнале не оставалось ни строки ни на одном уровне. Правило Silver
    `log-when-unavailable` просит ровно две строки — на пропажу и на
    возвращение.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_cameras=[{"id": "internal", "externalCameraId": "CAM-YARD"}])
    coordinator = _coordinator(hass, entry, api)

    with caplog.at_level(logging.INFO):
        api.query_cameras = AsyncMock(side_effect=ClientError("оператор молчит"))
        for _ in range(3):
            await coordinator._async_update_data()

        complaints = [
            r for r in caplog.records if "Камеры места" in r.getMessage()
        ]
        assert len(complaints) == 1, "жалоба повторяется на каждом цикле"
        # Тип исключения, а не его текст: в тексте оператора бывает адрес, а
        # `repr` ответа aiohttp — ещё и полный URL со всеми заголовками.
        assert "оператор молчит" not in complaints[0].getMessage()
        assert "ClientError" in complaints[0].getMessage()

        caplog.clear()
        api.query_cameras = AsyncMock(
            return_value=[{"id": "internal", "externalCameraId": "CAM-YARD"}]
        )
        data = await coordinator._async_update_data()

    assert [
        r for r in caplog.records
        if "Камеры места: данные снова приходят" in r.getMessage()
    ], "возвращение камер должно быть видно, и именно этого источника"
    assert "CAM-YARD" in [c["id"] for c in data["cameras"]]


async def test_one_broken_camera_source_does_not_take_the_others_down(
    hass: HomeAssistant, caplog
) -> None:
    """Отказ одного источника камер не уносит остальные — и он слышен.

    Домофонные, личные и общедомовые камеры приходят тремя разными
    запросами. Общий `except` на все три означал бы, что молчание оператора
    про общедомовые гасит и камеру домофона у двери. Но выжившие соседи —
    половина требования: общедомовых и городских камер у обычного абонента
    больше всего, и их пропажа обязана быть видна одной строкой. Транспорт
    об этом молчит по замыслу, так что фронт здесь — единственный источник.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(
        query_access_controls=[{"id": "2000", "externalCameraId": "CAM-GATE"}],
        query_cameras=[{"id": "i", "externalCameraId": "CAM-YARD"}],
    )
    api.query_public_cameras = AsyncMock(side_effect=ClientError("нет общедомовых"))
    coordinator = _coordinator(hass, entry, api)

    with caplog.at_level(logging.INFO):
        data = await coordinator._async_update_data()
        await coordinator._async_update_data()

        complaints = [
            r for r in caplog.records
            if r.getMessage().startswith("Общедомовые камеры:")
        ]
        assert len(complaints) == 1, "жалоба повторяется на каждом цикле"
        assert "нет общедомовых" not in complaints[0].getMessage()

        caplog.clear()
        api.query_public_cameras = AsyncMock(
            return_value=[{"id": "p", "externalCameraId": "CAM-PUB"}]
        )
        data = await coordinator._async_update_data()

    assert [
        r for r in caplog.records
        if "Общедомовые камеры: данные снова приходят" in r.getMessage()
    ], "возвращение общедомовых камер должно быть видно"
    assert sorted(c["id"] for c in data["cameras"]) == [
        "CAM-GATE", "CAM-PUB", "CAM-YARD"
    ]


@pytest.mark.parametrize(
    ("screens", "reason"),
    [
        (["ПОЛЕЗНАЯ-НАГРУЗКА"], "корень list"),
        ({"screens": ["ПОЛЕЗНАЯ-НАГРУЗКА"]}, "запись раздела не словарь"),
        (
            {"screens": [
                {"type": "PUBLIC_CAMERAS", "hidden": ["ПОЛЕЗНАЯ-НАГРУЗКА"]}
            ]},
            "скрытый элемент не словарь",
        ),
        (
            {"screens": [
                {"type": "PUBLIC_CAMERAS", "hidden": [{"eid": "ПОЛЕЗНАЯ-НАГРУЗКА"}]}
            ]},
            "элемент без id",
        ),
        # Пропажа верхнего ключа — то же переименование поля с тем же
        # последствием, и раньше она молчала.
        ({"sections": ["ПОЛЕЗНАЯ-НАГРУЗКА"]}, "нет ключа screens"),
    ],
)
async def test_unexpected_screens_shape_does_not_break_the_cycle(
    hass: HomeAssistant, caplog, screens, reason
) -> None:
    """Частично годная форма настроек разбирается, а не сваливается на фронт.

    Форму задаёт оператор, полагаться на неё нельзя. Упасть можно — вызов
    под фронтом «Настройки экранов», — но тогда непонятный кусок обнулил бы
    всю видимость места. Поэтому вытягиваем что вытягивается, и на фронт не
    сваливаемся: иначе проверки формы можно было бы снять незаметно.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(
        query_screens_settings=screens,
        query_access_controls=[{"id": "2000", "externalCameraId": "CAM-GATE"}],
        query_public_cameras=[{"id": "p", "externalCameraId": "CAM-PUB"}],
    )

    with caplog.at_level(logging.DEBUG):
        data = await _coordinator(hass, entry, api)._async_update_data()

    hidden = {c["id"]: c["hidden"] for c in data["cameras"]}
    # Именно на общедомовой: её `hidden` читается из разобранных настроек, а
    # у камеры домофона без подъездов это литерал — проверка на ней держала
    # бы что угодно, включая переворот умолчания в «скрыть всё».
    assert hidden == {"CAM-GATE": False, "CAM-PUB": False}, hidden
    # Разбор справился сам — на фронт не свалились: иначе проверки формы
    # можно было бы снять, и тест бы этого не заметил.
    assert not [
        r for r in caplog.records if r.getMessage().startswith("Настройки экранов:")
    ]
    # Но и не молча: без этой строки дрейф схемы оператора неотличим от
    # «пользователь ничего не прятал», а скрытые сущности вернутся в панель.
    drift = [
        r for r in caplog.records
        if "Настройки видимости" in r.getMessage()
    ]
    assert drift, "о вытянутой через силу форме надо сказать хотя бы на debug"
    # Что именно не так — иначе разные дрейфы неразличимы, и строка не
    # помогает тому, ради кого написана.
    assert any(reason in r.getMessage() for r in drift), [r.getMessage() for r in drift]
    # Но без тела, и во ВСЕХ записях: их по одной на запрошенный раздел, а
    # проверка первой пропустила бы утечку, сделанную по-разному для разных.
    assert "ПОЛЕЗНАЯ-НАГРУЗКА" not in caplog.text
    # Уровень: именно он делает приемлемым то, что строка не дедуплицируется.
    assert {r.levelno for r in drift} == {logging.DEBUG}


async def test_broken_access_controls_payload_keeps_the_rest_of_the_place(
    hass: HomeAssistant, caplog
) -> None:
    """Испорченный ответ по домофонам не уносит баланс и остальные данные.

    Внешний фронт сборки камер — единственное, что удерживает обновление
    места от падения, когда оператор присылает не ту форму: `data` в ответе
    по домофонам типом не проверяется. После разведения источников камер по
    своим фронтам его перестали исполнять тесты — и сломать его можно было
    бы, не уронив ни одного.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(
        query_access_controls=["строка вместо объекта"],
        query_balance={"balance": 100},
    )

    coordinator = _coordinator(hass, entry, api)
    with caplog.at_level(logging.INFO):
        data = await coordinator._async_update_data()

    complaints = [r for r in caplog.records if r.getMessage().startswith("Сборка камер:")]
    assert len(complaints) == 1, "о сорванной сборке камер сказано ровно один раз"
    assert "AttributeError" in complaints[0].getMessage(), "нужен тип, а не текст"
    assert data["cameras"] == []
    assert data["balances"], "баланс места пережил отказ по камерам"

    # Возвращение — вторая половина правила, и её легко забыть: без неё ключ
    # остаётся в отметках навсегда, и следующая пропажа дедуплицируется в
    # тишину.
    caplog.clear()
    api.query_access_controls = AsyncMock(
        return_value=[{"id": "2000", "externalCameraId": "CAM-GATE"}]
    )
    with caplog.at_level(logging.INFO):
        data = await coordinator._async_update_data()

    assert [
        r for r in caplog.records
        if "Сборка камер: данные снова приходят" in r.getMessage()
    ], "возвращение сборки камер должно быть видно"
    assert [c["id"] for c in data["cameras"]] == ["CAM-GATE"]


@pytest.mark.parametrize(
    ("method", "front"),
    [
        ("query_screens_settings", "Настройки экранов"),
        ("query_dnd_settings", "Режим «не беспокоить»"),
        ("query_access_controls", "Домофоны"),
        ("query_balance", "Баланс"),
    ],
)
async def test_every_front_says_it_once_and_says_it_back(
    hass: HomeAssistant, caplog, method, front
) -> None:
    """Каждый вид данных сообщает о пропаже и о возвращении сам за себя.

    До снятия глотания в слое API эти фронты срабатывали только на
    подставленных в тесте исключениях, а настоящий отказ оператора до них не
    доходил. Теперь доходит — значит, и проверять их надо на настоящем.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api()
    working = getattr(api, method)
    setattr(api, method, AsyncMock(side_effect=ClientError("оператор молчит")))
    coordinator = _coordinator(hass, entry, api)

    with caplog.at_level(logging.INFO):
        await coordinator._async_update_data()
        await coordinator._async_update_data()

        complaints = [
            r for r in caplog.records if r.getMessage().startswith(f"{front}:")
        ]
        assert len(complaints) == 1, "жалоба повторяется на каждом цикле"
        assert "оператор молчит" not in complaints[0].getMessage()

        caplog.clear()
        setattr(api, method, working)
        await coordinator._async_update_data()

    assert [
        r for r in caplog.records
        if f"{front}: данные снова приходят" in r.getMessage()
    ], "возвращение данных должно быть видно"


async def test_screens_payload_that_cannot_be_parsed_lands_on_its_front(
    hass: HomeAssistant, caplog
) -> None:
    """Совсем неразбираемая форма становится жалобой, а не трейсбеком.

    Проверки формы вытягивают то, что вытягивается; скаляр вместо списка не
    вытягивается ничем. Такой разбор обязан свалиться на фронт настроек
    экранов — он и владеет этим ответом, — а не улететь наружу: обработчик
    неожиданных исключений в ядре пишет трейсбек безусловно, на каждом цикле.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(
        query_screens_settings={"screens": 5},
        query_access_controls=[{"id": "2000", "externalCameraId": "CAM-GATE"}],
        query_public_cameras=[{"id": "p", "externalCameraId": "CAM-PUB"}],
    )
    coordinator = _coordinator(hass, entry, api)

    with caplog.at_level(logging.INFO):
        data = await coordinator._async_update_data()
        await coordinator._async_update_data()

    complaints = [
        r for r in caplog.records if r.getMessage().startswith("Настройки экранов:")
    ]
    assert len(complaints) == 1, "жалоба повторяется на каждом цикле"
    # Умолчание на отказе — «ничего не скрыто». Проверяем на общедомовой:
    # её `hidden` читается из настроек, а у камеры домофона это литерал, и
    # переворот умолчания в «скрыть всё» на ней был бы не виден.
    hidden = {c["id"]: c["hidden"] for c in data["cameras"]}
    assert hidden == {"CAM-GATE": False, "CAM-PUB": False}, hidden


async def test_no_front_lets_the_operator_text_into_the_journal(
    hass: HomeAssistant, caplog
) -> None:
    """Ни один фронт не выпускает в журнал текст исключения оператора.

    Жалоба пишет тип исключения, а не его текст, — но передать
    отформатированный текст фронту может и вызывающий, а таких мест восемь.
    В проде это `ClientError(ClientResponse)`, чей `repr` печатает полный
    URL и весь блок заголовков ответа: то самое, что соседняя строка
    транспорта нарочно прогоняет через редакцию.

    Проверка идёт по всем фронтам сразу: точечные ассерты закрывали четыре
    из восьми, и подстановка текста в остальных проходила незамеченной.
    """
    marker = "СЕКРЕТ-В-ТЕКСТЕ-ИСКЛЮЧЕНИЯ"
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api()
    for method in (
        "query_balance",
        "query_screens_settings",
        "query_access_controls",
        "query_cameras",
        "query_public_cameras",
        "query_dnd_settings",
    ):
        setattr(api, method, AsyncMock(side_effect=ClientError(marker)))

    coordinator = _coordinator(hass, entry, api)
    # Двумя циклами, потому что фронты сборки и фронты источников взаимно
    # исключают друг друга: пока сборщик падает, его внутренние источники не
    # выполняются, а пока они падают — сборщик отрабатывает успешно. За один
    # цикл проверка обошла бы два места из восьми.
    with caplog.at_level(logging.DEBUG):
        await coordinator._async_update_data()
        with (
            patch.object(
                coordinator,
                "_collect_cameras_for_place",
                side_effect=ValueError(marker),
            ),
            patch.object(
                coordinator,
                "_collect_locks_for_place",
                side_effect=ValueError(marker),
            ),
        ):
            await coordinator._async_update_data()

    ours = [
        r for r in caplog.records
        if r.name.startswith("custom_components.elektronny_gorod")
    ]
    complaints = [r for r in ours if "нет данных" in r.getMessage()]
    fronts = {r.getMessage().split(":", 1)[0] for r in complaints}
    # Ровно восемь, а не «хотя бы»: замолчавший фронт делает проверку утечки
    # для него пустой, и на «>= N» это прошло бы незамеченным.
    assert fronts == {
        "Баланс",
        "Настройки экранов",
        "Домофоны",
        "Камеры места",
        "Общедомовые камеры",
        "Сборка камер",
        "Замки",
        "Режим «не беспокоить»",
    }, fronts
    leaked = [r.getMessage() for r in ours if marker in r.getMessage()]
    assert leaked == [], leaked


@pytest.mark.parametrize(
    "screens",
    [
        {},
        {"screens": []},
        {"screens": [{"type": "PUBLIC_CAMERAS", "hidden": []}]},
        {"screens": [{"type": "ACCESS_CONTROLS", "hidden": [{"id": "E1"}]}]},
    ],
)
async def test_well_formed_screens_say_nothing(
    hass: HomeAssistant, caplog, screens
) -> None:
    """Штатная форма не жалуется — в том числе пустая.

    Молчание здесь и есть смысл сигнала: `{}` значит «пользователь ничего не
    настраивал». Стоит появиться лишней причине — и каждая установка начнёт
    писать по строке на раздел каждый цикл, а положительная проверка этого
    не увидит.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(query_screens_settings=screens)

    with caplog.at_level(logging.DEBUG):
        await _coordinator(hass, entry, api)._async_update_data()

    assert not [
        r for r in caplog.records if "Настройки видимости" in r.getMessage()
    ], caplog.text


async def test_partial_settings_keep_what_parsed(hass: HomeAssistant, caplog) -> None:
    """Годное берём, даже если рядом мусор.

    Обещание «учли, что смогли» ничем не держалось: ни один случай не
    сочетал годную запись с испорченной, поэтому разбор мог бы выбрасывать
    уже разобранное — и скрытые камеры вернулись бы в панель молча.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(
        query_screens_settings={"screens": [
            {"type": "PUBLIC_CAMERAS", "hidden": [
                {"id": "CAM-PUB"}, "мусор", {"eid": "нет id"},
            ]},
        ]},
        query_public_cameras=[
            {"id": "a", "externalCameraId": "CAM-PUB"},
            {"id": "b", "externalCameraId": "CAM-OTHER"},
        ],
    )

    with caplog.at_level(logging.DEBUG):
        data = await _coordinator(hass, entry, api)._async_update_data()

    hidden = {c["id"]: c["hidden"] for c in data["cameras"]}
    assert hidden == {"CAM-PUB": True, "CAM-OTHER": False}, hidden
    assert [r for r in caplog.records if "Настройки видимости" in r.getMessage()]


async def test_zero_is_a_valid_hidden_id(hass: HomeAssistant, caplog) -> None:
    """Идентификатор `0` — настоящий id, а не «его нет».

    Проверка на `None`, а не на ложность: с проверкой на ложность такая
    сущность и не скрылась бы, и была бы объявлена дрейфом схемы — ложное
    утверждение ровно того класса, ради которого сигнал и вводился.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(
        query_screens_settings={"screens": [
            {"type": "PUBLIC_CAMERAS", "hidden": [{"id": 0}]},
        ]},
        query_public_cameras=[{"id": "a", "externalCameraId": "0"}],
    )

    with caplog.at_level(logging.DEBUG):
        data = await _coordinator(hass, entry, api)._async_update_data()

    assert [c["hidden"] for c in data["cameras"]] == [True]
    assert not [
        r for r in caplog.records if "Настройки видимости" in r.getMessage()
    ], caplog.text


async def test_hidden_ids_do_not_leak_between_sections(
    hass: HomeAssistant,
) -> None:
    """Скрытое в одном разделе не прячет одноимённое в другом.

    Идентификаторы камер и подъездов приходят из разных пространств и могут
    совпасть. Без фильтра по разделу скрылась бы не та сущность.
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    api = _api(
        query_screens_settings={"screens": [
            {"type": "ACCESS_CONTROLS", "hidden": [{"id": "7"}]},
        ]},
        query_public_cameras=[{"id": "a", "externalCameraId": "7"}],
    )

    data = await _coordinator(hass, entry, api)._async_update_data()

    assert [c["hidden"] for c in data["cameras"]] == [False], "скрыли не ту камеру"
