import { useId } from "react";

export type Series = { key: string; label: string; points: { x: string; y: number; n?: number }[] };
export type Band = { from: string; to: string; label: string };

const DASH = ["", "6 4", "2 4"];

/** Small accessible line chart: direct labels, distinct dash per series, labelled shaded bands, table fallback. */
export function LineChart({
  title,
  series,
  bands = [],
  yMin,
  yMax,
  format = (y: number) => y.toFixed(2),
  xFormat = (x: string) => x,
  marks = [],
}: {
  title: string;
  series: Series[];
  bands?: Band[];
  yMin: number;
  yMax: number;
  format?: (y: number) => string;
  xFormat?: (x: string) => string;
  marks?: { x: string; y: number; label: string }[];
}) {
  const id = useId();
  const xs = Array.from(new Set(series.flatMap(s => s.points.map(p => p.x)))).sort();
  const W = 640;
  const H = 240;
  const P = { l: 40, r: 96, t: 16, b: 28 };
  const xi = (x: string) => P.l + (xs.indexOf(x) / Math.max(1, xs.length - 1)) * (W - P.l - P.r);
  const yi = (y: number) => P.t + (1 - (y - yMin) / (yMax - yMin)) * (H - P.t - P.b);
  const ticks = [yMin, (yMin + yMax) / 2, yMax];
  // end labels: push apart so they never overlap (min 16px)
  const ends = series
    .map(s => ({ key: s.key, y: s.points.length ? yi(s.points[s.points.length - 1].y) : 0 }))
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 16) ends[i].y = ends[i - 1].y + 16;
  const labelY = Object.fromEntries(ends.map(e => [e.key, e.y]));
  return (
    <figure aria-labelledby={id} className="m-0">
      <figcaption id={id} className="sr-only">
        {title}
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={title}>
        {bands.map(b => {
          const a = xs.findIndex(x => x >= b.from);
          const z = xs.findLastIndex(x => x <= b.to);
          if (a < 0 || z < a) return null;
          const x1 = xi(xs[a]) - 8;
          const x2 = xi(xs[z]) + 8;
          return (
            <g key={b.label}>
              <rect x={x1} y={P.t} width={x2 - x1} height={H - P.t - P.b} fill="var(--amber-tint)" />
              <text x={x1 + 4} y={P.t + 12} fontSize="11" fill="var(--amber)">
                {b.label}
              </text>
            </g>
          );
        })}
        {ticks.map(t => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={yi(t)} y2={yi(t)} stroke="var(--line)" />
            <text x={P.l - 6} y={yi(t) + 4} fontSize="11" textAnchor="end" fill="var(--ink-2)" className="tabular">
              {format(t)}
            </text>
          </g>
        ))}
        {xs.map((x, i) =>
          i % Math.ceil(xs.length / 6) === 0 ? (
            <text key={x} x={xi(x)} y={H - 8} fontSize="11" textAnchor="middle" fill="var(--ink-2)">
              {xFormat(x)}
            </text>
          ) : null,
        )}
        {series.map((s, si) => {
          const d = s.points.map((p, i) => `${i ? "L" : "M"}${xi(p.x)},${yi(p.y)}`).join(" ");
          const last = s.points[s.points.length - 1];
          return (
            <g key={s.key}>
              <path d={d} fill="none" stroke="var(--ink)" strokeWidth="2" strokeDasharray={DASH[si % 3]} strokeLinejoin="round" />
              {last ? (
                <text x={W - P.r + 8} y={labelY[s.key] + 4} fontSize="12" fill="var(--ink)" fontWeight="600">
                  {s.label}
                </text>
              ) : null}
            </g>
          );
        })}
        {marks.map(m => (
          <g key={`${m.x}-${m.label}`}>
            <circle cx={xi(m.x)} cy={yi(m.y)} r="5" fill="var(--scarlet)" stroke="var(--surface)" strokeWidth="2" />
          </g>
        ))}
      </svg>
      <table className="sr-only">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Week</th>
            {series.map(s => (
              <th scope="col" key={s.key}>
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {xs.map(x => (
            <tr key={x}>
              <th scope="row">{xFormat(x)}</th>
              {series.map(s => {
                const p = s.points.find(q => q.x === x);
                return <td key={s.key}>{p ? format(p.y) : "—"}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
