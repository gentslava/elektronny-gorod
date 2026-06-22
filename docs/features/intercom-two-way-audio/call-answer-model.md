# Модель приёма вызова домофона (pcap-доказано 2026-06-23)

> Полная картина «как приложение принимает вызов и поднимает двусторонний звук».
> Доказано **захватом трафика реального приложения** (PCAPdroid, телефон) + реверсом
> APK + 6 live-экспериментами с probe. PII/реальные IP — плейсхолдеры.

## 1. Главный вывод (модель приложения)

**`INVITE` приходит к устройству ТОЛЬКО после `REGISTER`, который приложение шлёт в
момент нажатия «ответить». Вызов НЕ форкается на устройство при звонке.**

Полный флоу:
```
1. Звонок с панели → FCM CALL_INCOMING (push, НЕ SIP) на все устройства аккаунта.
   Окно вызова — 30с (CallInvalidated): домофон сам сбрасывает на 30-й секунде.
2. Пользователь видит вызов, открывает приложение, смотрит ВИДЕО (go2rtc/RTSP —
   отдельный TCP-поток, «подгрузка видео»), думает (до 30с).
3. Жмёт «ОТВЕТИТЬ» → приложение шлёт свежий REGISTER к realm оператора.
4. Сервер НЕМЕДЛЕННО (≈90мс) шлёт INVITE на эту регистрацию.
5. Приложение отвечает 200 OK МГНОВЕННО (≈80мс) → ACK → RTP (latching) → разговор.
6. Завершение — BYE (любая сторона). После — REGISTER refresh.
```

🔑 **«Раздумья» происходят ДО `REGISTER`, а связка `REGISTER → INVITE → 200 OK`
всегда мгновенная (миллисекунды).** Любое время раздумий (1с…30с) допустимо.

## 2. Тайминги из pcap (реальный вызов, ответ на ~28-й секунде)

```
[+28.23s] TEL → SRV   REGISTER sip:{ac_id}.intercom.{operator}.ru   ← триггер
[+28.32s] SRV → TEL   INVITE  (+ 200 OK на REGISTER)               ← +90 мс
[+28.40s] TEL → SRV   200 OK  (SDP-answer)                          ← +80 мс (мгновенно)
[+28.41s] TEL → SRV   RTP + STUN-keepalive (bin 20B) на media-порты ← latching
[+28.50s] SRV → TEL   ACK
[+28.93s] TEL → SRV   RTP G.711 PCMU (uplink, ~445 пакетов)
[+29.98s] SRV → TEL   RTP G.711 PCMU (downlink, ~430 пакетов)      ← latching сработал
[+38.50s] TEL → SRV   BYE (через ~10с разговора)
[+38.75s] TEL → SRV   REGISTER refresh
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

## 5. Почему наш прототип рвался (наша ошибка)

Мы **держали SIP-регистрацию заранее** (held / push-binding) → сервер форкал `INVITE`
на неё **сразу при звонке** → мы ждали N секунд до `200 OK` → сервер ждёт **мгновенный**
ответ на этот forked INVITE и при позднем ответе **сносит media-leg** (`BYE` сразу
после `ACK`, downlink 0).

**Эксперименты (probe):**
| Тест | Что | Итог |
|---|---|---|
| held + auto-answer (D2 media) | держим рег., отвечаем сразу | ✅ разговор, downlink 3086 |
| push-wake delay=2 | forked INVITE, 200 OK через 2с | ✅ разговор 59с |
| push-wake delay=5 | forked INVITE, 200 OK через 5с | ❌ BYE +5.1с, downlink 0 |
| + periodic 180 / re-register / 183 early-media | держать вызов | ❌ не помогло |
| MIRROR_APP (без STUN, Expires=30) | локальный SDP | сервер не рвёт (17с), но downlink 0 |
| **pcap приложения** | REGISTER→INVITE→200OK | ✅ **мгновенно, latching, разговор** |

Вывод: дело **не в сигнализации и не в таймере панели**, а в том, что мы получали
INVITE рано (forking) и отвечали поздно. Правильно — **REGISTER в момент ответа**.

## 6. Правильная архитектура фичи (mirror приложения)

1. **НЕ держим** постоянную SIP-регистрацию для приёма вызова.
2. FCM `CALL_INCOMING` → `event`-сущность (показать вызов; видео — go2rtc; окно 30с).
3. По явному **«ответить»** (сервис/кнопка, в окне `CallInvalidated` ~30с):
   - mint SIP-креды (если нужно) → **`REGISTER`** (Expires=30, проприет. push-params);
   - принять пришедший `INVITE` → **`200 OK` немедленно** (SDP: локальный адрес,
     G.711, `sendrecv`);
   - **сразу слать RTP uplink** (+ STUN-keepalive) → активировать latching → downlink;
   - `hangup` → `BYE`.
4. Кодек **G.711 PCMU/PCMA**, plain RTP/UDP, без STUN/SRTP. Latching обеспечивает
   downlink за NAT.

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
