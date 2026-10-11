import { it, expect } from "vitest";
import { en } from "../../src/i18n/en";
import { es } from "../../src/i18n/es";
import { translate } from "../../src/i18n/useT";

it("every English key has a Spanish string", () => {
  const missing = Object.keys(en).filter(k => !(es as Record<string, string>)[k]);
  expect(missing).toEqual([]);
});

it("Spanish strings keep the same placeholders", () => {
  const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");
  const diff = Object.entries(en).filter(([k, v]) => ph(v) !== ph((es as Record<string, string>)[k]));
  expect(diff.map(([k]) => k)).toEqual([]);
});

it("interpolates variables", () => {
  expect(translate("en", "plan.remind", { time: "12:15 PM" })).toBe("We'll remind you at 12:15 PM.");
  expect(translate("es", "focus.step", { n: 2 })).toBe("Paso 2 de 3");
});
