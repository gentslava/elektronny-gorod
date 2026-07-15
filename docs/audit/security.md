Status: Active
Owner: Security & Privacy Agent
Last reviewed: 2026-07-15 (mobile apps 9.9.0 HTTP/push reconciliation;
pre-auth public bootstrap verified without Bearer, no new security finding)

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

## Сводка по состоянию на 2026-07-15

Проверка по текущему `master`: grep всех `LOGGER.*` в чувствительных файлах,
построчный разбор `_logging.py`/`http.py`/`config_flow.py`/`api.py`/
`camera.py`/`go2rtc.py`/`diagnostics.py`, а также поиск credential-like
значений в документации перед релизом.

| ID | Статус | Кратко |
|---|---|---|
| S-01..S-04 | ✅ RESOLVED | token/headers/body/entry.data — redaction через `_logging.py` |
| S-05 | ✅ RESOLVED | shared `async_get_clientsession` |
| S-06 | ✅ RESOLVED | логируется только `subscriberId`, не contract object |
| S-A71-01 | ✅ RESOLVED (new) | operator-токен в traceback при go2rtc PUT — оборван `from None` |
| S-08 | ✅ RESOLVED | `diagnostics.py` redacts secrets/PII; coordinator snapshot — counters-only |
| S-09 | ✅ RESOLVED | REST/binary `ClientTimeout` на GET/POST/DELETE operator API |
| S-10 | 🟡 OPEN P1 | retry/backoff для идемпотентных GET пока не реализован |
| S-16 | 🟡 MITIGATED P3 | go2rtc credentials redacted в diagnostics; plaintext HA storage остаётся |
| S-17/S-18 | 🟡 OPEN P3 | сырое логирование body/err в go2rtc.py (не активная утечка) |
| S-19 | 🟢 ACCEPTED-by-design | uplink AuthZ (любой auth HA-юзер) + AudioBridge `0.0.0.0:40020` LAN-exposure (ADR-0013/A-85) |
| S-20 | ✅ RESOLVED | production credential-like literal удалён из audit evidence; текущие production credentials не совпадают |

## P0 — критичные утечки (все RESOLVED)

### S-01. Утечка access_token в логи

- **Status:** ✅ **RESOLVED**. `config_flow.py:93` теперь
  `LOGGER.debug("Credentials captured (length=%d)", len(self.access_token))` —
  логируется только длина.
- **Original Severity:** P0 — при `debug` токен попадал в `home-assistant.log`.

### S-02. Утечка headers (Authorization: Bearer) и payload в логи

- **Status:** ✅ **RESOLVED**. `HTTP._log_request` использует
  `_logging.redact(headers)`; body не логируется (только размер /
  `<auth-path-redacted>`).
- **9.9.0 cross-check:** Bearer также не отправляется на pre-auth public
  `device-installations`; regression покрыта `tests/test_http.py`. Allowlist
  намеренно не совпадает с post-auth `/public/cameras`.
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

- **Status:** ✅ **RESOLVED**. `http.py` использует `_REST_TIMEOUT`
  (`total=30`, `connect=10`) и `_BINARY_TIMEOUT` (`total=60`, `connect=10`)
  и передаёт выбранный timeout во все GET/POST/DELETE запросы.
- **Файл:** [`http.py:15-22,120-126`](../../custom_components/elektronny_gorod/http.py)
- **Original Impact:** один зависший запрос к `myhome.proptech.ru` мог надолго
  задержать setup/coordinator tick.
- **Остаток:** retry/backoff вынесен в S-10/A-21 и применяется только к
  потенциально идемпотентным операциям; POST/login/open_lock автоматически
  ретраить нельзя.

### S-10. Нет retry / backoff на 5xx / network errors

- **Status:** 🟡 **OPEN** — timeout уже закрыт в S-09; это отдельный остаток.
- **Файл:** `http.py`, `api.py`
- **Impact:** временные сбои API → entry не загружается, требуется reload.
- **Fix:** обернуть critical-запросы в `tenacity`-подобный retry (или ручной exponential backoff).

### S-20. Production credential-like literal в публичном audit evidence

- **Status:** ✅ **RESOLVED** в текущем дереве 2026-07-13: фактическое значение
  заменено на `[REDACTED]` в `project-audit.md`.
- **Original Severity:** P0, если credential активен; публичный репозиторий
  содержит историю файла с production snapshot.
- **Verification:** SHA-256 отпечаток исторического значения безопасно сравнен
  с настроенными `go2rtc_password` двух production config entries — совпадений
  нет (`active_match=false`), само значение не выводилось.
- **Residual:** старое неактивное значение остаётся в git history. Историю
  `master` не переписываем; credential нельзя повторно использовать.

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

### S-19. Uplink-микрофон: AuthZ + AudioBridge LAN-exposure (ADR-0013, A-85)

- **Status:** 🟢 **ACCEPTED-by-design** (решение пользователя — accept-risk +
  документировать; guard **не** добавляется). Связано с
  [audit A-85](project-audit.md) + [ADR-0013](../decisions/0013-uplink-mic-transport.md).
- **Severity:** low/medium.
- **Файлы:** `uplink_ws.py` (WS-команда `elektronny_gorod/intercom_uplink`),
  `sip/call_controller.py` (`feed_uplink`), `sip/bridge.py` (`AudioBridge`).

**S-UP-01 — uplink AuthZ (accept-risk).** WS-команда `intercom_uplink` доверяет
**любому authenticated HA-юзеру**: любой авторизованный пользователь HA может
«говорить» (стримить микрофон) в активный вызов домофона.

- **Обоснование принятия:** паттерн **зеркалит штатный HA voice-assistant**
  (`connection.async_register_binary_handler` — тот же авторизованный WebSocket,
  через который проходит весь UI). HA-модель доверия: authenticated = trusted.
  Per-call AuthZ-разграничение поверх этого было бы **отклонением** от платформы,
  не митигацией реальной угрозы.
- **Окно атаки эфемерно:** uplink работает только при активном вызове (~120с),
  вне вызова команда возвращает error (нет активного контроллера/sink).
- **Mitigation:** ничего не добавляем (by-design). Документировано как
  known-limitation в A-85. Если в будущем появится multi-tenant сценарий — тогда
  пересмотр через новый ADR.

**AudioBridge LAN-exposure (downlink-аудио).** `AudioBridge` (`sip/bridge.py`)
поднимает HTTP-сервер на `0.0.0.0:40020` (mpegts/aac-аудио гостя) для доступа
go2rtc по LAN.

- **Severity:** low — bind на все интерфейсы, но: (1) **эфемерно** на время вызова
  (teardown на hangup/BYE); (2) контент = аудио гостя у двери, не секрет/токен;
  (3) bind `0.0.0.0` нужен, чтобы go2rtc (отдельный процесс/контейнер) дотянулся
  по LAN-адресу хоста (`detect_lan_ip()`).
- **Status:** accepted-by-design. Возможное hardening (bind на конкретный
  LAN-IP вместо `0.0.0.0`) — polish-backlog, не блокер.

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

`manifest.json:requirements` больше не пуст: `firebase-messaging>=0.4` (FCM-вызов,
ADR-0011 — тянет protobuf / http_ece / cryptography; «серая зона» приватных API
Google задокументирована в [A-80](project-audit.md)) + `audioop-lts>=0.2.1`
(G.711-транскод SIP, A-81; только Python 3.13+). Остальное — `aiohttp`/`voluptuous`/
`yarl` из HA core. CVE-risk core-зависимостей управляется HA core; внешние pip-deps
обновляются по линии поддержки upstream (см. A-80 §Watch).

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
