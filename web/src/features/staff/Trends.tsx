import { TrendDown } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, DIMENSIONS, type StaffFilters } from "../../api/client";
import { shortDate } from "../../lib/format";
import { LineChart, type Series } from "../../ui/charts/LineChart";
import { ErrorState, Skeleton } from "../../ui/States";
import { CAMPUS_LABEL, Panel, SuppressionNote, cap } from "./shared";

export function Trends({ filters }: { filters: StaffFilters }) {
  const [dim, setDim] = useState<string>(filters.dimension ?? "emotional");
  const weekly = useQuery({ queryKey: ["staff", "weekly", filters], queryFn: () => api.staff.weekly(filters) });
  const dips = useQuery({ queryKey: ["staff", "dips", filters], queryFn: () => api.staff.dips(filters) });

  if (weekly.isError) return <ErrorState error={weekly.error} onRetry={() => weekly.refetch()} />;
  if (!weekly.data) return <Skeleton className="h-96" />;

  const pts = weekly.data.points.filter(p => p.dimension === dim);
  const campuses = Array.from(new Set(pts.map(p => p.campus)));
  const series: Series[] = campuses.map(c => ({
    key: c,
    label: CAMPUS_LABEL[c] ?? c,
    points: pts.filter(p => p.campus === c).map(p => ({ x: p.week, y: p.avg_score, n: p.n })),
  }));
  const bands = weekly.data.overlays.map(o => ({ from: o.start, to: o.end, label: o.label }));
  const myDips = (dips.data?.dips ?? []).filter(d => d.dimension === dim);
  const ys = pts.map(p => p.avg_score);
  const yMin = Math.floor((Math.min(...ys, 2.4) - 0.1) * 10) / 10;
  const yMax = Math.ceil((Math.max(...ys, 3) + 0.1) * 10) / 10;

  return (
    <>
      <h1 tabIndex={-1} className="mb-6 text-[30px] font-semibold tracking-tight outline-none">
        Trends
      </h1>
      <Panel
        title={`Weekly average: ${cap(dim)}`}
        sub="Average inventory score by week of take, groups of 10+ only."
        action={
          <select
            aria-label="Dimension to chart"
            value={dim}
            onChange={e => setDim(e.target.value)}
            className="h-10 rounded-xl border border-line-strong/60 bg-surface px-3 text-[14px] cursor-pointer"
          >
            {DIMENSIONS.map(d => (
              <option key={d} value={d}>
                {cap(d)}
              </option>
            ))}
          </select>
        }
      >
        <LineChart
          title={`Weekly average ${dim} score by campus`}
          series={series}
          bands={bands}
          yMin={yMin}
          yMax={yMax}
          xFormat={x => shortDate(x)}
          marks={myDips.map(d => ({ x: d.week, y: d.avg_score, label: `${d.campus} dip` }))}
        />
        <SuppressionNote n={weekly.data.suppressed_groups} min={weekly.data.min_group_size} />
      </Panel>

      <Panel title="Dips worth a look" sub={`Weeks where a group fell ${dips.data ? Math.round(dips.data.threshold * 100) / 100 : ""}+ below its trailing average.`}>
        {myDips.length ? (
          <ul className="flex flex-col gap-2">
            {myDips.map(d => (
              <li key={`${d.campus}-${d.week}`} className="flex items-start gap-3 rounded-xl bg-surface-2 px-4 py-3">
                <TrendDown size={20} className="mt-0.5 shrink-0 text-scarlet-ink" aria-hidden />
                <span className="text-[15px]">
                  <span className="font-semibold">
                    {CAMPUS_LABEL[d.campus]} · week of {shortDate(d.week)}
                  </span>
                  <span className="text-ink-2">
                    {" "}
                    · {d.avg_score.toFixed(2)} vs {d.trailing_avg.toFixed(2)} usual (−{d.drop.toFixed(2)}), n = {d.n}
                    {d.overlay ? ` · ${d.overlay}` : ""}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[15px] text-ink-2">No dips for {dim} with these filters.</p>
        )}
      </Panel>
    </>
  );
}
