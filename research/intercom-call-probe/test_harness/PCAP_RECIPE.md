# Рецепт домофона/оператора из app_call.pcap (для door-эмулятора)

## SIP-flow (успешный вызов)
REGISTER → 401(digest MD5, realm) → REGISTER(auth) → 200 OK → [held] → INVITE →
100 Trying(+44мс) → 200 OK+SDP(+88мс) → ACK(+180мс) → uplink RTP(+613мс от INVITE,
+433мс от ACK) → downlink RTP(+1661мс, ТОЛЬКО после первого uplink = latching) → BYE.

## SDP-offer домофона (в INVITE)
v=0
o=FreeSWITCH <ts> <ts> IN IP4 <DOOR_MEDIA_IP>
s=FreeSWITCH
c=IN IP4 <DOOR_MEDIA_IP>
t=0 0
m=audio <DOOR_RTP_PORT> RTP/AVP 0 8 101 13
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:101 telephone-event/8000
a=fmtp:101 0-15
a=rtpmap:13 CN/8000
a=ptime:20
(нет a=sendrecv; PT=0 PCMU реально используется)
From: <sip:000@<realm>>;tag=...  To: <sip:<login>@<realm>>
Record-Route: <sip:<proxy>;lr=on;ftag=...>  Contact: <sip:mod_sofia@<DOOR_MEDIA_IP>:11000;...>

## RTP / LATCHING (критично)
- downlink идёт ТОЛЬКО после первого uplink-пакета (FreeSWITCH защёлкивает src первого uplink как dst downlink).
- symmetric: uplink src-порт == порт в SDP-answer m=audio. downlink dst = этот же порт.
- PT=0 PCMU, 160 байт/пакет, ptime=20мс, seq с 0 у app-uplink.
- uplink стартует ПОСЛЕ ACK.

## Что даёт downlink=0 (детекторы бага)
- uplink src-порт ≠ SDP-answer порт (несимметрично) → strict FreeSWITCH не латчится.
- uplink на неверный dst (неверно распарсен SDP-offer door_ip:port) → не доходит → нет латчинга.
- нет 200 OK / нет echo Via+Record-Route / нет To-tag → ACK не приходит, сессии нет.
- ранний uplink до ACK → media-leg ещё не открыт (по pcap app ждёт ACK).
