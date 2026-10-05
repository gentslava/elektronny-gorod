#!/usr/bin/env python3
"""Восстановить контракт сервиса из декомпилята jadx: пути, методы, поля DTO.

    jadx -j 4 --no-res -d /tmp/src app.apk
    ./apk-contract.py /tmp/src mh-temp-pass

Печатает Retrofit-интерфейсы, где встречается подстрока, и для каждого
упомянутого в них DTO — имена полей на проводе.

Почему именно так. R8 переименовывает поля в `f6779a`, и `@Metadata.d2`,
где обычно лежат исходные имена, у релизной сборки вычищен. Но два
источника переживают обфускацию:

* `toString()` data-класса Kotlin — компилятор зашивает туда имена
  свойств литералами (`"CreateTempPassRequestRaw(placeId="`);
* сгенерированный Moshi адаптер `<Class>JsonAdapter` — в нём лежат
  **имена на проводе**, а они и нужны, потому что могут отличаться от
  имён свойств.

Адаптер авторитетнее: `toString` даёт имя в Kotlin, JsonAdapter — в JSON.
Расхождение между ними означает `@Json(name = ...)`, и брать надо второе.

🔴 Это статическое доказательство: строка в бинарнике доказывает, что
клиент умеет так позвать, но не то, что сервер так отвечает, и не то,
какие значения допустимы. В api-reference оно идёт с пометкой
«static-only» до первого живого подтверждения (ADR-0006).
"""
from __future__ import annotations

import pathlib
import re
import sys

# Имена аннотаций Retrofit R8 тоже переименовывает, и в каждой сборке
# по-своему: `@GET` был `pt0.f` в 9.10.0 и стал `z45` в 9.11.0. Зашитая
# таблица имён молча переставала находить вызовы, поэтому соответствие
# берётся из самого Retrofit: его `RequestFactory` разбирает аннотации
# цепочкой `instanceof <имя> → "<МЕТОД>"`, и эти литералы обфускация не
# трогает.
RF_MARKER = '"@Headers annotation is empty."'
RF_VERB = re.compile(
    r'instanceof\s+([\w.]+)\)\s*\{\s*(?:[\w.]+\.)?\w+\(\s*'
    r'"(DELETE|GET|HEAD|PATCH|POST|PUT|OPTIONS)",\s*\(\(\1\)'
)
# `@HTTP` несёт метод и путь аргументами: `X.method(), X.path(), X.hasBody()`.
RF_HTTP = re.compile(
    r'instanceof\s+([\w.]+)\)\s*\{\s*\1\s+(\w+)\s*=\s*\(\1\)\s*\w+;\s*'
    r'(?:[\w.]+\.)?\w+\(\s*\2\.method\(\),\s*\2\.path\(\)'
)
# Суффикс `Raw` — соглашение этого приложения для DTO уровня API. Если в
# другом пакете оно иное, менять здесь.
DTO_REF = re.compile(r"[A-Za-z0-9_.]*\.([A-Za-z0-9_]+Raw)\b")
# `toString()` data-класса: "Cls(first=", ", second=", "first=" — имя поля
# всегда стоит перед `=` внутри строкового литерала.
TOSTRING = re.compile(r'"[^"]*?([a-zA-Z][A-Za-z0-9]*)=(?:"|,)')
# Единственный вызов в адаптере, у которого все аргументы — литералы: это
# `JsonReader.Options.of(...)`. Он и перечисляет имена на проводе по порядку.
OPTIONS = re.compile(r'=\s*\w+\.\w+\(\s*("(?:[^"]+)"(?:\s*,\s*"(?:[^"]+)")*)\s*\)\s*;')


ALL_VERBS = {"DELETE", "GET", "HEAD", "PATCH", "POST", "PUT", "OPTIONS"}
PACKAGE = re.compile(r"^package\s+([\w.]+);", re.M)
IMPORT = re.compile(r"^import\s+([\w.]+);", re.M)


def _package(text: str) -> str:
    m = PACKAGE.search(text)
    return m.group(1) if m else ""


def retrofit_aliases(tree: pathlib.Path) -> tuple[dict[str, str], str]:
    """Полные имена HTTP-аннотаций → метод, плюс полное имя `@HTTP`.

    Имя без точки — импорт самого `RequestFactory` или класс его пакета
    (в 9.11.0 всё лежит в `defpackage`); оно дополняется до полного, и
    дальше короткое написание в интерфейсе засчитывается только при
    импорте этого полного имени или в его пакете.

    Неполная таблица — тоже ошибка: пропавший метод означал бы, что вызовы
    этого типа молча исчезнут из вывода. А без `RequestFactory` не
    распознать ничего, и пустой вывод выглядел бы как «эндпоинтов нет».
    """
    for path in tree.rglob("*.java"):
        text = path.read_text(errors="replace")
        if RF_MARKER not in text:
            continue
        pkg = _package(text)
        imported = {imp.rsplit(".", 1)[-1]: imp for imp in IMPORT.findall(text)}

        def full(name: str) -> str:
            # Короткое имя — либо импорт самого RequestFactory (необфусцированный
            # Retrofit: `import retrofit2.http.GET;`), либо класс его пакета.
            if "." in name:
                return name
            return imported.get(name) or (f"{pkg}.{name}" if pkg else name)

        verbs = {full(name): verb for name, verb in RF_VERB.findall(text)}
        http = RF_HTTP.search(text)
        missing = sorted(ALL_VERBS - set(verbs.values()))
        if missing or not http:
            raise SystemExit("RequestFactory найден, но таблица аннотаций неполная: "
                             f"нет {', '.join(missing + ([] if http else ['@HTTP']))}")
        return verbs, full(http.group(1))
    raise SystemExit("RequestFactory Retrofit в декомпиляте не найден — "
                     "имена HTTP-аннотаций не восстановить")


