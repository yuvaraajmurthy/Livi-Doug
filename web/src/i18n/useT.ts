import { useSyncExternalStore } from "react";
import { en, type Key } from "./en";
import { es } from "./es";

export type Lang = "en" | "es";
let lang: Lang = "en";
const listeners = new Set<() => void>();

export const language = {
  get: () => lang,
  set(l: Lang) {
    if (l === lang) return;
    lang = l;
    document.documentElement.lang = l;
    for (const fn of [...listeners]) fn();
  },
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};

export function translate(l: Lang, key: Key, vars?: Record<string, string | number>): string {
  let s = (l === "es" ? es : en)[key] ?? en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

export function useLang(): Lang {
  return useSyncExternalStore(language.subscribe, language.get, language.get);
}

export function useT() {
  const l = useLang();
  return (key: Key, vars?: Record<string, string | number>) => translate(l, key, vars);
}

export type { Key };
