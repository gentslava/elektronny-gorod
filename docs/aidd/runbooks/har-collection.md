# Runbook: HAR collection (reverse engineering)

Процесс сбора HTTPS-трафика мобильного приложения «Мой Дом» / «Умный Дом.ру» для анализа API. Источник правды для любых spec в проекте — см. [ADR-0006](../../decisions/0006-mirror-app-behavior.md).

## Когда применять

- Перед началом любой новой фичи, которая трогает API.
- При расследовании bug-а, связанного с поведением серверной стороны.
- При периодической проверке: «не изменилось ли поведение приложения после обновления».

## Что понадобится

- Android-устройство (физическое или эмулятор Pixel) с возможностью установки сторонних APK.
- APK оригинального приложения:
  - «Мой Дом — Электронный город»: `ru.inetra.intercom`;
  - «Умный Дом.ру»: `com.ertelecom.smarthome`.
- Charles Proxy (или mitmproxy / Proxyman).
- Действующий аккаунт оператора (свой, **не чужой без согласия владельца**).
- Объектные знания: см. [ADR-0006](../../decisions/0006-mirror-app-behavior.md), [`source-base.md`](../source-base.md).

## Шаги

### 1. Подготовка устройства

Android современных версий блокирует MITM через certificate pinning. Варианты обхода:

**Вариант A — пересборка APK с отключённым pinning (предпочтительный).** Patches typically using [apk-mitm](https://github.com/shroudedcode/apk-mitm):

```bash
# Установка apk-mitm
npx apk-mitm <path/to/myhome.apk>
# → создаст myhome-patched.apk
adb install -r myhome-patched.apk
```

**Вариант B — Frida + objection (для root устройства).** Hooking SSLPinning runtime. Сложнее, не покрывается этим runbook.

**Вариант C — Magisk + TrustUserCerts + LSPosed/JustTrustMe.** Только для root.

Рекомендация — **Вариант A**. Не требует root.

### 2. Установка Charles Root Certificate

1. Charles → **Help → SSL Proxying → Install Charles Root Certificate on a Mobile Device or Remote Browser**.
2. На устройстве: открыть `chls.pro/ssl`, скачать `.pem`.
3. Settings → Security → Install from storage → выбрать сертификат → имя «Charles».
4. Это user cert. APK с MITM-патчем доверяет user certs (обычные APK — нет).

### 3. Настройка proxy на устройстве

- WiFi → Modify → Proxy: Manual.
- Host: IP машины с Charles в той же сети.
- Port: 8888 (по умолчанию Charles).

### 4. Включение SSL Proxying в Charles

Charles → **Proxy → SSL Proxying Settings**:
- Add: `*.proptech.ru:443`.
- (опционально) `*.googleapis.com:443` — для FCM-трафика.

### 5. Запись сессии

1. Charles → **File → New Session** (чистый старт).
2. На устройстве: запустить пропатченный APK.
3. Выполнить целевой сценарий (например: открыть домофон, посмотреть камеру, проверить баланс, обновить экран).
4. Charles → **File → Save Session As HAR…**.

### 6. Сохранение в проекте

Положить файл в [`research/api/`](../../../research/api/) (локальная папка, в `.gitignore`):

```
research/api/
├── README.md
├── 2026-05-23-login-sms-flow.har          ← naming: YYYY-MM-DD-<scenario>.har
├── 2026-05-23-open-intercom.har
└── notes/
    └── 2026-05-23-login-sms-flow.md       ← опционально: твой анализ
```

🔴 **НЕ коммитить.** HAR содержит:
- access_token, refresh_token;
- accountId, subscriberId, phone;
- адрес квартиры;
- финансовую информацию.

### 7. Анализ

Передать HAR агенту:
- Открыть нужный файл с Read tool.
- Агент разбирает endpoints, headers, последовательность, тайминги.
- Результат — обновление [`docs/architecture/api-reference.md`](../../architecture/api-reference.md) (когда будет создан) **только на основе того, что в HAR**.

## Анти-чек-лист

- 🔴 НЕ записывать сессии чужих аккаунтов без явного согласия владельца.
- 🔴 НЕ коммитить HAR в git (см. `.gitignore`).
- 🔴 НЕ публиковать HAR в issue / Discord / Gist даже после redaction (риск миссинга чего-то).
- 🔴 НЕ использовать HAR-снимок без записи источника (дата + сценарий + версия приложения).
- 🔴 НЕ экспериментировать с endpoints, которых нет в HAR — это нарушает ADR-0006.

## Verification

После сбора HAR — быстрый smoke-check:

```bash
# в HAR есть response для основных endpoints?
jq '.log.entries[] | .request.url' research/api/<file>.har | sort -u

# есть ли auth-flow?
jq '.log.entries[] | select(.request.url | contains("/auth/"))' research/api/<file>.har
```

## Связь

- [ADR-0006](../../decisions/0006-mirror-app-behavior.md) — обязательность зеркалирования.
- [`source-base.md`](../source-base.md) — внешние источники методологии.
- [`api-reference.md`](../../architecture/api-reference.md) (будет создан после первого анализа HAR).
- [`research/api/README.md`](../../../research/api/README.md) — naming convention и принципы хранения.

## Next reading

- `har-analysis.md` (запланирован, не создан) — как из HAR выводить структуру API в `api-reference.md`.
- [ADR-0006](../../decisions/0006-mirror-app-behavior.md).
