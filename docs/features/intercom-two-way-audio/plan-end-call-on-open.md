# Завершение вызова на панели при открытии и «Отклонить» — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** открытие двери звонящей панели и «Отклонить» в HA останавливают звонок на самой панели, а не только гасят экран HA ([#98](https://github.com/gentslava/elektronny-gorod/issues/98), [A-120](../../audit/project-audit.md)).

**Architecture:** панель отпускает вызов только после `200 OK` какого-либо ответвления, поэтому держимый вызов завершается последовательностью `200 OK` → ждать `ACK` → `BYE` (новый `SipManager.async_end`). Сервис `hangup` переходит на неё; замок после успешного открытия шлёт dispatcher-сигнал, контроллер завершает вызов, если звонит та же панель. Тихий `release` остаётся для путей, где вызов уже закончен в другом месте или интеграция выгружается.

**Tech Stack:** Python 3.14, Home Assistant ≥ 2026.8.1, asyncio UDP SIP-стек интеграции, pytest + `pytest-homeassistant-custom-component`.

**Spec:** [call-answer-model.md §6a](call-answer-model.md) (доказательства PCAP + прод-лог 2026-10-26) и [A-120](../../audit/project-audit.md) (causal chain, целевое поведение, согласовано владельцем 2026-10-26).

## Execution

- **Plan revision:** `issue-98/r1`; scope одобрен владельцем gentslava 2026-10-26.
- **Execution mode:** subagent-driven; ветка `fix/98-end-call-at-panel` от `master` в изолированном worktree.
- **Implementer:** свежий `general-purpose` subagent на каждую задачу 1–4; root — docs-задача 5, проверки, freeze.
- **Reviewers (read-only, независимые):** `code-reviewer` (5 осей, весь candidate), `ha-expert` (lock-сущность, dispatcher, unload lifecycle), `qa-engineer` (тесты, регрессии). `security-auditor` не требуется: auth, токены, diagnostics и FCM не затрагиваются; новые строки лога не содержат идентификаторов звонка.
- **Acceptance live (прод-HA, после candidate freeze):** звонок в подъезд → `lock.unlock` без ответа → панель замолкает за ≤ 3 с; звонок → «Отклонить» в карточке → то же; звонок → «Принять» → «Открыть» → разговор завершён; звонок в подъезд → открыть калитку → вызов подъезда продолжает звонить.

## Global Constraints

- Логирование только `%`-форматированием; без `call_id`, `place_id`, `access_control_id`, SIP-логина и адресов в новых строках `INFO` и выше.
- Константы таймингов остаются в модуле (`.agents/rules/constants-locality.md`); в `const.py` — только сигнал, общий для `lock.py` и `__init__.py`.
- `ACK_TIMEOUT = 2.0` секунды (приложение получает `ACK` через ~0,1 с; запас на сеть).
- Никаких новых сущностей, сервисов, config-flow шагов и полей `strings.json`.
- Существующие тесты не удалять и не ослаблять.

## Review Focus

1. Открыли **другую** панель (калитку), пока звонит подъезд → вызов подъезда не трогается.
2. `ACK` не пришёл (сервер успел отменить вызов, потеря пакета) → через `ACK_TIMEOUT` всё равно `BYE` и закрытие сокета, без зависания и исключений.
3. Битый SDP в держимом INVITE → `200 OK` собрать нельзя → тихий `release`, как раньше, без исключения.
4. Выгрузка/перезагрузка записи во время звонка → вызов **не** принимается (тихий `release`), панель звонит как раньше.
5. FCM `ended`, hold-таймаут, смена звонящего → тихий `release`: нельзя отвечать на вызов, завершённый в другом месте.

---

### Task 1: `ACK` в SIP-протоколе

**Files:**
- Modify: `custom_components/elektronny_gorod/sip/protocol.py` (`__init__`, `datagram_received`, `answer`)
- Test: `tests/test_sip_protocol_dialogue.py`

