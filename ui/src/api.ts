// Centralized API client.
//
// Every request carries the active FalkorDB graph as the `x-graph-name` header so
// the backend routes it to the right graph. This replaces an earlier global
// `window.fetch` monkey-patch — keeping the behavior explicit, testable, and the
// single place that knows about the graph header.

export const DEFAULT_GRAPH = "data_oop";
const GRAPH_STORAGE_KEY = "selected_graph";

/** localStorage is missing in some test/SSR environments — access it defensively. */
function safeStorage(): Storage | null {
  try {
    return typeof localStorage !== "undefined" ? localStorage : null;
  } catch {
    return null;
  }
}

let activeGraph = safeStorage()?.getItem(GRAPH_STORAGE_KEY) || DEFAULT_GRAPH;

/** The graph all API requests currently target. */
export function getActiveGraph(): string {
  return activeGraph;
}

/** Switch the graph all subsequent API requests target (persisted to localStorage). */
export function setActiveGraph(name: string): void {
  activeGraph = name;
  safeStorage()?.setItem(GRAPH_STORAGE_KEY, name);
}

/** `fetch` wrapper that injects the `x-graph-name` header unless already set. */
export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (!headers.has("x-graph-name")) {
    headers.set("x-graph-name", activeGraph);
  }
  return fetch(path, { ...init, headers });
}
