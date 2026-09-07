"""Метки времени для входа: тот же момент и тот же вид, что у приложения.

Оператор проверяет `hash2` — MD5 от компактной метки, — а вывести её он
может только из ISO-метки, которую мы прислали. Значит обе обязаны описывать
один момент. Раньше это выполнялось, но момент брался локальный и
подписывался `Z`: у новосибирского абонента метка уходила на семь часов
вперёд настоящего UTC. Ломаться это не ломалось (обе метки врали одинаково),
но расходилось с приложением, а его мы зеркалим — ADR-0006.
"""
from __future__ import annotations

import re
import time as time_module
from datetime import UTC, datetime

import pytest

from custom_components.elektronny_gorod.time import Time

_NOVOSIBIRSK = "Asia/Novosibirsk"  # UTC+7 — домашний часовой пояс оператора


@pytest.fixture
def in_novosibirsk(monkeypatch):
    """Перевести процесс в зону оператора и вернуть обратно.

    Без этого проверка бессмысленна на CI: раннеры живут в UTC, и локальное
    время там совпадает с UTC — прежний дефект был бы не виден.
    """
    monkeypatch.setenv("TZ", _NOVOSIBIRSK)
    time_module.tzset()
    yield
    monkeypatch.undo()
    time_module.tzset()


def test_timestamp_is_utc_not_local(in_novosibirsk) -> None:
    """Метка — настоящий UTC, а не местное время с приписанным `Z`."""
    stamp = Time().get_timestamp()

    sent = datetime.fromisoformat(stamp.removesuffix("Z")).replace(tzinfo=UTC)
    drift = abs((sent - datetime.now(UTC)).total_seconds())

    assert drift < 5, f"метка разошлась с UTC на {drift:.0f} с: {stamp}"


def test_simpletime_describes_the_same_moment(in_novosibirsk) -> None:
    """Компактная метка выводится из ISO-метки — оператор так и делает.

    Разъедься они, и подпись пароля перестала бы сходиться с меткой.
    """
    moment = Time()

    derived = moment.get_timestamp()[:19].replace("-", "").replace("T", "").replace(":", "")

    assert moment.get_simpletime() == derived


def test_timestamp_shape_matches_the_app() -> None:
    """Ровно три знака в долях секунды и `Z` вместо смещения.

    Формат снят с HAR приложения: дата, `T`, время, ровно три знака долей
    секунды и `Z` — без смещения.
    """
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", Time().get_timestamp())


def test_whole_second_does_not_lose_the_fraction(monkeypatch) -> None:
    """Ровная секунда не укорачивает метку.

    Прежняя реализация резала три символа с конца, а `isoformat()` при
    нулевых микросекундах доли не печатает вовсе — метка теряла хвост
    секунд, и подпись переставала сходиться. Раз в миллион входов.
    """
    moment = Time()
    monkeypatch.setattr(moment, "time", moment.time.replace(microsecond=0))

    assert moment.get_timestamp().endswith(".000Z"), moment.get_timestamp()
