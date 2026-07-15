import { LitElement, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import "./components/eg-icon.js";
import { type Lang, langOf } from "./i18n.js";
import {
  fetchHistoryPage,
  formatHistoryTime,
  groupEventsByDay,
  historyStrings,
  mergeHistoryEvents,
  resolveHistoryConfig,
  type HistoryCardConfig,
  type HistoryEventRow,
} from "./history/model.js";
import { historyCardStyles } from "./history/styles.js";

interface HassLike {
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
  callWS: (message: Record<string, unknown>) => Promise<unknown>;
  locale?: { language?: string };
  language?: string;
}

@customElement("eg-event-history-card")
export class EgEventHistoryCard extends LitElement {
  @property({ attribute: false }) public hass?: HassLike;

  @state() private _config?: HistoryCardConfig;
  @state() private _events: HistoryEventRow[] = [];
  @state() private _sourceName = "";
  @state() private _page = -1;
  @state() private _last = false;
  @state() private _loading = false;
  @state() private _loaded = false;
  @state() private _error = "";

  private _loadedEntity = "";

  public setConfig(config: unknown): void {
    this._config = resolveHistoryConfig(config);
  }

  public getCardSize(): number {
    return 5;
  }

  public static getStubConfig(): HistoryCardConfig {
    return { entity: "event.intercom_call_history" };
  }

  protected override updated(changed: PropertyValues): void {
    if (!changed.has("hass") && !changed.has("_config")) return;
    const entity = this._config?.entity;
    if (!this.hass || !entity || entity === this._loadedEntity) return;
    this._loadedEntity = entity;
    this._events = [];
    this._page = -1;
    this._last = false;
    this._loaded = false;
    void this._loadPage(0, true);
  }

  private get _lang(): Lang {
    return langOf(this.hass);
  }

  private get _displaySource(): string {
    if (this._sourceName) return this._sourceName;
    const value = this._config
      ? this.hass?.states[this._config.entity]?.attributes["friendly_name"]
      : undefined;
    return typeof value === "string" ? value : "";
  }

  private readonly _refresh = (): void => {
    if (!this._loading) void this._loadPage(0, true);
  };

  private readonly _more = (): void => {
    if (!this._loading && !this._last) void this._loadPage(this._page + 1, false);
  };

  private async _loadPage(pageNumber: number, replace: boolean): Promise<void> {
    const hass = this.hass;
    const entity = this._config?.entity;
    if (!hass || !entity) return;
    this._loading = true;
    this._error = "";
    try {
      const page = await fetchHistoryPage(hass, entity, pageNumber);
      if (this._loadedEntity !== entity || page.entity_id !== entity) return;
      this._events = replace
        ? mergeHistoryEvents([], page.events)
        : mergeHistoryEvents(this._events, page.events);
      this._sourceName = page.source_name;
      this._page = page.page;
      this._last = page.last;
      this._loaded = true;
    } catch {
      if (this._loadedEntity === entity) this._error = historyStrings(this._lang).unavailable;
    } finally {
      if (this._loadedEntity === entity) {
        this._loading = false;
        this._loaded = true;
      }
    }
  }

  protected override render(): TemplateResult {
    const strings = historyStrings(this._lang);
    const groups = groupEventsByDay(this._events, this._lang);
    return html`
      <ha-card>
        <header>
          <h2>${this._config?.title ?? strings.title}</h2>
          <button
            class="refresh"
            aria-label=${strings.refresh}
            title=${strings.refresh}
            ?disabled=${this._loading}
            @click=${this._refresh}
          ><eg-icon class=${this._loading ? "spin" : ""} name="refresh-cw"></eg-icon></button>
        </header>
        <div class="content" aria-live="polite">
          ${this._renderBody(groups, strings)}
          ${this._events.length && this._error
            ? html`<p class="inline-error" role="alert">${this._error}</p>`
            : nothing}
          ${this._events.length && !this._last
            ? html`<footer><button class="more" ?disabled=${this._loading} @click=${this._more}>
                ${this._loading ? strings.loading : strings.more}
              </button></footer>`
            : nothing}
        </div>
      </ha-card>
    `;
  }

  private _renderBody(
    groups: ReturnType<typeof groupEventsByDay>,
    strings: ReturnType<typeof historyStrings>,
  ): TemplateResult {
    if (!this._loaded && this._loading) {
      return html`<div class="state" role="status" aria-label=${strings.loading}>
        <div class="skeleton"><div class="skeleton-line"></div><div class="skeleton-line"></div></div>
      </div>`;
    }
    if (!this._events.length && this._error) {
      return html`<div class="state error" role="alert">
        <span>${this._error}</span>
        <button class="retry" @click=${this._refresh}>${strings.retry}</button>
      </div>`;
    }
    if (!this._events.length) return html`<div class="state">${strings.empty}</div>`;
    return html`${groups.map((group) => html`
      <section aria-labelledby="day-${group.key}">
        <h3 id="day-${group.key}">${group.label}</h3>
        <ul class="events">
          ${group.events.map((event) => this._renderEvent(event, strings))}
        </ul>
      </section>
    `)}`;
  }

  private _renderEvent(
    event: HistoryEventRow,
    strings: ReturnType<typeof historyStrings>,
  ): TemplateResult {
    const missed = event.event_type === "call_missed";
    const occurred = new Date(event.occurred_at * 1000);
    return html`<li class="event ${missed ? "missed" : "accepted"}">
      <span class="event-icon"><eg-icon name=${missed ? "phone-off" : "phone"}></eg-icon></span>
      <span class="event-copy">
        <span class="event-title">${strings.event[event.event_type]}</span>
        ${this._displaySource ? html`<span class="source">${this._displaySource}</span>` : nothing}
      </span>
      <time datetime=${occurred.toISOString()}>${formatHistoryTime(event.occurred_at, this._lang)}</time>
    </li>`;
  }

  static override styles = historyCardStyles;
}

declare global {
  interface HTMLElementTagNameMap {
    "eg-event-history-card": EgEventHistoryCard;
  }
}
