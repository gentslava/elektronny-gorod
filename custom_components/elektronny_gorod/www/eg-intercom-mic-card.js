/**
 * eg-intercom-mic-card — кнопка «говорить» для домофона «Электронный город».
 *
 * Микрофон браузера (getUserMedia) → AudioWorklet (Float32→Int16 PCM) → бинарный
 * фрейм по АВТОРИЗОВАННОМУ HA-WebSocket (handler_id-префикс, как у голосового
 * ассистента HA) → WS-команда `elektronny_gorod/intercom_uplink` → UplinkSink →
 * SIP RTP-uplink в домофон (ADR-0013, механизм #1).
 *
 * Без go2rtc/TURN: едет по тому же WSS, что весь UI (работает удалённо/4G).
 * HTTPS-origin обязателен (браузер даёт микрофон только на secure origin).
 *
 * Установка: добавить как Lovelace-ресурс (JavaScript Module):
 *   /elektronny_gorod_static/eg-intercom-mic-card.js
 * Карта на дашборд: `type: custom:eg-intercom-mic-card`.
 */
class EgIntercomMicCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  getCardSize() {
    return 1;
  }

  _render() {
    if (this._rendered) return;
    this._rendered = true;
    this.innerHTML = `
      <ha-card header="${this._config.title || "Домофон — микрофон"}">
        <div class="eg-box">
          <button id="eg-mic" class="eg-btn">🎤 Говорить</button>
          <div id="eg-status" class="eg-status"></div>
        </div>
      </ha-card>
      <style>
        .eg-box { display:flex; flex-direction:column; gap:8px; padding:16px; align-items:center; }
        .eg-btn { font-size:1.2rem; padding:.7rem 1.4rem; border-radius:12px; border:none;
                  cursor:pointer; background:var(--primary-color); color:var(--text-primary-color); }
        .eg-btn.active { background:var(--error-color); }
        .eg-status { font-size:.85rem; color:var(--secondary-text-color); min-height:1.1em; }
      </style>`;
    this._btn = this.querySelector("#eg-mic");
    this._statusEl = this.querySelector("#eg-status");
    this._btn.addEventListener("click", () => this._toggle());
  }

  _status(text) {
    if (this._statusEl) this._statusEl.textContent = text;
  }

  async _toggle() {
    if (this._active) {
      this._stop();
    } else {
      await this._start();
    }
  }

  async _start() {
    if (!this._hass || !this._hass.connection) {
      this._status("нет связи с Home Assistant");
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this._status("микрофон недоступен (нужен HTTPS-origin)");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const ac = new (window.AudioContext || window.webkitAudioContext)();
      const sampleRate = ac.sampleRate; // обычно 48000; сервер ресемплит до 8к

      // Slot-leak guard (S-UP-02): каждый sendMessagePromise регистрирует на
      // сервере binary-handler, который живёт до закрытия вкладки. Раньше каждый
      // toggle ON слал новую команду → после ~255 toggle «Too many binary
      // handlers». Подписываемся ОДИН раз на вкладку и переиспользуем handler_id;
      // toggle OFF/ON останавливает/запускает только локальный захват.
      // Re-subscribe лишь если sample_rate сменился (редко — AC-rate стабилен).
      let sub = this._uplinkSub;
      if (!sub || sub.sampleRate !== sampleRate) {
        // WS-команда → регистрирует binary-handler на сервере, возвращает handler_id (1 байт).
        const res = await this._hass.connection.sendMessagePromise({
          type: "elektronny_gorod/intercom_uplink",
          sample_rate: sampleRate,
        });
        sub = { handlerId: res.handler_id, sampleRate };
        this._uplinkSub = sub;
      }
      const handlerId = sub.handlerId;
      const socket = this._hass.connection.socket;

      await ac.audioWorklet.addModule(this._workletUrl());
      const node = new AudioWorkletNode(ac, "eg-pcm-int16", { numberOfOutputs: 0 });
      node.port.onmessage = (e) => {
        // e.data — Int16Array PCM-кадр. Префиксуем handler_id и шлём по сокету.
        const i16 = e.data;
        const frame = new Uint8Array(1 + i16.byteLength);
        frame[0] = handlerId;
        frame.set(new Uint8Array(i16.buffer), 1);
        if (socket.readyState === 1) socket.send(frame);
      };
      const src = ac.createMediaStreamSource(stream);
      src.connect(node);

      this._ctx = { ac, stream, node, src };
      this._active = true;
      this._btn.classList.add("active");
      this._btn.textContent = "🔴 Остановить";
      this._status(`микрофон активен (${sampleRate} Гц → 8к G.711)`);
    } catch (err) {
      this._status("ошибка: " + (err && err.message ? err.message : err));
      this._stop();
    }
  }

  _stop() {
    const c = this._ctx;
    if (c) {
      try { c.node.port.onmessage = null; c.node.disconnect(); c.src.disconnect(); } catch (_) {}
      try { c.stream.getTracks().forEach((t) => t.stop()); } catch (_) {}
      try { c.ac.close(); } catch (_) {}
    }
    this._ctx = null;
    this._active = false;
    if (this._wUrl) {
      try { URL.revokeObjectURL(this._wUrl); } catch (_) {}
      this._wUrl = null; // следующий _start пересоздаст ворклет-URL
    }
    if (this._btn) {
      this._btn.classList.remove("active");
      this._btn.textContent = "🎤 Говорить";
    }
  }

  disconnectedCallback() {
    this._stop();
  }

  _workletUrl() {
    if (this._wUrl) return this._wUrl;
    const code = `
      class EgPcmInt16 extends AudioWorkletProcessor {
        process(inputs) {
          const ch = inputs[0] && inputs[0][0];
          if (ch && ch.length) {
            const i16 = new Int16Array(ch.length);
            for (let i = 0; i < ch.length; i++) {
              const s = Math.max(-1, Math.min(1, ch[i]));
              i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
            }
            this.port.postMessage(i16, [i16.buffer]);
          }
          return true;
        }
      }
      registerProcessor("eg-pcm-int16", EgPcmInt16);`;
    this._wUrl = URL.createObjectURL(new Blob([code], { type: "application/javascript" }));
    return this._wUrl;
  }
}

customElements.define("eg-intercom-mic-card", EgIntercomMicCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "eg-intercom-mic-card",
  name: "ЭГ Домофон — Микрофон",
  description: "Кнопка «говорить»: микрофон браузера → домофон (two-way audio uplink).",
});
