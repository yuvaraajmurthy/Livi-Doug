import { Lightbulb } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, type StaffFilters } from "../../api/client";
import { signal } from "../../api/inspector";
import { ErrorState, Skeleton } from "../../ui/States";
import { CAMPUS_LABEL, HBar, NothingToShow, Panel, SuppressedRow, SuppressionNote, cap } from "./shared";

export function Gaps({ filters }: { filters: StaffFilters }) {
  const gaps = useQuery({ queryKey: ["staff", "gaps", filters], queryFn: () => api.staff.gaps(filters) });
  useEffect(() => {
    if (gaps.data) signal("staff:gaps", gaps.data);
  }, [gaps.data]);
  if (gaps.isError) return <ErrorState error={gaps.error} onRetry={() => gaps.refetch()} />;
  if (!gaps.data) return <Skeleton className="h-96" />;
  const rows = gaps.data.rows;
  const max = Math.max(1, ...rows.map(r => r.low_students_per_item));

  // The within-Camden story: Camden's thinnest area, compared with the same area in Newark.
  const camden = rows.filter(r => r.campus === "camden").sort((a, b) => b.low_students_per_item - a.low_students_per_item)[0];
  const newark = camden ? rows.find(r => r.campus === "newark" && r.dimension === camden.dimension) : undefined;
  const plusTwo = camden ? camden.low_students / (camden.items + 2) : null;

  return (
    <>
      <h1 tabIndex={-1} className="mb-6 text-[30px] font-semibold tracking-tight outline-none">
        Where supply is thin
      </h1>
      {camden ? (
        <div data-testid="gap-callout" data-tour="gap-callout" className="mb-8 rounded-[20px] bg-ink p-5 text-bg lg:p-6">
          <p className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.08em] opacity-80">
            <Lightbulb size={16} aria-hidden />
            Worth a look
          </p>
          <p className="mt-2 text-[22px] font-semibold leading-snug tracking-tight">
            Camden {camden.dimension}: {camden.low_students_per_item.toFixed(1)} students with low {camden.dimension} scores per
            resource.
            {newark ? ` Newark: ${newark.low_students_per_item.toFixed(1)}.` : ""}
          </p>
          <p className="mt-2 text-[15px] opacity-80">
            {camden.low_students} students, {camden.items} resources tagged {camden.dimension} on campus. Two more would make it
            about {plusTwo?.toFixed(1)} per resource (arithmetic, not a prediction).
          </p>
        </div>
      ) : null}
      <Panel title="Students with a low score, per matching resource" sub="Higher means fewer options per student who needs them.">
        {!rows.length && !gaps.data.suppressed_groups ? <NothingToShow min={gaps.data.min_group_size} /> : null}
        <ul className="flex flex-col gap-3">
          {rows.map(r => (
            <li key={`${r.campus}-${r.dimension}`} className="grid items-center gap-1 sm:grid-cols-[220px_1fr]">
              <span className="text-[14px]">
                <span className="font-medium">{CAMPUS_LABEL[r.campus] ?? r.campus}</span>{" "}
                <span className="text-ink-2">· {cap(r.dimension)}</span>
              </span>
              <HBar
                value={r.low_students_per_item}
                max={max}
                tone={r === camden ? "scarlet" : "ink"}
                label={r.low_students_per_item.toFixed(1)}
              />
            </li>
          ))}
          {Array.from({ length: gaps.data.suppressed_groups }).map((_, i) => (
            <li key={`s${i}`}>
              <SuppressedRow>hidden group</SuppressedRow>
            </li>
          ))}
        </ul>
        <SuppressionNote n={gaps.data.suppressed_groups} min={gaps.data.min_group_size} />
      </Panel>
    </>
  );
}
