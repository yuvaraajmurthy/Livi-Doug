// Performs story actions on the real UI: finds [data-tour] elements, shows a tap ripple, clicks, types, moves time.
// Used by "Do it for me" in table tours and by the stage presenter (inside the iframe).
import { api } from "../api/client";
import { dataMode } from "../session/mode";
import { startSession } from "../session/start";
import { jumpTime, skipTime } from "../features/time/TimeSheet";
import type { Action } from "./types";

let navigateFn: ((to: string) => void) | null = null;
export function setNavigator(fn: (to: string) => void) {
  navigateFn = fn;
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));
const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export async function findTarget(id: string, timeout = 8000): Promise<HTMLElement> {
  const t0 = performance.now();
  for (;;) {
    const all = Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${CSS.escape(id)}"]`));
    const el = all.find(e => e.getClientRects().length > 0);
    if (el) return el;
    if (performance.now() - t0 > timeout) throw new Error(`Can't find "${id}" on this screen`);
    await sleep(100);
  }
}

function clickable(el: HTMLElement): HTMLElement {
  if (el.matches("button, a, input, textarea, select, [role=button], [role=radio]")) return el;
  return el.querySelector<HTMLElement>("button, a") ?? el;
}

function ripple(el: HTMLElement) {
  if (reduced()) return;
  const r = el.getBoundingClientRect();
  const dot = document.createElement("span");
  dot.setAttribute("aria-hidden", "true");
  Object.assign(dot.style, {
    position: "fixed",
    left: `${r.left + r.width / 2 - 22}px`,
    top: `${r.top + r.height / 2 - 22}px`,
    width: "44px",
    height: "44px",
    borderRadius: "999px",
    background: "rgba(204,0,51,0.28)",
    border: "2px solid rgba(204,0,51,0.7)",
    zIndex: "9999",
    pointerEvents: "none",
    transform: "scale(0.4)",
    opacity: "1",
    transition: "transform 380ms cubic-bezier(.22,1,.36,1), opacity 420ms ease-out",
  } as CSSStyleDeclaration);
  document.body.appendChild(dot);
  requestAnimationFrame(() => {
    dot.style.transform = "scale(1.4)";
    dot.style.opacity = "0";
  });
  setTimeout(() => dot.remove(), 520);
}

async function typeInto(el: HTMLElement, text: string) {
  const input = el as HTMLInputElement | HTMLTextAreaElement;
  input.focus();
  const proto = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")!.set!;
  const delay = reduced() ? 0 : 32;
  for (let i = 1; i <= text.length; i++) {
    setter.call(input, text.slice(0, i));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    if (delay) await sleep(delay);
  }
}

export async function perform(actions: Action[], opts: { stage?: boolean } = {}) {
  for (const a of actions) {
    switch (a.kind) {
      case "tap": {
        const el = clickable(await findTarget(a.target));
        el.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
        await sleep(reduced() ? 0 : 260);
        ripple(el);
        await sleep(reduced() ? 0 : 120);
        el.click();
        break;
      }
      case "type": {
        const el = await findTarget(a.target);
        el.scrollIntoView({ block: "center" });
        await typeInto(el, a.text);
        if (a.submit) clickable(await findTarget(a.submit)).click();
        break;
      }
      case "key":
        document.dispatchEvent(new KeyboardEvent("keydown", { key: a.key, bubbles: true }));
        break;
      case "wait":
        await sleep(reduced() ? 0 : a.ms);
        break;
      case "navigate":
        navigateFn?.(a.to);
        break;
      case "session": {
        const to = await startSession(a.persona, { sandbox: a.sandbox, stage: opts.stage });
        navigateFn?.(to);
        break;
      }
      case "skip":
        await skipTime(a.to);
        break;
      case "clock":
        await jumpTime(a.now);
        break;
      case "replay": {
        const m = await import("./replay/enable");
        if (a.on) await m.enableReplay();
        else m.disableReplay();
        break;
      }
      case "templates":
        await api.forceTemplates(a.on);
        dataMode.setTemplates(a.on);
        break;
    }
  }
}
