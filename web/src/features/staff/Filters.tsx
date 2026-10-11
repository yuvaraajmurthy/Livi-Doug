import { Funnel } from "@phosphor-icons/react";
import { DIMENSIONS, type StaffFilters } from "../../api/client";
import { signal } from "../../api/inspector";

const CAMPUSES = [
  ["new_brunswick", "New Brunswick"],
  ["newark", "Newark"],
  ["camden", "Camden"],
] as const;

const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

/** One narrow example filter that is very likely to produce hidden groups, for the "try to see a small group" demo. */
export const NARROW: StaffFilters = { campus: "camden", level: "grad", first_gen: true, housing: "resident" };

export function Filters({ value, onChange }: { value: StaffFilters; onChange: (f: StaffFilters) => void }) {
  const set = (k: keyof StaffFilters, v: string) =>
    onChange({ ...value, [k]: v === "" ? null : k === "first_gen" ? v === "true" : v });
  const sel =
    "h-11 rounded-xl border border-line-strong/60 bg-surface px-3 text-[15px] text-ink cursor-pointer min-w-0";
  const active = Object.values(value).some(v => v !== null && v !== undefined);
  return (
    <div className="mb-8 flex flex-wrap items-center gap-2" role="group" aria-label="Filters">
      <Funnel size={18} className="text-ink-2" aria-hidden />
      <select aria-label="Campus" className={sel} value={value.campus ?? ""} onChange={e => set("campus", e.target.value)}>
        <option value="">All campuses</option>
        {CAMPUSES.map(([k, l]) => (
          <option key={k} value={k}>
            {l}
          </option>
        ))}
      </select>
      <select aria-label="Dimension" className={sel} value={value.dimension ?? ""} onChange={e => set("dimension", e.target.value)}>
        <option value="">All dimensions</option>
        {DIMENSIONS.map(d => (
          <option key={d} value={d}>
            {cap(d)}
          </option>
        ))}
      </select>
      <select aria-label="Level" className={sel} value={value.level ?? ""} onChange={e => set("level", e.target.value)}>
        <option value="">All levels</option>
        <option value="undergrad">Undergrad</option>
        <option value="grad">Grad</option>
      </select>
      <select
        aria-label="First-generation"
        className={sel}
        value={value.first_gen === null || value.first_gen === undefined ? "" : String(value.first_gen)}
        onChange={e => set("first_gen", e.target.value)}
      >
        <option value="">First-gen: any</option>
        <option value="true">First-gen</option>
        <option value="false">Not first-gen</option>
      </select>
      <select aria-label="Housing" className={sel} value={value.housing ?? ""} onChange={e => set("housing", e.target.value)}>
        <option value="">Any housing</option>
        <option value="resident">Resident</option>
        <option value="commuter">Commuter</option>
      </select>
      {active ? (
        <button type="button" onClick={() => onChange({})} className="h-11 rounded-xl px-3 text-[14px] font-medium text-scarlet-ink hover:bg-scarlet-tint cursor-pointer">
          Clear
        </button>
      ) : (
        <button
          type="button"
          data-tour="staff-narrow"
          onClick={() => {
            onChange(NARROW);
            signal("staff:suppressed");
          }}
          className="h-11 rounded-xl px-3 text-[14px] font-medium text-ink-2 underline underline-offset-4 hover:text-ink cursor-pointer"
        >
          Try to see a small group
        </button>
      )}
    </div>
  );
}
