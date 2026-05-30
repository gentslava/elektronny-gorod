Status: Active
Owner: Security & Privacy Agent
Last reviewed: 2026-05-30 (S-01..S-06 verified RESOLVED по коду; S-17/S-18 added)

Source files:
- `custom_components/elektronny_gorod/config_flow.py`
- `custom_components/elektronny_gorod/http.py`
- `custom_components/elektronny_gorod/api.py`
- `custom_components/elektronny_gorod/helpers.py`
- `custom_components/elektronny_gorod/user_agent.py`

Related docs:
- `project-audit.md`
- `ha-compatibility.md`
- `architecture/overview.md`
- `roadmap.md`

Used by agents:
- Security & Privacy Agent, Lead Architect, Validator

Quality gates:
- SECURITY_OK

---

# Security & Privacy Audit

## Threat model в одну строку

> **(Исторический — закрыт.)** До hotfix `hotfix/p0-security` любой пользователь
> HA с уровнем `debug`/`info` для `custom_components.elektronny_gorod.*` видел
> чужой access_token в логах. **По состоянию на 2026-05-30 утечки нет** —
> верифицировано по коду независимым security-аудитом (см. статусы S-01..S-06).

## Сводка по состоянию на 2026-05-30

Независимая проверка по факту кода (ветка `fix/a71-camera-stream-auto-recovery`,
v3.2.0): grep всех `LOGGER.*` в чувствительных файлах + построчный разбор
`_logging.py`/`http.py`/`config_flow.py`/`api.py`/`camera.py`/`go2rtc.py`.

| ID | Статус | Кратко |
|---|---|---|
| S-01..S-04 | ✅ RESOLVED | token/headers/body/entry.data — redaction через `_logging.py` |
| S-05 | ✅ RESOLVED | shared `async_get_clientsession` |
| S-06 | ✅ RESOLVED | логируется только `subscriberId`, не contract object |
| S-A71-01 | ✅ RESOLVED (new) | operator-токен в traceback при go2rtc PUT — оборван `from None` |
| S-08 | 🔴 OPEN P1 | `diagnostics.py` отсутствует → entry.data дампится целиком |
| S-09 | 🔴 OPEN P1 | нет `ClientTimeout` на основном operator API (`http.py:110,112`) |
| S-16 | 🔴 OPEN P1 | go2rtc_password plaintext в entry.data (утечёт через S-08) |
| S-17/S-18 | 🟡 OPEN P3 | сырое логирование body/err в go2rtc.py (не активная утечка) |

## P0 — критичные утечки (все RESOLVED)

### S-01. Утечка access_token в логи

- **Status:** ✅ **RESOLVED**. `config_flow.py:93` теперь
  `LOGGER.debug("Credentials captured (length=%d)", len(self.access_token))` —
  логируется только длина.
- **Original Severity:** P0 — при `debug` токен попадал в `home-assistant.log`.

### S-02. Утечка headers (Authorization: Bearer) и payload в логи

- **Status:** ✅ **RESOLVED**. `http.py:16-34` `_log_request` использует
  `redact(headers)` (`_logging.py:52`); body не логируется (только размер /
  `<auth-path-redacted>`).
- **Original Severity:** P0 — `headers` содержал `Authorization: Bearer`,
  `data` auth-POST содержал пароль/SMS-код.

### S-03. Утечка response body на DEBUG

- **Status:** ✅ **RESOLVED**. `http.py:37-56` `_log_response` логирует только
  status + Content-Length; body не читается; для auth-path размер пропущен.
- **Original Severity:** P0 — debug-логи содержали `accessToken`/`refreshToken`.

### S-04. Утечка `entry.data` в логи

- **Status:** ✅ **RESOLVED**. `config_flow.py:299,307` теперь `entry.entry_id`.
  Grep `LOGGER.*entry\.(data|options)` по компоненту → 0 совпадений.
- **Original Severity:** P0 — `entry.data` содержал токены/user_agent/operator_id.

### S-05. Per-request `ClientSession` без `async_get_clientsession`

