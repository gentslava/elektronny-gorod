# Модель приёма вызова домофона (pcap-доказано 2026-07-13)

> Полная картина «как приложение принимает вызов и поднимает двусторонний звук».
> Доказано **захватами трафика реального приложения** (PCAPdroid, Android) +
> реверсом APK + live-экспериментами с probe. Вывод 2026-06-23 о
> register-on-answer исправлен новым полным pre-answer захватом 2026-07-13.
> PII/реальные IP — плейсхолдеры.

## 1. Главный вывод (модель приложения)

Штатное приложение использует **register-on-ring с коротким held-окном**:
после push-wake сразу регистрирует SIP-контакт, получает `INVITE`, отвечает
`100 Trying` и держит INVITE до ответа или завершения звонка.

Полный флоу:
```
1. Звонок с панели → FCM `CALL_INCOMING` будит приложение/интеграцию.
2. Клиент шлёт свежий `REGISTER` к realm конкретного access control.
3. Сервер присылает `INVITE`; клиент примерно через 20–40 мс отвечает
   `100 Trying`, но не принимает разговор.
4. До ответа INVITE держится около 24 секунд. Сервер может завершить его через
   `CANCEL`, либо клиент отклоняет его `603` по окончании окна.
5. «Ответить» → `200 OK` на уже держимый INVITE → `ACK` → RTP-latching → разговор.
6. Завершение — `BYE`; после окна клиент снимает короткую регистрацию.
```

🔑 `REGISTER → INVITE → 100 Trying` — это **pre-answer**, а не автоответ.
`200 OK` появляется только после явного ответа пользователя.

## 2. Тайминги из полного pcap штатного приложения (2026-07-13)

```
вызов 1: REGISTER → INVITE (+4.46с) → 100 Trying (+20мс)
          → CANCEL сервера через ~24с → 200(CANCEL) + 487(INVITE) → unregister
вызов 2: REGISTER → INVITE → 100 Trying (+23мс)
          → 603 клиента через ~24с → unregister
вызов 3: REGISTER → INVITE → 100 Trying (+40мс)
          → 200 OK через 4.27с после INVITE → ACK → RTP → BYE → unregister
```

## 3. 200 OK + SDP приложения (точно из pcap, +28.40с)

```
SIP/2.0 200 Ok
... эхо 2×Via, From, To+наш-tag, Call-ID, CSeq, Record-Route ...
Contact: <sip:{login}@{realm};gr=urn:uuid:...>;+sip.instance="<urn:uuid:...>"   # GRUU
Allow: INVITE, ACK, CANCEL, OPTIONS, BYE, REFER, NOTIFY, MESSAGE, SUBSCRIBE, INFO, PRACK, UPDATE
v=0
o={login} 3637 3150 IN IP4 {LOCAL_IP}    # ЛОКАЛЬНЫЙ адрес (не STUN!)
s=Talk
c=IN IP4 {LOCAL_IP}
m=audio 46061 RTP/AVP 0 8 101            # G.711 PCMU(0)/PCMA(8) + telephone-event(101)
a=rtpmap:101 telephone-event/8000        # только 101 (0/8 — статич. PT, rtpmap не нужен)
a=rtcp:40498                             # RTCP на ОТДЕЛЬНОМ порту (не audio+1!)
```

- **БЕЗ STUN/ICE.** Анонсирует локальный адрес → downlink доходит через **FreeSWITCH
  RTP-latching**: устройство шлёт uplink первым (+ STUN/RTP-keepalive 20B сразу), сервер
  «защёлкивает» source и шлёт downlink туда.
- Answer **убирает CN(13)** из offer (offer `0 8 101 13` → answer `0 8 101`).
- **GRUU** в Contact (`;gr=urn:uuid` + `+sip.instance`) — RFC 5627.
- INVITE-offer от сервера: `o=FreeSWITCH … IN IP4 {media-SBC}`, `c=IN IP4 {media-SBC}`,
  `m=audio {port} RTP/AVP 0 8 101 13` (PCMU/PCMA/telephone-event/CN), `ptime:20`.
  Media-сервер (FreeSWITCH `mod_sofia`) — отдельный публичный IP, меняется по вызову;
  realm/registrar — другой IP (`:5060/UDP`). BYE приходит от `mod_sofia@{media-SBC}`.

## 4. REGISTER приложения (точный формат из pcap, +28.23с)

```
REGISTER sip:{realm} SIP/2.0
From/To: <sip:{login}@{realm}>
Contact: <sip:{login}@{ip}:{nat_port};app-id=com.novotelecom.domophone;
         pn-type=google;Call-Id:%20{call_id};pn-tok={FCM_TOKEN}>
Expires: 30
Supported: replaces, outbound, gruu, path
Accept: application/sdp
User-Agent: Myhome/Myhome-android
Authorization: Digest realm="{realm}", nonce="...", algorithm=MD5, username="{login}", uri="..."
```

- **Expires=30** (короткий) + re-REGISTER + `iterate()` каждые 20мс (держит свежесть).
- **push-params проприетарные** (НЕ RFC 8599 `pn-provider/pn-prid`!), внутри Contact URI:
  `app-id=com.novotelecom.domophone; pn-type=google; Call-Id:%20{call_id}; pn-tok={FCM_TOKEN}`.
  ⚠️ Реверс приблизил `app-id` как «2» — **pcap дал точное `com.novotelecom.domophone`**;
  `Call-Id:%20…` — это URL-энкод «Call-Id: <id>» прямо в params (особенность Linphone).
