// Микрофон вызова: getUserMedia → AudioWorklet (Float32→Int16 PCM) → бинарный фрейм
// по авторизованному HA-WebSocket (handler_id-префикс) → WS-команда
// `elektronny_gorod/intercom_uplink` → SIP RTP-uplink в домофон (ADR-0013, #1).
// Порт проверенной логики из www/eg-intercom-mic-card.js (slot-leak guard сохранён).
// Чистая логика gate-решения вынесена в shouldAutoStartMic (юнит-тест).

export type MicPermission = "granted" | "denied" | "prompt" | "unknown";

/**
 * Авто-захват микрофона при `active` допустим ТОЛЬКО если разрешение уже выдано
 * и origin secure (иначе нужен явный тап — getUserMedia спросит разрешение).
 */
export function shouldAutoStartMic(perm: MicPermission, secure: boolean): boolean {
  return secure && perm === "granted";
}

interface HaConn {
  socket: WebSocket;
  sendMessagePromise: (msg: Record<string, unknown>) => Promise<unknown>;
}

interface AudioCtxRefs {
  ac: AudioContext;
  stream: MediaStream;
  node: AudioWorkletNode;
  src: MediaStreamAudioSourceNode;
}

/** Управляет захватом микрофона и его отправкой в HA. Без Lit — реюзабельно/тестируемо. */
export class MicController {
  public active = false;
  public lastError = "";

  private _ctx?: AudioCtxRefs;
  // Slot-leak guard (S-UP-02): один binary-handler на вкладку, переиспользуем
  // handler_id; toggle ON/OFF останавливает/запускает только локальный захват.
  private _sub?: { handlerId: number; sampleRate: number };
  private _wUrl?: string;

  constructor(
    private readonly _getConn: () => HaConn | undefined,
    private readonly _onChange: () => void = () => {},
  ) {}

  public async queryPermission(): Promise<MicPermission> {
    try {
      const perms = (navigator as Navigator & {
        permissions?: { query: (d: { name: PermissionName }) => Promise<PermissionStatus> };
      }).permissions;
      const status = await perms?.query({ name: "microphone" as PermissionName });
      return (status?.state as MicPermission) ?? "unknown";
    } catch {
      return "unknown";
    }
  }

  public get secure(): boolean {
    return typeof window !== "undefined" && window.isSecureContext === true;
  }

  public async start(): Promise<void> {
    if (this.active) return;
    const conn = this._getConn();
    if (!conn) {
      this._fail("нет связи с Home Assistant");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      this._fail("микрофон недоступен (нужен HTTPS-origin)");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ac = new Ctor();
      const sampleRate = ac.sampleRate;

      let sub = this._sub;
      if (!sub || sub.sampleRate !== sampleRate) {
        const res = (await conn.sendMessagePromise({
          type: "elektronny_gorod/intercom_uplink",
          sample_rate: sampleRate,
        })) as { handler_id: number };
        sub = { handlerId: res.handler_id, sampleRate };
        this._sub = sub;
      }
      const handlerId = sub.handlerId;
      const socket = conn.socket;

      await ac.audioWorklet.addModule(this._workletUrl());
      const node = new AudioWorkletNode(ac, "eg-pcm-int16", { numberOfOutputs: 0 });
      node.port.onmessage = (e: MessageEvent<Int16Array>) => {
        const i16 = e.data;
        const frame = new Uint8Array(1 + i16.byteLength);
        frame[0] = handlerId;
        frame.set(new Uint8Array(i16.buffer), 1);
        if (socket.readyState === 1) socket.send(frame);
      };
      const src = ac.createMediaStreamSource(stream);
      src.connect(node);

      this._ctx = { ac, stream, node, src };
      this.active = true;
      this.lastError = "";
      this._onChange();
    } catch (err) {
      this._fail(err instanceof Error ? err.message : String(err));
    }
  }

  public stop(): void {
    const c = this._ctx;
    if (c) {
      try {
        c.node.port.onmessage = null;
        c.node.disconnect();
        c.src.disconnect();
      } catch {
        /* ignore */
      }
      try {
        c.stream.getTracks().forEach((t) => t.stop());
      } catch {
        /* ignore */
      }
      try {
        void c.ac.close();
      } catch {
        /* ignore */
      }
    }
    this._ctx = undefined;
    this.active = false;
    if (this._wUrl) {
      try {
        URL.revokeObjectURL(this._wUrl);
      } catch {
        /* ignore */
      }
      this._wUrl = undefined;
    }
    this._onChange();
  }

  private _fail(msg: string): void {
    this.lastError = msg;
    this.stop();
  }

  private _workletUrl(): string {
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