**Interfaces:**
- Produces: атрибут `SipProtocol.acked: asyncio.Future[None] | None` — `None` до `answer()`; `answer()` создаёт новый future; входящий `ACK` резолвит его (`set_result(None)`), если он не завершён. `ACK` без `answer()` игнорируется.

- [ ] **Step 1: Failing tests** в разделе «Ответ на вызов и завершение»:
  - `test_ack_after_answer_is_reported` — INVITE → `answer(...)` → `datagram_received(_request("ACK"), addr)` → `protocol.acked.done()`; при этом `transport.sent` не пополнился (на `ACK` не отвечают).
  - `test_ack_without_answer_is_ignored` — INVITE без `answer` → `ACK` → `protocol.acked is None`, исключений нет.
  - `test_repeated_ack_is_harmless` — два `ACK` после `answer` → без `InvalidStateError`.
- [ ] **Step 2:** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_protocol_dialogue.py -q` → новые тесты FAIL (`AttributeError: acked`).
- [ ] **Step 3:** реализовать атрибут и ветку `elif method == "ACK"` в `datagram_received`; future создаётся через `asyncio.get_event_loop().create_future()`, как `registered`/`invite` в `connection_made`.
- [ ] **Step 4:** тот же прогон → PASS; весь `tests/test_sip_protocol*.py` зелёный.
- [ ] **Step 5:** commit `feat(sip): различать ACK на ответ держимого вызова`.

### Task 2: `SipManager.async_end` — завершить вызов на панели

**Files:**
- Modify: `custom_components/elektronny_gorod/sip/manager.py` (`accept`, новый `async_end`, новый `_media_from_offer`, docstring модуля)
- Test: `tests/test_sip_manager.py`

**Interfaces:**
- Consumes: `SipProtocol.acked` (Task 1), `SipProtocol.answer(invite_msg, addr, media_ip, media_port, payload_type, codec)`, `SipProtocol.send_bye()`.
- Produces:
  - `async def SipManager.async_end(self) -> None` — активный вызов: как `async_hangup` (`teardown(send_bye=True)`); держимый: `200 OK` → ожидание `held.sip.acked` до `ACK_TIMEOUT` → `send_bye()` → `held.release()`; нет вызова — no-op. RTP-сокет и uplink **не** поднимаются; в SDP — `RTP_LOCAL_PORT`.
  - `def _media_from_offer(body: str) -> tuple[int, str, str, int] | None` (модульная функция) — `(payload_type, codec, door_ip, door_port)` или `None` для offer без audio / без payload / с нечисловым payload или портом. `accept()` переходит на неё без изменения поведения.
  - `ACK_TIMEOUT = 2.0` — модульная константа рядом с `INVITE_TIMEOUT`.
  - `async_hangup` не меняется (тихий `release` для held).

- [ ] **Step 1: Failing tests** (фейковый held по образцу `_manager_holding`, но с `held.sip.acked`):
  - `test_end_answers_then_hangs_up_held_call` — `held.sip.acked` уже резолвлен → `answer` вызван с `RTP_LOCAL_PORT` и PT из offer `m=audio 4000 RTP/AVP 0`, затем `send_bye`, затем `release`; порядок проверить через `Mock().mock_calls` общего родителя; `mgr.holding is False`.
  - `test_end_sends_bye_even_without_ack` — `held.sip.acked` — незавершённый future, `ACK_TIMEOUT` пропатчен на `0.01` → `send_bye` и `release` вызваны, исключения нет (Review Focus 2).
  - `test_end_releases_silently_on_malformed_offer` — body без `m=audio` → `answer` и `send_bye` не вызывались, `release` вызван (Review Focus 3).
  - `test_end_hangs_up_active_call` — `mgr._active` — мок с `teardown = AsyncMock()` → `teardown` awaited с `send_bye=True`.
  - `test_end_without_call_is_noop` — пустой менеджер → без исключений.
  - Существующие `test_accept_*` остаются зелёными без правок.
- [ ] **Step 2:** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_manager.py -q` → новые FAIL.
- [ ] **Step 3:** вынести разбор offer в `_media_from_offer`, перевести `accept` на неё, реализовать `async_end`. Ожидание `ACK` — `asyncio.wait_for(asyncio.shield(acked), ACK_TIMEOUT)`, `TimeoutError` → `LOGGER.debug`; `acked is None` (транспорт уже закрыт) → ожидание пропускается. Итоговая строка `LOGGER.info("SIP: вызов завершён на панели (200 OK → BYE)")`.
- [ ] **Step 4:** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_manager.py tests/test_sip_manager_lifecycle.py -q` → PASS.
- [ ] **Step 5:** commit `feat(sip): завершать держимый вызов на панели через 200 OK → BYE`.

### Task 3: контроллер — «Отклонить» и сигнал открытия

**Files:**
- Modify: `custom_components/elektronny_gorod/const.py` (рядом с `SIGNAL_DOORBELL`)
- Modify: `custom_components/elektronny_gorod/sip/call_controller.py` (`async_hangup`, новый `handle_door_opened`, docstring модуля)
- Modify: `custom_components/elektronny_gorod/__init__.py` (подписка рядом с `SIGNAL_DOORBELL`; `async_unload_entry`)
- Test: `tests/test_sip_call_controller.py`, `tests/test_call_services.py` (`test_actions_survive_the_unload_of_the_last_entry`).

**Interfaces:**
- Consumes: `SipManager.async_end()` (Task 2).
- Produces:
  - `SIGNAL_DOOR_OPENED: Final = f"{DOMAIN}_door_opened"` в `const.py`; аргумент сигнала — `access_control_id: str`.
  - `async def DoorbellCallController.async_hangup(self, *, end_ringing: bool = True) -> bool` — при `end_ringing=True` снимает менеджер через `async_end()`, иначе через `async_hangup()`; остальное поведение (мост, `ENDED`, `_active = None`, возврат `had_call`) без изменений.
  - `@callback def DoorbellCallController.handle_door_opened(self, access_control_id: str) -> None` — если `self._active` есть и `self._active.access_control_id == access_control_id`, ставит `self._hass.async_create_task(self.async_hangup())`; иначе ничего.
  - `__init__.py`: `entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_DOOR_OPENED, sip_controller.handle_door_opened))`; в `async_unload_entry` — `await sip_controller.async_hangup(end_ringing=False)`.
  - `_async_release_held`, `_async_switch_caller`, hold-таймаут продолжают звать `manager.async_hangup()`.

- [ ] **Step 1: Failing tests:**
  - `test_hangup_ends_ringing_at_panel` — `_manager` мок с `async_end = AsyncMock()`, `async_hangup = AsyncMock()` → `await controller.async_hangup()` → `async_end` awaited, `async_hangup` не вызван.
  - `test_hangup_without_end_ringing_releases_silently` — `async_hangup(end_ringing=False)` → `manager.async_hangup` awaited, `async_end` не вызван (Review Focus 4).
  - `test_door_opened_for_ringing_panel_hangs_up` — hass-мок, в котором `async_create_task` складывает корутины в список; `handle_signal(_ring(ac="A"))` → `handle_door_opened("A")` → ровно одна корутина; после её `await` — `async_end` awaited, `current_call() is None`, в `_call_states` последний — `CALL_STATE_ENDED`.
  - `test_door_opened_for_other_panel_is_ignored` — ring `ac="A"`, `handle_door_opened("B")` → задач нет, `current_call()` не `None` (Review Focus 1).
  - `test_door_opened_without_call_is_ignored` — без ring → задач нет.
  - `test_door_opened_during_conversation_hangs_up` — `_manager.in_call = True`, ring `ac="A"` → после задачи `async_end` awaited.
  - `test_fcm_ended_while_holding_releases_silently` — по образцу `test_fcm_ended_clears_held_call_when_not_in_call`: после `_async_release_held` `manager.async_hangup` awaited, `async_end` не вызывался (Review Focus 5); аналогичная проверка для `_async_switch_caller`.
  - В `test_actions_survive_the_unload_of_the_last_entry` заменить `controller.async_hangup.assert_awaited_once()` на `assert_awaited_once_with(end_ringing=False)` (Review Focus 4 на уровне unload).
  - Существующие `test_hangup_*`, где мок задаёт только `async_hangup`, перевести на `async_end` там, где они проверяют пользовательский отбой; смысл утверждений не менять.
- [ ] **Step 2:** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_call_controller.py -q` → новые FAIL.
- [ ] **Step 3:** реализовать константу, параметр `end_ringing`, `handle_door_opened`, подписку и вызов в unload.
- [ ] **Step 4:** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_call_controller.py tests/test_call_services.py -q` → PASS.
- [ ] **Step 5:** commit `fix(sip): «Отклонить» и открытие двери завершают вызов на панели`.

### Task 4: замок сообщает об открытии

**Files:**
- Modify: `custom_components/elektronny_gorod/lock.py` (`async_unlock`, docstring модуля/метода)
- Test: `tests/test_lock.py`

**Interfaces:**
- Consumes: `SIGNAL_DOOR_OPENED` (Task 3).
- Produces: после **успешного** `coordinator.open_lock(...)` — `async_dispatcher_send(self.hass, SIGNAL_DOOR_OPENED, str(self._access_control_id))`; при `ClientError`/`TimeoutError` сигнал не отправляется.

- [ ] **Step 1: Failing tests:**
  - `test_unlock_reports_opened_door` — подписаться `async_dispatcher_connect(hass, SIGNAL_DOOR_OPENED, received.append)` → `lock.unlock` → `received == [str(AC_ID)]`.
  - `test_failed_unlock_does_not_report` — `mock_api.open_lock.side_effect = ClientError()` → `HomeAssistantError`, `received == []` (вызов продолжает звонить, его можно принять).
- [ ] **Step 2:** `PYTHONPATH=. .venv/bin/pytest tests/test_lock.py -q` → новые FAIL.
- [ ] **Step 3:** добавить отправку сигнала после успешного открытия, до перехода в `UNLOCKED`.
- [ ] **Step 4:** тот же прогон → PASS; затем полный `PYTHONPATH=. .venv/bin/pytest tests/ -q` → без падений.
- [ ] **Step 5:** commit `fix(lock): открытие двери завершает вызов той же панели`.

### Task 5: документация и changelog (root)

**Files:**
- Modify: `docs/features/intercom-two-way-audio/call-card-ux-spec.md` (строки сценариев 3–5 таблицы потоков)
- Modify: `docs/features/intercom-two-way-audio/call-answer-model.md` (§6 п.3: `hangup` до ответа = `200 OK` → `BYE`)
- Modify: `docs/audit/project-audit.md` (A-120: статус `🟢 resolved-in-branch — pending merge fix/98-end-call-at-panel`, раздел «Как закрыто»)
- Modify: `CHANGELOG.md` (`[Unreleased]` → `Changed`)

- [ ] **Step 1:** UX-спека: 3 — «Отклонить» до ответа принимает и сразу кладёт трубку, панель замолкает; 4 — «Открыть» без ответа открывает дверь и завершает вызов на панели, ответить после открытия нельзя; 5 — «Открыть» во время разговора открывает и завершает разговор (как приложение).
- [ ] **Step 2:** CHANGELOG: открытие двери звонящей панели и «Отклонить» останавливают звонок на панели, а не только экран HA; во время разговора открытие завершает разговор, как в приложении; оператор, вероятно, учитывает такой вызов как принятый, и другие устройства видят «отвечено на другом устройстве»; выгрузка интеграции во время звонка его не принимает.
- [ ] **Step 3:** `bash .agents/hooks/check-markdown-wrap.sh` и `bash .agents/hooks/check-audit-reconciliation.sh` → без ошибок; scrub на реальные ID/адреса.
- [ ] **Step 4:** commit `docs: A-120 — сброс вызова на панели при открытии и отклонении`.