- **`Supported: replaces, outbound, gruu, path`** — RFC 5626 outbound + GRUU.
- Digest **MD5 non-qop**; `User-Agent: Myhome/Myhome-android`.
- SIP-стек **Linphone 5.4.42** (реверс — research-spike.md §D4): голый `accept()`,
  авто-180 выключен, нет 183/session-timers/re-INVITE; только **UDP**, plain RTP
  (без SRTP/AVPF/ICE/STUN), видео off (видео — go2rtc).
- SIP-креды (login/password/realm) минтятся REST-ом оператора (`/sipdevices`).

## 5. Почему ранний вывод register-on-answer был ошибочным

Захват 2026-06-23 показывал отвеченный вызов, но не полностью отделял push-wake и
pre-answer фазу. Задержка до видимого `REGISTER` была ошибочно принята за
«раздумья до регистрации». Полный захват 2026-07-13 показывает, что приложение
регистрируется заранее и удерживает INVITE ответом `100 Trying`.

Эксперименты с поздним `200 OK` по-прежнему полезны: нельзя просто молчать после
INVITE или принимать его с большой задержкой без provisional response. Штатный
контракт — сразу `100 Trying`, затем `200 OK` только по действию пользователя.

**Эксперименты (probe):**
| Тест | Что | Итог |
|---|---|---|
| held + auto-answer (D2 media) | держим рег., отвечаем сразу | ✅ разговор, downlink 3086 |
| push-wake delay=2 | forked INVITE, 200 OK через 2с | ✅ разговор 59с |
| push-wake delay=5 | forked INVITE, 200 OK через 5с | ❌ BYE +5.1с, downlink 0 |
| + periodic 180 / re-register / 183 early-media | держать вызов | ❌ не помогло |
| MIRROR_APP (без STUN, Expires=30) | локальный SDP | сервер не рвёт (17с), но downlink 0 |
| **pcap приложения** | REGISTER→INVITE→100→200OK | ✅ **held, затем latching/разговор** |

Вывод: проблема прототипа была не в самом раннем `REGISTER`, а в неточном
воспроизведении held-диалога. Правильно — **REGISTER на ring → немедленный
`100 Trying` → `200 OK` при ответе**.

## 6. Правильная архитектура фичи (mirror приложения)

1. Не держим постоянную регистрацию вне активного окна звонка.
2. FCM `CALL_INCOMING` → `event`-сущность + mint → **`REGISTER`** (Expires=30,
   `Call-Id` из FCM, `Accept: application/sdp`) → `INVITE` → **`100 Trying`**.
3. По явному **«ответить»** (сервис/кнопка, в окне `CallInvalidated` ~30с):
   - принять уже держимый `INVITE` → **`200 OK` немедленно** (SDP: локальный
     адрес, G.711, `sendrecv`);
   - **сразу слать RTP uplink** (+ STUN-keepalive) → активировать latching → downlink;
   - `hangup` → `BYE`.
4. Кодек **G.711 PCMU/PCMA**, plain RTP/UDP, без STUN/SRTP. Latching обеспечивает
   downlink за NAT.
5. 🔴 **Привязка к `Call-ID`:** ответ строго привязан к `Call-ID` из FCM
   `CALL_INCOMING`; **не отвечать на завершённый/сброшенный вызов**. Иначе запоздалый
   `REGISTER` (от вызова, который не дождался ответа) поймает `INVITE` *следующего*
   вызова → ложный «ответ сразу» (баг рассинхрона — наблюдался в probe при сбросе
   до ответа). В интеграции: один активный «ответ»-флоу на `Call-ID`, отмена по
   `CallInvalidated`/`CALL_END`.

**✅ Подтверждено штатным приложением (2026-07-13):** три последовательных вызова
показали одинаковый pre-answer `REGISTER → INVITE → 100 Trying`; один завершён
серверным `CANCEL`, один отклонён клиентом, один принят `200 OK` с последующим RTP.

## 7. Артефакты

- `research/intercom-call-probe/probe_push_answer.py` — probe (push-wake, ANSWER, MIRROR_APP).
- `research/intercom-call-probe/analyze_pcap.py` — анализатор pcap (SIP-flow/SDP/RTP).
- pcap реального приложения — `captures/` (gitignored, секреты).
- Реверс APK — Linphone 5.4.42 (см. summary в истории сессии).

## 8. Метод захвата трафика приложения (reusable для будущего reverse)

SIP/RTP приложения идут по **UDP без шифрования** → перехватываются полностью.
1. **PCAPdroid** (Android, без root): Target app → «Мой Дом» (`ru.inetra.intercom`),
   dump mode → PCAP file. Start → звонок + ответ → Stop.
2. **adb pull**: `adb -s <serial> pull /storage/emulated/0/Download/PCAPdroid/<f>.pcap captures/`.
3. **Анализ**: `analyze_pcap.py` (dpkt, link-layer **DLT_RAW=101**) — SIP-flow + SDP +
   RTP-timing. Секреты (Digest `response`/`nonce`, `pn-tok`, login, IP) **маскировать**
   перед документированием.
- iOS-альтернатива: Mac + `rvictl -s <udid>` → virtual interface → tcpdump/Wireshark.
- pcap содержит SIP-пароль/токены → **gitignored** (`captures/`, `*.pcap`).

## Связь
- [research-spike.md](research-spike.md) — D1/D2/D3/D4 (реверс) развилки.
- [design.md](design.md) — целевая архитектура (§3.1, §6).
- [FINDINGS.md](../../../research/intercom-call-probe/FINDINGS.md) — канал вызова/медиа.