- **Status:** ✅ **RESOLVED** в ветке `feat/shared-client-session` (ADR-0008). `HTTP.__init__(hass, ...)` + `async_get_clientsession(hass)` в `__request`. См. [audit A-05](project-audit.md).
- **Severity:** P0 (Reliability / Performance)
- **Original Impact:** каждый запрос — новый TLS handshake, отсутствовал общий pool HA, рост сокетов в TIME_WAIT, медленные ответы.

## P1 — важные

### S-06. Утечка `contract` объекта

- **Status:** ✅ **RESOLVED**. `config_flow.py:217` теперь
  `LOGGER.debug("Selected contract subscriberId=%s", selected_id)` — только ID,
  не contract object.
- **Original Impact:** `contract` содержал accountId, subscriberId, address,
  operatorId (PII).

### S-A71-01. Operator-токен в traceback при go2rtc PUT (NEW, RESOLVED)

- **Status:** ✅ **RESOLVED** (ветка `fix/a71-camera-stream-auto-recovery`).
- **Файл:** [`camera.py:124-134`](../../custom_components/elektronny_gorod/camera.py#L124-L134)
- **Impact (предотвращённый):** forpost RTSP-URL с токеном (`https://forpost-N.
  novotelecom.ru:18081/rtsp/a<NNNNNN>/<token>/...`) передаётся в go2rtc PUT;
  при `ClientError` он мог попасть в traceback/RuntimeError.
- **Fix:** `except ClientError as exc: raise RuntimeError(f"...{type(exc).__name__}") from None`
  — цепочка оборвана `from None`, в RuntimeError только имя класса исключения и
  `resp.status` (без body). PATCH-ошибки swallowed.

### S-07. Отсутствие auto-refresh на 401

- **Файл:** [`api.py:160-162`](../../custom_components/elektronny_gorod/api.py#L160-L162)
- **Impact:** при истечении access_token интеграция падает с `unauthorized` — пользователь должен заново вручную проходить config_flow, несмотря на наличие `refresh_token` в `entry.data`.
- **Fix:** реализовать `_refresh_access_token()` и автоматически вызывать при `401`. Затем — повторить запрос.

### S-08. Отсутствие diagnostics.py с redaction

- **Status:** ✅ **RESOLVED** — добавлен `diagnostics.py` (3.3.0).
  `async_get_config_entry_diagnostics` → `async_redact_data(entry.as_dict(), TO_REDACT)`.
  `TO_REDACT = SENSITIVE_KEYS ∪ {phone, contract, operator_id, account_id,
  subscriber_id, name, address}` (синхронизирован с `_logging.py`; есть тест
  `test_to_redact_covers_sensitive_keys`). Coordinator-снимок — только счётчики.
  6 тестов `tests/test_diagnostics.py`. Разблокирует `SECURITY_OK`.
- **Файл:** [`diagnostics.py`](../../custom_components/elektronny_gorod/diagnostics.py)
- **Original Impact:** когда пользователь экспортирует diagnostics через UI — HA по умолчанию пытается дампить `entry.data` целиком (через `async_get_config_entry_diagnostics`). Без нашего `diagnostics.py` пользователь не может безопасно поделиться диагностикой.
- **Fix:** создать `diagnostics.py`:
  ```python
  TO_REDACT = {
      "access_token", "refresh_token", "user_agent", "name",
      "account_id", "subscriber_id",
      "go2rtc_username", "go2rtc_password",  # S-16
  }

  async def async_get_config_entry_diagnostics(hass, entry):
      return async_redact_data(entry.as_dict(), TO_REDACT)
  ```

### S-16. go2rtc credentials в `entry.data` plaintext

- **Status:** 🟡 **MITIGATED** — `go2rtc_username`/`go2rtc_password` в `TO_REDACT`
  → больше **не утекают** в diagnostics-выгрузку (S-08 RESOLVED). Остаётся
  plaintext в `.storage`/backup (HA-storage limitation) — полное шифрование
  (`Store`/pin) в backlog, не блокер.
- **Файлы:** [`config_flow.py:362`](../../custom_components/elektronny_gorod/config_flow.py#L362), [`config_flow.py:419-420`](../../custom_components/elektronny_gorod/config_flow.py#L419-L420), [`camera.py:166-170`](../../custom_components/elektronny_gorod/camera.py#L166-L170)
- **Severity:** P1 → P3 (после mitigation)
- **Impact:** `go2rtc_password` (Basic Auth) хранится в `entry.data` без шифрования. ~~Попадёт в diagnostics-выгрузку (S-08)~~ — закрыто redaction.
- **Fix:** ✅ ключи в `TO_REDACT`. Долгосрочно — рассмотреть HA `Store` с pin-кодом.
- **Дополнительно:** в [`camera.py:167`](../../custom_components/elektronny_gorod/camera.py#L167) `import base64` находится внутри метода — функционально безопасно, но плохая практика (плюс auth-header строится «вручную» вместо `aiohttp.BasicAuth`).

### S-09. Нет timeout на HTTP-запросы

- **Status:** 🔴 **STILL OPEN** (P1) — подтверждено 2026-05-30.
  `http.py:110` (`session.get`) и `:112` (`session.post`) — без `timeout=`.
  Grep `ClientTimeout|timeout` в `http.py`/`api.py` → 0. ⚠️ go2rtc-пути
  (`camera.py:107,641`, но **не** `go2rtc.py` — см. A-72) имеют timeout;
  основной operator API — нет. См. [audit A-21](project-audit.md).
- **Файл:** [`http.py:110,112`](../../custom_components/elektronny_gorod/http.py#L110-L112)
- **Impact:** один зависший запрос к `myhome.proptech.ru` блокирует setup /
  coordinator tick и может удерживать сокет неограниченно.
- **Fix:** `ClientTimeout(total=30)` на всех запросах.

### S-10. Нет retry / backoff на 5xx / network errors

- **Файл:** `http.py`, `api.py`
- **Impact:** временные сбои API → entry не загружается, требуется reload.
- **Fix:** обернуть critical-запросы в `tenacity`-подобный retry (или ручной exponential backoff).

## P2 — желательно

### S-11. Логирование `Failed to fetch balance: %s` f-string

- **Файл:** [`sensor.py:90`](../../custom_components/elektronny_gorod/sensor.py#L90)
- **Impact:** `e` может содержать ClientResponse с URL → утечка через `repr()`. Минор.
- **Fix:** `LOGGER.exception("Failed to fetch balance")`.

### S-12. SHA1 для пароля

- **Файл:** [`helpers.py:35-39`](../../custom_components/elektronny_gorod/helpers.py#L35-L39)
- **Impact:** SHA1 — устаревший алгоритм. Но это формат серверного API; не наша уязвимость. Документировать.

### S-13. Hardcoded crypto «соль» (reverse-engineered)

- **Файл:** [`helpers.py:43-44`](../../custom_components/elektronny_gorod/helpers.py#L43-L44)
- **Impact:** юридический риск (использование reverse-engineered протокола в нарушение ToS оператора). Не уязвимость, но требует понимания.
- **Mitigation:** документировать ограничения в README; рекомендовать пользователям предоставлять access_token напрямую (advanced mode) как альтернативу.

### S-14. UUID не привязан к HA install_id

- **Файл:** [`user_agent.py:18`](../../custom_components/elektronny_gorod/user_agent.py#L18)
- **Impact:** каждый раз новый UUID при создании UserAgent — это нарушает «привязку» сессии на стороне оператора. На практике сейчас работает, но фрагильно.
- **Mitigation:** uuid сохраняется в `entry.data` и не пересоздаётся при reauth.

## P3 — низкий

### S-15. Случайный Pixel device fingerprint

- **Файл:** [`user_agent.py:11-13`](../../custom_components/elektronny_gorod/user_agent.py#L11-L13)
- **Impact:** ToS-вопрос; не уязвимость безопасности.

### S-17. go2rtc.py — сырой ClientError в логе (NEW)

- **Файл:** [`go2rtc.py:104-105`](../../custom_components/elektronny_gorod/go2rtc.py#L104-L105)
- **Код:** `LOGGER.debug("go2rtc cleanup request failed: %s", err)`
- **Impact:** `str(ClientError)` может содержать URL. В **текущем** flow URL =
  `{base_url}/api/streams?src=ha_check_<uuid>` (validation cleanup, synthetic
  stream name, креды в Authorization header а не в URL) → реальной утечки нет.
  Паттерн фрагильный, противоречит defense-in-depth из `camera.py` (`from None`).
- **Fix:** логировать `type(err).__name__` вместо `err`. НЕ блокер.

### S-18. go2rtc.py — сырой response body в логе (NEW)

- **Файл:** [`go2rtc.py:78,103`](../../custom_components/elektronny_gorod/go2rtc.py#L78)
- **Код:** `LOGGER.debug("...failed: %s %s", resp.status, body)`
- **Impact:** body от go2rtc в validation/cleanup flow = echo dummy src
  (`rtsp://127.0.0.1...` / `ha_check_<uuid>`) без operator-токена → безопасно в
  текущем использовании. Unbounded body-логирование — фрагильно.
- **Fix:** логировать только `resp.status`. НЕ блокер.

## CI / Secrets

| Аспект | Статус |
|---|---|
| `release.yaml` использует `secrets.GITHUB_TOKEN` | ✅ стандартно |
| Нет hardcoded API keys в коде | ✅ |
| Нет `.env` в репозитории | ✅ |
| Pre-commit hook на проверку секретов | 🔴 нет |

## MCP / Tools

Сейчас в репозитории нет `.claude/`, `.cursor/`, `.github/copilot-instructions.md` — следовательно, нет рисков MCP-стороны.

При появлении (Итерация 3) добавить:
- `docs/aidd/MCP_TOOLS.md` — права и ограничения;
- pre-commit hook на проверку секретов в diff.

## Dependency vulnerabilities

`manifest.json:requirements: []` — нет специфичных зависимостей. Используются версии `aiohttp`/`voluptuous`/`yarl`, поставляемые с HA core. CVE-risk управляется HA core.

## Сводный план

| ID | Что | Приоритет | Trade-off | Owner |
|---|---|---|---|---|
| S-01 | Удалить лог токена | P0 | none | Security |
| S-02 | Redact headers / data в логах | P0 | потеря удобства отладки → компенсируется feature flag | Security |
| S-03 | Redact auth response body | P0 | то же | Security |
| S-04 | Логировать `entry_id` вместо `entry.data` | P0 | none | Security |
| S-05 | Shared `ClientSession` | P0 | требует прокинуть `hass` глубже | Architecture |
| S-06 | Не логировать contract | P1 | none | Security |
| S-07 | Auto-refresh на 401 | P1 | требует код | Architecture |
| S-08 | `diagnostics.py` с redaction | P1 | мелкая работа | HA Expert |
| S-09 | `ClientTimeout` | P1 | none | Architecture |
| S-10 | Retry/backoff | P1 | требует код | Architecture |

## Definition of done для SECURITY_OK gate

- [x] **S-01..S-04, S-06 исправлены** (ветка `hotfix/p0-security`; верифицировано по коду 2026-05-30).
- [x] Добавлен helper `_logging.py` с `SENSITIVE_KEYS` + `redact()` (ADR-0004).
- [x] `grep -rE 'LOGGER\..*(token|password|sms|headers|entry\.data)' custom_components/elektronny_gorod/` возвращает 0 реальных утечек (1 совпадение `config_flow.py:93` — redacted-by-design, длина).
- [x] S-05 (shared ClientSession) — RESOLVED (ADR-0008).
- [x] S-A71-01 (operator-токен в traceback go2rtc PUT) — RESOLVED (`from None`).
- [ ] 🔴 **S-08 — `diagnostics.py` с redaction всё ещё ОТСУТСТВУЕТ** (P1, блокирует gate).
- [ ] 🔴 **S-09 — `ClientTimeout` на основном API всё ещё ОТСУТСТВУЕТ** (P1).
- [ ] S-16 (go2rtc_password redact) — зависит от S-08.
- [ ] S-07 (auto-refresh на 401) — Итерация 3 после HAR-сценария истечения.
- [ ] S-17/S-18 (go2rtc.py raw logging) — P3, defense-in-depth, по мере touch.

## Next reading

- For all findings: `project-audit.md`
- For HA-checklist: `ha-compatibility.md`
- For roadmap: `roadmap.md`
- For testing of fixes: `testing/strategy.md`
