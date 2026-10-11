import { useQuery } from "@tanstack/react-query";
import { api, type StaffFilters } from "../../api/client";
import { pct } from "../../lib/format";
import { ErrorState, Skeleton } from "../../ui/States";
import { CAMPUS_LABEL, HBar, NothingToShow, Panel, SuppressedRow, SuppressionNote } from "./shared";

type Agg = { suggested: number; committed: number; attended: number; helped: number; students: number; with_friend: number };
const zero = (): Agg => ({ suggested: 0, committed: 0, attended: 0, helped: 0, students: 0, with_friend: 0 });

export function Overview({ filters }: { filters: StaffFilters }) {
  const funnel = useQuery({ queryKey: ["staff", "funnel", filters], queryFn: () => api.staff.funnel(filters) });
  const retakes = useQuery({ queryKey: ["staff", "retakes", filters], queryFn: () => api.staff.retakes(filters) });

  if (funnel.isError) return <ErrorState error={funnel.error} onRetry={() => funnel.refetch()} />;
  if (!funnel.data) return <Skeleton className="h-96" />;
  const f = funnel.data;

  const byCampus = new Map<string, Agg>();
  const total = zero();
  for (const r of f.rows) {
    const a = byCampus.get(r.campus) ?? zero();
    for (const k of ["suggested", "committed", "attended", "helped", "students", "with_friend"] as const) {
      a[k] += r[k];
      total[k] += r[k];
    }
    byCampus.set(r.campus, a);
  }
  const kpis = [
    { label: "Steps suggested", value: total.suggested.toLocaleString(), sub: `${total.students.toLocaleString()} student-areas` },
    { label: "Said “I’m in”", value: pct(total.committed / Math.max(1, total.suggested)), sub: `${total.committed.toLocaleString()} plans` },
    { label: "Went", value: pct(total.attended / Math.max(1, total.committed)), sub: `${total.with_friend} brought a friend` },
    { label: "Said it helped", value: pct(total.helped / Math.max(1, total.attended)), sub: "rated 4 or 5" },
  ];

  return (
    <>
      <h1 tabIndex={-1} className="mb-6 text-[30px] font-semibold tracking-tight outline-none">
        From suggestion to “it helped”
      </h1>
      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4" data-tour="staff-kpis">
        {kpis.map(k => (
          <div key={k.label} className="rounded-[20px] border border-line bg-surface p-4">
            <p className="text-[13px] font-medium text-ink-2">{k.label}</p>
            <p className="mt-1 text-[30px] font-semibold leading-none tracking-tight tabular">{k.value}</p>
            <p className="mt-1.5 text-[13px] text-ink-2">{k.sub}</p>
          </div>
        ))}
      </div>

      <Panel title="By campus" sub="Share of the previous step. Activity only; scores never leave the student.">
        {!f.rows.length && !f.suppressed_groups ? <NothingToShow min={f.min_group_size} /> : null}
        <div className="flex flex-col gap-6">
          {[...byCampus.entries()].map(([campus, a]) => (
            <div key={campus}>
              <p className="mb-2 text-[15px] font-semibold">{CAMPUS_LABEL[campus] ?? campus}</p>
              <div className="grid gap-1.5 text-[13px] text-ink-2 sm:grid-cols-[110px_1fr]">
                <span>Took a step</span>
                <HBar value={a.committed} max={a.suggested} label={pct(a.committed / Math.max(1, a.suggested))} />
                <span>Went</span>
                <HBar value={a.attended} max={a.committed} label={pct(a.attended / Math.max(1, a.committed))} />
                <span>Helped</span>
                <HBar value={a.helped} max={a.attended} tone="green" label={pct(a.helped / Math.max(1, a.attended))} />
              </div>
            </div>
          ))}
          {Array.from({ length: f.suppressed_groups }).map((_, i) => (
            <SuppressedRow key={i}>hidden group</SuppressedRow>
          ))}
        </div>
        <SuppressionNote n={f.suppressed_groups} min={f.min_group_size} />
      </Panel>

      {retakes.data ? (
        <Panel
          title="Do students come back to the inventory?"
          sub="Retake rate: students who used Compass vs. those who didn’t (synthetic semester, not a causal claim)."
        >
          <div className="flex flex-col gap-5">
            {retakes.data.rows.map(r => (
              <div key={r.campus}>
                <p className="mb-2 text-[15px] font-semibold">{CAMPUS_LABEL[r.campus] ?? r.campus}</p>
                <div className="grid gap-1.5 text-[13px] text-ink-2 sm:grid-cols-[110px_1fr]">
                  <span>Used Compass</span>
                  <HBar value={r.users_rate} max={1} tone="scarlet" label={pct(r.users_rate)} />
                  <span>Didn’t</span>
                  <HBar value={r.non_users_rate} max={1} label={pct(r.non_users_rate)} />
                </div>
              </div>
            ))}
          </div>
          <SuppressionNote n={retakes.data.suppressed_groups} min={retakes.data.min_group_size} />
        </Panel>
      ) : null}
    </>
  );
}
