Status: Active
Owner: Security & Privacy Agent
Last reviewed: 2026-05-22

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

> Любой пользователь Home Assistant, у которого включён уровень `debug` или `info` для `custom_components.elektronny_gorod.*`, **сегодня** видит чужой access_token в логах. Этот токен даёт API-доступ к чужим камерам, домофонам и финансовым данным.

## P0 — критичные утечки

### S-01. Утечка access_token в логи

- **Файл:** [`config_flow.py:77`](../../custom_components/elektronny_gorod/config_flow.py#L77)
- **Код:**
  ```python
  LOGGER.debug("Access token is %s", self.access_token)
  ```
- **Severity:** P0
- **Impact:** при `debug` уровне токен попадает в `home-assistant.log` (+ возможно в диагностические выгрузки).
- **Fix:** удалить строку. Не нужно логировать факт ввода токена.

### S-02. Утечка headers (Authorization: Bearer) и payload в логи

- **Файл:** [`http.py:11-13`](../../custom_components/elektronny_gorod/http.py#L11-L13)
- **Код:**
  ```python
  async def _log_request(url, headers, data) -> None:
      LOGGER.info(f"Sending API request to {url} with headers={headers} and data={data}")
  ```
- **Severity:** P0
- **Impact:**
  - `headers` всегда содержит `Authorization: Bearer <token>` после первого запроса.
  - `data` для auth POST-ов содержит **пароль** (`hash1`, `hash2`) или **SMS-код** или **payload с accountId/subscriberId**.
- **Fix:**
  - Создать helper `_redact_headers(headers)`, маскирующий `authorization`.
  - Не логировать `data` ни на каком уровне для auth endpoints.
  - Если для отладки нужна структура запроса — логировать `url`, `method`, `bool(data is not None)`, длина body.

### S-03. Утечка response body на DEBUG

- **Файл:** [`http.py:16-25`](../../custom_components/elektronny_gorod/http.py#L16-L25)
- **Код:**
  ```python
  if body := await response.text():
      LOGGER.debug(f"Response {_url} ({_method}) [{_status} {_reason}] data: {body}")
  ```
- **Severity:** P0 для auth endpoints (там в ответе `accessToken`, `refreshToken`).
- **Impact:** debug-логи содержат полный JSON ответа на login/refresh/verify.
- **Fix:** ввести redaction для auth-эндпоинтов (path-based whitelist), либо логировать только status + Content-Length.

### S-04. Утечка `entry.data` в логи

- **Файл:** [`config_flow.py:283, 291`](../../custom_components/elektronny_gorod/config_flow.py#L283)
- **Код:**
  ```python
  LOGGER.info("Entry %s already exists", entry.data)
  LOGGER.info("Reauth entry %s with params %s", entry.data, data)
  ```
- **Severity:** P0
- **Impact:** `entry.data` содержит токены, refresh-токены, user_agent (с account_id), operator_id.
- **Fix:**
  ```python
  LOGGER.info("Entry %s already exists", entry.entry_id)
  LOGGER.info("Reauth entry %s (%s)", entry.entry_id, entry.title)
  ```

### S-05. Per-request `ClientSession` без `async_get_clientsession`

- **Status:** ✅ **RESOLVED** в ветке `feat/shared-client-session` (ADR-0008). `HTTP.__init__(hass, ...)` + `async_get_clientsession(hass)` в `__request`. См. [audit A-05](project-audit.md).
- **Severity:** P0 (Reliability / Performance)
- **Original Impact:** каждый запрос — новый TLS handshake, отсутствовал общий pool HA, рост сокетов в TIME_WAIT, медленные ответы.

## P1 — важные

### S-06. Утечка `contract` объекта

- **Файл:** [`config_flow.py:201`](../../custom_components/elektronny_gorod/config_flow.py#L201)
- **Код:** `LOGGER.debug("Selected contract is %s. Contract object is %s", selected_id, contract)`
- **Impact:** `contract` содержит accountId, subscriberId, address, operatorId. Не токен, но PII.
- **Fix:** логировать только `selected_id`; либо обезличивать.

### S-07. Отсутствие auto-refresh на 401

- **Файл:** [`api.py:160-162`](../../custom_components/elektronny_gorod/api.py#L160-L162)
- **Impact:** при истечении access_token интеграция падает с `unauthorized` — пользователь должен заново вручную проходить config_flow, несмотря на наличие `refresh_token` в `entry.data`.
- **Fix:** реализовать `_refresh_access_token()` и автоматически вызывать при `401`. Затем — повторить запрос.

### S-08. Отсутствие diagnostics.py с redaction

- **Файл:** ❌
- **Impact:** когда пользователь экспортирует diagnostics через UI — HA по умолчанию пытается дампить `entry.data` целиком (через `async_get_config_entry_diagnostics`). Без нашего `diagnostics.py` пользователь не может безопасно поделиться диагностикой.
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

- **Файлы:** [`config_flow.py:362`](../../custom_components/elektronny_gorod/config_flow.py#L362), [`config_flow.py:419-420`](../../custom_components/elektronny_gorod/config_flow.py#L419-L420), [`camera.py:166-170`](../../custom_components/elektronny_gorod/camera.py#L166-L170)
- **Severity:** P1
- **Impact:** `go2rtc_password` (Basic Auth) хранится в `entry.data` без шифрования. Попадёт в diagnostics-выгрузку (S-08), в backup HA, в `.storage/core.config_entries`.
- **Fix:** добавить ключи в `TO_REDACT`. Долгосрочно — рассмотреть HA `auth_storage` / `Store` с pin-кодом.
- **Дополнительно:** в [`camera.py:167`](../../custom_components/elektronny_gorod/camera.py#L167) `import base64` находится внутри метода — функционально безопасно, но плохая практика (плюс auth-header строится «вручную» вместо `aiohttp.BasicAuth`).

### S-09. Нет timeout на HTTP-запросы

- **Файл:** [`http.py:60-62`](../../custom_components/elektronny_gorod/http.py#L60-L62)
- **Impact:** один зависший запрос блокирует setup и может удерживать сокет неограниченно.
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

- [x] **S-01..S-04, S-06 исправлены** (ветка `hotfix/p0-security`).
- [x] Добавлен helper `_logging.py` с `SENSITIVE_KEYS` + `redact()` (ADR-0004).
- [x] `grep -rE 'LOGGER\..*(token|password|sms|headers|entry\.data)' custom_components/elektronny_gorod/` возвращает 0 совпадений (после merge ветки).
- [ ] Добавлен `diagnostics.py` с redaction (S-08) — Итерация 2.
- [ ] Hotfix-релиз с changelog «security: redact tokens in logs» — после merge PR.
- [ ] Уведомление пользователей в release notes (включено в CHANGELOG.md).
- [ ] S-05 (shared ClientSession) — Этап 2, отдельный PR.
- [ ] S-07 (auto-refresh на 401) — Итерация 3 после HAR-сценария истечения.
- [ ] S-08, S-16 (diagnostics + go2rtc_password redact) — Итерация 2.

## Next reading

- For all findings: `project-audit.md`
- For HA-checklist: `ha-compatibility.md`
- For roadmap: `roadmap.md`
- For testing of fixes: `testing/strategy.md`
