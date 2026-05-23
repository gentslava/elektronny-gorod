# research/apk/

Локальная папка для оригинальных и пропатченных APK мобильных приложений «Мой Дом» / «Умный Дом.ру».

🔴 **Эта папка НЕ коммитится** (см. [`.gitignore`](../../.gitignore)). APK — это интеллектуальная собственность оператора, не наша.

## Что класть сюда

```
research/apk/
├── README.md                      ← только этот файл коммитится
├── myhome-original.apk            ← оригинал (скачан вручную)
├── myhome-patched.apk             ← результат 00-patch-apk.sh
└── archive/                       ← (опционально) старые версии
    ├── myhome-9.1.0-original.apk
    └── myhome-9.1.0-patched.apk
```

## Откуда брать APK

Официально через Google Play API скачать APK программно — **нельзя**. Варианты:

1. **APKMirror** — `https://www.apkmirror.com/apk/proptech/` (ищи нужный package).
2. **APKPure** — `https://apkpure.com/`.
3. **Свой телефон**: `adb shell pm path <package>` → `adb pull <path>`. Только для своего аккаунта.

Все три варианта — пользовательское действие, не автоматизируется AI-агентом.

## Package names

| Приложение | Package |
|---|---|
| Мой Дом (Электронный город) | `ru.inetra.intercom` |
| Умный Дом.ру | `com.ertelecom.smarthome` |

## Версионирование

При обновлении приложения:

1. Скачать новый APK → `myhome-original.apk` (overwrite).
2. (опционально) переименовать старый в `archive/myhome-<version>-original.apk` для diff-сравнения.
3. Запустить `./research/scripts/00-patch-apk.sh`.
4. Перейти к [`01-baseline-setup.sh`](../scripts/01-baseline-setup.sh) — обновить baseline.
5. Зафиксировать в `research/scripts/.baseline-meta`: новая версия + SHA256.

## Проверка версии APK

```bash
# Версия из manifest
aapt dump badging research/apk/myhome-original.apk | grep -E 'versionName|versionCode'

# Или через bundletool / apksigner
```

Сохраняй версию в `research/scripts/.baseline-meta` для трассируемости.

## Anti-checklist

- 🔴 НЕ коммитить `.apk` файлы.
- 🔴 НЕ распространять пропатченные `.apk` третьим лицам — это уже модифицированное приложение оператора.
- 🔴 НЕ использовать пропатченный APK как «обычный» клиент. Только для исследования.
- 🔴 НЕ скачивать APK с непроверенных источников (есть риск troyan-сборок).

## Связь

- [ADR-0006](../../docs/decisions/0006-mirror-app-behavior.md)
- [ADR-0007](../../docs/decisions/0007-stateful-emulator-baseline.md)
- [`research/scripts/README.md`](../scripts/README.md) — pipeline
- [`docs/aidd/runbooks/har-collection.md`](../../docs/aidd/runbooks/har-collection.md) — workflow
