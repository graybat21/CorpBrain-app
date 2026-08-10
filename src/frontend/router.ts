/**
 * Hash routing for the shipped shell (DEC-01, issue #14).
 *
 * DEC-01 fixes client routing to a **hash router** — the SPA is a prebuilt static bundle loaded
 * inside pywebview/WebView2, and any path-based router needs a server willing to rewrite unknown
 * paths back to index.html. `#/dashboard` needs nothing from anyone.
 *
 * Written by hand rather than with `react-router-dom`. CLAUDE.md §4 limits dependencies to a
 * pre-approved list and react-router is not on it; what this file replaces is one `hashchange`
 * listener and a string split, which is not worth a dependency, a bundle-size increase, and a
 * PyInstaller-visible transitive tree.
 *
 * The route is the source of truth for which tab is showing. That matters beyond tidiness: the
 * shell opens the window at `#/dashboard` (see `src/main.py`), so if the hash were merely a
 * mirror of Zustand state the initial route would be decorative and the shell's choice of entry
 * screen would have no effect.
 */

import type { ActiveTab } from './store/appStore';

/** Tabs addressable as `#/<tab>`. Kept in this order for the fallback below. */
export const ROUTE_TABS: ActiveTab[] = ['dashboard', 'files', 'wiki', 'rename', 'analytics', 'settings'];

/** Where an empty, unknown, or malformed hash lands. */
export const DEFAULT_TAB: ActiveTab = 'dashboard';

/** A parsed location: which tab to render, plus a workspace to select if the route named one. */
export interface RouteState {
  tab: ActiveTab;
  workspaceId: string | null;
}

/**
 * Parse `window.location.hash` into a route.
 *
 * Accepts `#/dashboard`, `#dashboard`, and `#/workspace/<id>`. The workspace form resolves to the
 * dashboard tab: it addresses *which workspace* is open, not a seventh screen, and the issue's
 * task breakdown lists it alongside `#/dashboard` for exactly that reason.
 *
 * Unknown routes fall back rather than throwing. A hash is user-editable text in a WebView's
 * address state; a typo must not blank the app.
 */
export function parseHash(hash: string): RouteState {
  const raw = hash.replace(/^#/, '').replace(/^\//, '');
  const [head, ...rest] = raw.split('/').filter((segment) => segment.length > 0);

  if (!head) {
    return { tab: DEFAULT_TAB, workspaceId: null };
  }

  if (head === 'workspace') {
    const workspaceId = rest[0] ?? null;
    return { tab: DEFAULT_TAB, workspaceId };
  }

  const tab = ROUTE_TABS.find((candidate) => candidate === head);
  return { tab: tab ?? DEFAULT_TAB, workspaceId: null };
}

/** The canonical hash for a tab, so callers never assemble the string themselves. */
export function hashForTab(tab: ActiveTab): string {
  return `#/${tab}`;
}

/**
 * Navigate by writing the hash.
 *
 * Assigning to `location.hash` fires `hashchange`, which is what drives the render — so this
 * function does not also set store state. One direction of data flow: hash → store → render.
 */
export function navigateToTab(tab: ActiveTab): void {
  const next = hashForTab(tab);
  if (window.location.hash !== next) {
    window.location.hash = next;
  }
}

/**
 * Subscribe to hash changes, and report the current one immediately.
 *
 * The immediate call is what applies the shell's initial `#/dashboard` (and any deep link the
 * user typed) — `hashchange` does not fire for the page's first load. Returns an unsubscribe
 * function for React's effect cleanup.
 */
export function subscribeToRoute(onRoute: (route: RouteState) => void): () => void {
  const handler = () => onRoute(parseHash(window.location.hash));
  handler();
  window.addEventListener('hashchange', handler);
  return () => window.removeEventListener('hashchange', handler);
}