def http_pattern(text: str, verbs: dict[str, str], http: str) -> tuple[re.Pattern[str], list[str]]:
    """Шаблон вызовов для одного файла и порядок методов в его группах.

    Полное имя (`@pt0.o`) годится всегда. Короткое (`@o`) — только если
    файл импортирует именно эту аннотацию или лежит в её пакете: иначе
    `@o` у Moshi (`tj0.o`) или `@b` чужого SDK читались как Retrofit, и в
    выводе появлялись «пути» вида `POST guest` из энумов.
    """
    pkg, imports = _package(text), set(IMPORT.findall(text))

    def spelled(name: str) -> str:
        owner, _, short = name.rpartition(".")
        forms = [re.escape(name)]
        if short and (name in imports or owner == pkg):
            forms.append(re.escape(short))
        return "|".join(forms)

    order = sorted(verbs, key=len, reverse=True)
    alt = "|".join(f"(?P<v{i}>{spelled(n)})" for i, n in enumerate(order))
    alt += f"|(?P<http>{spelled(http)})"
    return re.compile(rf"@(?:{alt})\((?P<args>[^)]*)\)"), [verbs[n] for n in order]


def wire_names(tree: pathlib.Path, cls: str) -> list[str]:
    """Имена полей на проводе — из `JsonReader.Options` в Moshi-адаптере.

    Брать все строки файла подряд нельзя: там же лежит `@Metadata` с
    именем Kotlin-модуля (`accesskeys_ntkRelease`), и оно уезжало в вывод
    как поле DTO.
    """
    for path in tree.rglob(f"{cls}JsonAdapter.java"):
        text = path.read_text(errors="replace")
        best: list[str] = []
        for m in OPTIONS.finditer(text):
            names = re.findall(r'"([^"]+)"', m.group(1))
            if len(names) > len(best):
                best = names
        return best
    return []


def kotlin_names(tree: pathlib.Path, cls: str) -> list[str]:
    for path in tree.rglob(f"{cls}.java"):
        text = path.read_text(errors="replace")
        out = [m.group(1) for m in TOSTRING.finditer(text)]
        if out:
            return list(dict.fromkeys(out))
    return []


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    tree, needle = pathlib.Path(argv[0]), argv[1]

    interfaces = [p for p in tree.rglob("*.java")
                  if needle in p.read_text(errors="replace")]
    if not interfaces:
        raise SystemExit(f"«{needle}» в декомпиляте не встречается")

    verbs, http = retrofit_aliases(tree)

    referenced: list[str] = []
    found = 0
    for path in sorted(interfaces):
        text = path.read_text(errors="replace")
        pattern, methods = http_pattern(text, verbs, http)
        calls = []
        for m in pattern.finditer(text):
            args = m.group("args")
            if m.group("http"):
                method = re.search(r'method\s*=\s*"([A-Z]+)"', args)
                route = re.search(r'path\s*=\s*"([^"]*)"', args)
                if method and route:
                    calls.append((method.group(1), route.group(1)))
                continue
            route = re.search(r'"([^"]*)"', args)
            if route:
                idx = next(i for i in range(len(methods)) if m.group(f"v{i}"))
                calls.append((methods[idx], route.group(1)))
        if not calls:
            continue
        found += len(calls)
        print(f"═══ {path.relative_to(tree)}")
        for verb, route in calls:
            print(f"   {verb:6} {route}")
        for ref in DTO_REF.findall(text):
            if ref not in referenced:
                referenced.append(ref)
        print()

    if not found:
        # Подстрока есть, а вызовов нет — значит, она в константе, логе
        # или распознавание сломалось. Пустой вывод тут хуже ошибки.
        raise SystemExit(f"«{needle}» встречается в {len(interfaces)} файл(ах), "
                         "но ни одного Retrofit-вызова с ним не распознано")

    for cls in referenced:
        wire, kotlin = wire_names(tree, cls), kotlin_names(tree, cls)
        print(f"── {cls}")
        print(f"   провод : {', '.join(wire) or '—'}")
        if kotlin and set(kotlin) != set(wire):
            print(f"   kotlin : {', '.join(kotlin)}   ⚠️ расходится: смотри @Json(name=)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
