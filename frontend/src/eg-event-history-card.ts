import { LitElement, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import "./components/eg-icon.js";
import { type Lang, langOf } from "./i18n.js";
import {
  fetchHistoryPage,
  filterHistoryEvents,
  formatHistoryTime,
  groupEventsByDay,
  historyPageRequests,
  historySources,
  historyStrings,
  mergeHistoryEvents,
  resolveHistoryConfig,
  type HistoryCardConfig,
  type HistoryEventRow,
  type HistoryFeedState,
  type HistorySource,
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
  @state() private _selectedSource = "";
  @state() private _loading = false;
  @state() private _loaded = false;
  @state() private _error = "";

  private _loadedEntitiesKey = "";
  private _feedStates = new Map<string, HistoryFeedState>();

  public setConfig(config: unknown): void {
    this._config = resolveHistoryConfig(config);
  }

  public getCardSize(): number {
    return 5;
  }

  public static getStubConfig(): HistoryCardConfig {
    return { entities: ["event.account_event_history"] };
  }

  protected override updated(changed: PropertyValues): void {
    if (!changed.has("hass") && !changed.has("_config")) return;
    const entities = this._config?.entities;
    const entitiesKey = entities?.join("\u0000") ?? "";
    if (!this.hass || !entities?.length || entitiesKey === this._loadedEntitiesKey) return;
    this._loadedEntitiesKey = entitiesKey;
    this._events = [];
    this._selectedSource = "";
    this._feedStates = new Map();
    this._loaded = false;
    void this._loadPages(true);
  }

  private get _lang(): Lang {
    return langOf(this.hass);
  }

  private get _allLast(): boolean {
    const entities = this._config?.entities ?? [];
    return entities.length > 0
      && entities.every((entity) => this._feedStates.get(entity)?.last === true);
  }

  private readonly _refresh = (): void => {
    if (!this._loading) void this._loadPages(true);
  };

  private readonly _more = (): void => {
    if (!this._loading && !this._allLast) void this._loadPages(false);
  };

  private async _loadPages(refresh: boolean): Promise<void> {
    const hass = this.hass;
    const entities = this._config?.entities;
    if (!hass || !entities?.length) return;
    const loadedKey = entities.join("\u0000");
    const requests = historyPageRequests(entities, this._feedStates, refresh);
    if (!requests.length) return;
    this._loading = true;
    this._error = "";
    try {
      const results = await Promise.allSettled(
        requests.map(({ entityId, page }) => fetchHistoryPage(hass, entityId, page)),
      );
      if (this._loadedEntitiesKey !== loadedKey) return;
      let incoming: HistoryEventRow[] = [];
      let failed = false;
      let succeeded = false;
      results.forEach((result, index) => {
        if (result.status === "rejected") {
          failed = true;
          return;
        }
        succeeded = true;
        incoming = mergeHistoryEvents(incoming, result.value.events);
        const entityId = requests[index]?.entityId;
        if (entityId) {
          this._feedStates.set(entityId, {
            page: result.value.page,
            last: result.value.last,
          });
        }
      });
      if (succeeded) {
        this._events = refresh
          ? mergeHistoryEvents([], incoming)
          : mergeHistoryEvents(this._events, incoming);
        const sources = historySources(this._events, entities.length > 1);
        if (
          this._selectedSource
          && !sources.some((source) => source.key === this._selectedSource)
        ) {
          this._selectedSource = "";
        }
      }
      if (failed) this._error = historyStrings(this._lang).unavailable;
      this._loaded = true;
    } catch {
      if (this._loadedEntitiesKey === loadedKey) {
        this._error = historyStrings(this._lang).unavailable;
      }
    } finally {
      if (this._loadedEntitiesKey === loadedKey) {
        this._loading = false;
        this._loaded = true;
      }
    }
  }

  protected override render(): TemplateResult {
    const strings = historyStrings(this._lang);
    const sources = historySources(
      this._events,
      (this._config?.entities.length ?? 0) > 1,
    );
    const visibleEvents = filterHistoryEvents(this._events, this._selectedSource);
    const groups = groupEventsByDay(visibleEvents, this._lang);
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
          ${sources.length > 1 ? this._renderFilters(sources, strings) : nothing}
          ${this._renderBody(groups, strings, sources)}
          ${this._loaded && this._error
            ? html`<p class="inline-error" role="alert">${this._error}</p>`
            : nothing}
          ${this._loaded && !this._allLast
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
    sources: HistorySource[],
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
    if (!groups.length) return html`<div class="state">${strings.empty}</div>`;
    return html`${groups.map((group) => html`
      <section aria-labelledby="day-${group.key}">
        <h3 id="day-${group.key}">${group.label}</h3>
        <ul class="events">
          ${group.events.map((event) => this._renderEvent(event, strings, sources))}
        </ul>
      </section>
    `)}`;
  }

  private _renderEvent(
    event: HistoryEventRow,
    strings: ReturnType<typeof historyStrings>,
    sources: HistorySource[],
  ): TemplateResult {
    const missed = event.event_type === "call_missed";
    const occurred = new Date(event.occurred_at * 1000);
    const source = sources.find((item) => item.key === event.source_key)?.label
      ?? event.source_name;
    return html`<li class="event ${missed ? "missed" : "accepted"}">
      <span class="event-icon"><eg-icon name=${missed ? "phone-off" : "phone"}></eg-icon></span>
      <span class="event-copy">
        <span class="event-title">${strings.event[event.event_type]}</span>
        ${source ? html`<span class="source">${source}</span>` : nothing}
      </span>
      <time datetime=${occurred.toISOString()}>${formatHistoryTime(event.occurred_at, this._lang)}</time>
    </li>`;
  }

  private _renderFilters(
    sources: HistorySource[],
    strings: ReturnType<typeof historyStrings>,
  ): TemplateResult {
    return html`<div class="filters" aria-label=${strings.devices}>
      <button
        class="chip ${this._selectedSource ? "" : "active"}"
        aria-pressed=${this._selectedSource ? "false" : "true"}
        @click=${() => { this._selectedSource = ""; }}
      >${strings.allDevices}</button>
      ${sources.map((source) => html`<button
        class="chip ${this._selectedSource === source.key ? "active" : ""}"
        aria-pressed=${this._selectedSource === source.key ? "true" : "false"}
        @click=${() => { this._selectedSource = source.key; }}
      >${source.label}</button>`)}
    </div>`;
  }

  static override styles = historyCardStyles;
}

declare global {
  interface HTMLElementTagNameMap {
    "eg-event-history-card": EgEventHistoryCard;
  }
}
