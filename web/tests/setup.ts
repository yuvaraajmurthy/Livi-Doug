import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "msw/node";
import { cleanup } from "@testing-library/react";
import { transferableAbortController } from "node:util";

export const server = setupServer();

// jsdom has no layout: give scroll APIs harmless no-ops
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

// Node's fetch (undici) only accepts its own AbortSignal, but jsdom swaps in its own global, so a request with a
// signal fails inside msw on newer Node. Hand fetch a native signal that follows the jsdom one.
const NativeAbortController = transferableAbortController().constructor as typeof AbortController;
function nativeSignal(s: AbortSignal): AbortSignal {
  const c = new NativeAbortController();
  if (s.aborted) c.abort(s.reason);
  else s.addEventListener("abort", () => c.abort(s.reason), { once: true });
  return c.signal;
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  const mswFetch = globalThis.fetch;
  globalThis.fetch = (input, init) => mswFetch(input, init?.signal ? { ...init, signal: nativeSignal(init.signal) } : init);
});
afterEach(() => { server.resetHandlers(); cleanup(); });
afterAll(() => server.close());
