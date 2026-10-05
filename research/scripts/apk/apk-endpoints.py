#!/usr/bin/env python3
"""Инвентарь и диф эндпоинтов по таблице строк dex — без полной декомпиляции.

Полный `jadx` на этих пакетах идёт минуты и даёт 19 тысяч файлов. Чтобы
понять «что нового в релизе», этого не нужно: пути лежат в таблице строк
dex и вытаскиваются за секунды. Декомпиляция нужна потом и только для
того, что диф показал.

    ./apk-endpoints.py new.apk                 # инвентарь
    ./apk-endpoints.py old.apk new.apk         # диф старая → новая

Принимает `.apk`, а также `.xapk`/`.apks` — из контейнера берутся все
вложенные `.apk`. Без этого контейнер давал пустой список, а в режиме дифа
он читался как «удалено всё».

Почему таблица строк, а не `strings`-подобный скан. В dex каждая строка
предваряется длиной в формате ULEB128, и её байт очень часто попадает в
печатный диапазон: у путей длиной 65–90 и 97–122 это буква. Скан печатных
последовательностей выдавал такие пути как `Kapi/…`, они не проходили
проверку формата и **молча пропадали** — на реальном пакете так терялась
пятая часть эндпоинтов, включая те, которые интеграция сама вызывает.
Подрезать префикс по символу нельзя: буква от буквы неотличима. Разбор
таблицы снимает вопрос — длина читается как длина, а не угадывается.
"""
from __future__ import annotations

import re
import struct
import sys
import zipfile

# Путь эндпоинта целиком: `api/...`, `/api/...`, `rest/...`. Якоря на обоих
# концах обязательны — без них выражение находило бы `api/` внутри имени
# класса (`Lcom/ertelecom/.../data/api/TempPassRaw;`).
ENDPOINT = re.compile(r"^/?(?:api|rest)/[A-Za-z0-9._~/{}-]+$")
_STRING_IDS_SIZE = 56
_STRING_IDS_OFF = 60


def _uleb128(buf: bytes, off: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = buf[off]
        off += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, off
        shift += 7


def dex_strings(dex: bytes):
    """Строки из таблицы `string_ids` файла dex."""
    count = struct.unpack_from("<I", dex, _STRING_IDS_SIZE)[0]
    table = struct.unpack_from("<I", dex, _STRING_IDS_OFF)[0]
    for index in range(count):
        data_off = struct.unpack_from("<I", dex, table + index * 4)[0]
        _, start = _uleb128(dex, data_off)          # длина в символах, не в байтах
        end = dex.index(b"\x00", start)
        yield dex[start:end].decode("utf-8", "replace")


def _dex_blobs(path: str):
    """Все dex пакета; для контейнера — dex каждого вложенного apk."""
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith(".dex"):
                yield archive.read(name)
            elif name.endswith(".apk"):
                import io

                with zipfile.ZipFile(io.BytesIO(archive.read(name))) as inner:
                    for nested in inner.namelist():
                        if nested.endswith(".dex"):
                            yield inner.read(nested)


def endpoints(path: str) -> set[str]:
    found: set[str] = set()
    for dex in _dex_blobs(path):
        found.update(s for s in dex_strings(dex) if ENDPOINT.match(s))
    if not found:
        print(f"⚠️  {path}: ни одного эндпоинта — это apk/xapk?", file=sys.stderr)
    return found


def main(argv: list[str]) -> int:
    if not argv or len(argv) > 2:
        raise SystemExit(__doc__)
    if len(argv) == 1:
        for line in sorted(endpoints(argv[0])):
            print(line)
        return 0

    old, new = endpoints(argv[0]), endpoints(argv[1])
    added, removed = sorted(new - old), sorted(old - new)
    print(f"{argv[0]}: {len(old)}\n{argv[1]}: {len(new)}\n")
    print(f"── добавлено ({len(added)}) ──")
    for line in added:
        print("  +", line)
    print(f"\n── удалено ({len(removed)}) ──")
    for line in removed:
        print("  -", line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
