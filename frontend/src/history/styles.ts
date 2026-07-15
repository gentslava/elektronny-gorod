import { css, type CSSResult } from "lit";

import { egTokens } from "../theme/tokens.js";

export const historyCardStyles: CSSResult[] = [
  egTokens,
  css`
    :host {
      display: block;
      container-type: inline-size;
    }
    ha-card {
      overflow: hidden;
      color: var(--eg-text);
      background: var(--eg-card);
      border-radius: var(--eg-r-card);
    }
    header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 20px 20px 12px;
    }
    h2 {
      flex: 1;
      min-width: 0;
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      font-weight: 600;
    }
    button {
      min-height: 44px;
      border: 0;
      border-radius: var(--eg-r-full);
      color: var(--eg-text);
      background: transparent;
      font: inherit;
      cursor: pointer;
    }
    button:focus-visible {
      outline: 2px solid var(--eg-primary);
      outline-offset: 2px;
    }
    button:disabled {
      opacity: 0.55;
      cursor: default;
    }
    .refresh {
      display: inline-grid;
      width: 44px;
      place-items: center;
    }
    .refresh:hover,
    .refresh:active {
      background: var(--eg-elevated);
    }
    .refresh eg-icon {
      --eg-icon-size: 20px;
    }
    .content {
      padding: 0 16px 16px;
    }
    .filters {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 0 0 4px;
      scrollbar-width: thin;
    }
    .chip {
      min-height: 36px;
      padding: 0 14px;
      flex: none;
      color: var(--eg-text-2);
      background: var(--eg-elevated);
      font-size: 13px;
      font-weight: 600;
      white-space: nowrap;
    }
    .chip.active {
      color: var(--eg-primary);
      background: var(--eg-primary-bg);
    }
    section + section {
      margin-top: 20px;
    }
    h3 {
      margin: 14px 4px 8px;
      color: var(--eg-text-2);
      font-size: 14px;
      line-height: 1.4;
      font-weight: 600;
      text-transform: capitalize;
    }
    .events {
      overflow: hidden;
      margin: 0;
      padding: 0;
      border: 1px solid var(--eg-divider);
      border-radius: var(--eg-r-md);
      list-style: none;
    }
    .event {
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr) auto;
      align-items: center;
      gap: 12px;
      min-height: 72px;
      padding: 8px 12px;
      box-sizing: border-box;
    }
    .event + .event {
      border-top: 1px solid var(--eg-divider);
    }
    .event-icon {
      display: grid;
      width: 44px;
      height: 44px;
      place-items: center;
      border-radius: var(--eg-r-md);
      color: var(--eg-success);
      background: var(--eg-success-bg);
    }
    .event.missed .event-icon {
      color: var(--eg-error);
      background: var(--eg-error-bg);
    }
    .event-icon eg-icon {
      --eg-icon-size: 22px;
    }
    .event-copy {
      display: flex;
      min-width: 0;
      flex-direction: column;
      gap: 3px;
    }
    .event-title {
      overflow: hidden;
      font-size: 15px;
      line-height: 1.3;
      font-weight: 600;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .source {
      overflow: hidden;
      color: var(--eg-text-2);
      font-size: 13px;
      line-height: 1.3;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    time {
      color: var(--eg-text-2);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }
    .state {
      display: grid;
      min-height: 144px;
      padding: 20px;
      place-items: center;
      color: var(--eg-text-2);
      text-align: center;
    }
    .state.error {
      gap: 8px;
      color: var(--eg-error);
    }
    .retry,
    .more {
      padding: 0 18px;
      color: var(--eg-primary);
      background: var(--eg-primary-bg);
      font-weight: 600;
    }
    footer {
      display: flex;
      padding-top: 16px;
      justify-content: center;
    }
    .inline-error {
      margin: 12px 4px 0;
      color: var(--eg-error);
      font-size: 13px;
      text-align: center;
    }
    .spin {
      animation: spin 900ms linear infinite;
    }
    .skeleton {
      width: 100%;
    }
    .skeleton-line {
      height: 64px;
      border-radius: var(--eg-r-md);
      background: var(--eg-elevated);
      animation: pulse 1.4s ease-in-out infinite alternate;
    }
    .skeleton-line + .skeleton-line {
      margin-top: 8px;
    }
    @container (min-width: 640px) {
      .content {
        padding-right: 20px;
        padding-left: 20px;
      }
      .event {
        min-height: 76px;
        padding-right: 16px;
        padding-left: 16px;
      }
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes pulse {
      to { opacity: 0.55; }
    }
    @media (prefers-reduced-motion: reduce) {
      .spin,
      .skeleton-line { animation: none; }
    }
  `,
];
