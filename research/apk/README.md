# research/apk/

Локальная папка для оригинальных и пропатченных APK мобильных приложений
оператора. Используется для capture HAR через mitmproxy/Charles.

🔴 **Эта папка НЕ коммитится** (см. [`.gitignore`](../../.gitignore)). APK —
интеллектуальная собственность оператора, не наша.

## Приложения, с которыми работаем

| Приложение | Package | Backend | Используется в integration |
|---|---|---|---|
| **Мой Дом** (Электронный город / Дом.ру / др.) | `ru.inetra.intercom` | `myhome.proptech.ru` | ✅ да |
| **Электронный город** (legacy / standalone) | `com.electronnijgorod.novosibirsk` | `my.2090000.ru` + Keycloak | ❌ нет (другой бэкенд) |
| **Дом.ру Агент** | `com.ertelecom.agent` | (не разбирали) | ❌ нет |
| **Умный Дом.ру** | `com.ertelecom.smarthome` | (не разбирали) | ❌ нет |

Подробнее про разделение бэкендов — см. [`docs/architecture/api-reference.md`](../../docs/architecture/api-reference.md) раздел «Backends — separate ecosystems».

⚠️ **Важно про naming:** имя файла APK / xapk / apks никак не связано с реальным package — оператор может выпускать «Мой Дом.ру» как Дом.ру Агент (`com.ertelecom.agent`), а «Мой Дом» как `ru.inetra.intercom`. **Всегда проверяй package через aapt / jadx до patching.**

## Форматы файлов

APK скачивается в одном из трёх форматов:
- **`.apk`** — обычный single-package. `apk-mitm <file>.apk` → `<file>-patched.apk`. Install через `adb install`.
- **`.xapk`** (APKPure формат) — zip с base + split-config APKs. `apk-mitm` принимает напрямую, выдаёт `-patched.xapk`. Распаковать (`unzip`) → `adb install-multiple *.apk`.
- **`.apks`** (Google Play Android App Bundle) — bundletool output. `apk-mitm` принимает напрямую, выдаёт `-patched.apks`. Распаковать → `adb install-multiple base.apk split_config*.apk` (игнорируй `*.idsig`).

## Структура файлов

```
research/apk/
├── README.md                                  ← коммитится
├── myhome-9.7.0-original.apks                 ← Мой Дом (.apks, Google Play bundle)
├── myhome-9.7.0-original-patched.apks         ← после apk-mitm
├── eg-3.6.6-original.apk                      ← Электронный город (legacy)
├── eg-3.6.6-original-patched.apk
├── domru-agent-3.64.0-original.apk            ← Дом.ру Агент (com.ertelecom.agent)
├── domru-agent-3.64.0-original-patched.apk
├── umnydom-9.3.0-original.apk                 ← Умный Дом.ру
└── umnydom-9.3.0-original-patched.apk
```

## Откуда брать APK

1. **APKMirror** — `https://www.apkmirror.com/`
2. **APKPure** — `https://apkpure.com/` (отдают `.xapk` — это zip с base APK
   + split-configs; распакуй через `unzip` и возьми `*.apk` нужного package).
3. **Свой телефон**: `adb shell pm path <package>` → `adb pull <path>`.

## Патчинг (отключение SSL pinning)

```bash
# Один раз — установка
npm install -g apk-mitm

# Каждый APK
apk-mitm research/apk/<file>-original.apk
# Выход: research/apk/<file>-original-patched.apk
```

⚠️ **Не запускать параллельно несколько `apk-mitm`** — они race-condition'ятся
на скачивании `uber-apk-signer.jar` в кэш. Запускай последовательно.

После патча `logs/` создаётся в корне проекта (gitignored).

## Установка на устройство для capture

```bash
# Эмулятор / отладочное устройство
adb install research/apk/<file>-original-patched.apk

# Старая версия (если уже установлена)
adb install -r research/apk/<file>-original-patched.apk

# Проверка
adb shell pm list packages | grep -E "intercom|electronnij|smarthome"
```

После установки настрой Charles/mitmproxy CA на устройстве (как обычный
user cert — `apk-mitm` уже снял pinning, значит user-cert будет доверенным).

## Capture сценарии (важные)

Для разбора как приложение разделяет камеры на категории:

- Главный экран (cold start) — base requests
- Экран «Камеры» / «Все камеры» (если есть подкатегории — критично)
- Открыть подменю «Подъездные камеры» / «Внутридомовые» / «Городские» если есть
- Открыть 1 камеру каждого типа (intercom / лифт / городская) — для stream
- Экран домофона
- Экран баланса (его нет в текущих HAR)
- Pull-to-refresh

## Anti-checklist

- 🔴 НЕ коммитить `.apk` / `.xapk` файлы (gitignored — `*.apk`, `*.xapk`, `*.apks`).
- 🔴 НЕ распространять пропатченные APK третьим лицам — это модифицированное
  приложение оператора.
- 🔴 НЕ использовать пропатченный APK как обычный клиент — только для capture.
- 🔴 НЕ скачивать APK с непроверенных источников (риск trojan-сборок).

## Связь

- [ADR-0006](../../docs/decisions/0006-mirror-app-behavior.md) — обязательность mirror-app behavior
- [ADR-0007](../../docs/decisions/0007-stateful-emulator-baseline.md) — baseline-pipeline
- [`research/scripts/README.md`](../scripts/README.md) — pipeline через mitmproxy
- [`docs/aidd/runbooks/har-collection.md`](../../docs/aidd/runbooks/har-collection.md) — workflow
- [`docs/architecture/api-reference.md`](../../docs/architecture/api-reference.md) — найденные endpoints + backend split
