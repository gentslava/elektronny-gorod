// Заглушки HA-элементов для работы реальной карточки вне Home Assistant.
// Повторяет паттерн frontend/demo/index.html из репозитория интеграции:
// в реальном HA эти элементы даёт фронтенд Home Assistant.

const GUEST_IMG = `${import.meta.env.BASE_URL}assets/guest.jpg`;

let registered = false;

/** Зарегистрировать заглушки. Вызывать ДО импорта бандла карточки. */
export function registerHaStubs(): void {
  if (registered) return;
  registered = true;

  // Микрофон в симуляции не используется: отвечаем «granted» на запрос
  // статуса разрешения, чтобы карточка не показывала permission-баннеры.
  // Реальный getUserMedia никогда не вызывается (см. DemoHost.quiet).
  const perms = navigator.permissions;
  const origQuery = perms?.query?.bind(perms);
  if (perms && origQuery) {
    (perms as { query: unknown }).query = async (desc: { name?: string }) => {
      if (desc?.name === "microphone") {
        return {
          state: "granted",
          onchange: null,
          addEventListener() {},
          removeEventListener() {},
        } as unknown as PermissionStatus;
      }
      return origQuery(desc as PermissionDescriptor);
    };
  }

  class HaCard extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const s = this.attachShadow({ mode: "open" });
      s.innerHTML = "<style>:host{display:block}</style><slot></slot>";
    }
  }
  if (!customElements.get("ha-card")) customElements.define("ha-card", HaCard);

  class HaCameraStream extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const s = this.attachShadow({ mode: "open" });
      s.innerHTML =
        "<style>:host{display:block;width:100%;height:100%}" +
        "img{width:100%;height:100%;object-fit:cover;display:block}</style>" +
        `<img src="${GUEST_IMG}" alt="" />`;
    }
  }
  if (!customElements.get("ha-camera-stream")) {
    customElements.define("ha-camera-stream", HaCameraStream);
  }
}

/** Импорт production-бандла карточки (после регистрации заглушек). */
export async function loadCardBundle(): Promise<void> {
  registerHaStubs();
  await import("@card-bundle");
}
