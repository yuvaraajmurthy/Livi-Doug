import { motion } from "motion/react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { LogoMark } from "../../ui/Logo";

const rise = (i: number) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.15 + i * 0.12, duration: 0.55, ease: [0.22, 1, 0.36, 1] as const },
});

/** Before: a plain, generic results page (an illustration, no Rutgers marks). Social 1.9, and nothing to do. */
function ResultsToday() {
  const rows: [string, number][] = [
    ["Spiritual", 3.4],
    ["Intellectual", 3.2],
    ["Occupational", 3.0],
    ["Environmental", 2.9],
    ["Physical", 2.7],
    ["Emotional", 2.6],
    ["Financial", 2.1],
    ["Social", 1.9],
  ];
  return (
    <div className="w-[340px] rounded-[18px] border border-line bg-surface p-5 font-[system-ui] shadow-hero">
      <p className="text-[12px] uppercase tracking-wide text-ink-2">Illustration: a results page today</p>
      <p className="mt-1 text-[17px] font-semibold">Your Wellness Inventory results</p>
      <ul className="mt-3 flex flex-col gap-1.5">
        {rows.map(([l, v]) => (
          <li key={l} className="grid grid-cols-[100px_1fr_28px] items-center gap-2 text-[13px]">
            <span className={l === "Social" ? "font-semibold text-scarlet-ink" : ""}>{l}</span>
            <span className="h-2 rounded-full bg-surface-2">
              <span className={`block h-2 rounded-full ${l === "Social" ? "bg-scarlet" : "bg-line-strong"}`} style={{ width: `${((v - 1) / 3) * 100}%` }} />
            </span>
            <span className="text-right tabular">{v.toFixed(1)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 rounded-lg bg-surface-2 px-3 py-2 text-[13px] text-ink-2">Thank you for completing the inventory.</p>
    </div>
  );
}

export function ColdOpen() {
  return (
    <div className="grid h-full grid-cols-[1fr_auto] items-center gap-16 px-16">
      <div>
        <motion.p {...rise(0)} className="text-[15px] font-semibold uppercase tracking-[0.12em] text-scarlet-ink">
          Rutgers Health Hack 2026 · Wellness Reimagined
        </motion.p>
        <motion.h1 {...rise(1)} className="display mt-4 text-[76px] leading-[0.98]">
          1,505 students took the inventory.
        </motion.h1>
        <motion.p {...rise(2)} className="display mt-3 text-[76px] leading-[0.98] text-scarlet">
          Then what?
        </motion.p>
        <motion.p {...rise(3)} className="mt-8 max-w-[34ch] text-[22px] leading-snug text-ink-2">
          Andre scored 1.9 in Social. He commutes, has one gap on Tuesdays, and eats lunch in his car.
        </motion.p>
      </div>
      <motion.div {...rise(2)}>
        <ResultsToday />
        <p className="mt-4 text-center text-[16px] text-ink-2">…and nothing to do next.</p>
      </motion.div>
    </div>
  );
}

function useQr(url: string) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    QRCode.toDataURL(url, { margin: 1, width: 360, color: { dark: "#15171a", light: "#ffffff" } }).then(setSrc, () => setSrc(null));
  }, [url]);
  return src;
}

const NUMBERS: [string, string][] = [
  ["0.22 s", "p95 to rank a student's whole week, live on AWS"],
  ["61 / 61", "crisis test phrases caught by code alone, AI off"],
  ["0", "groups under 10 the database will return to staff"],
  ["190+", "real Rutgers events and services, refreshed hourly"],
];

const RUBRIC: [string, string][] = [
  ["Impact", "Score → one step → follow-up → retake, closed in one loop"],
  ["Engagement", "If-then plan, reminder, bring-a-friend, cooperative campus cup"],
  ["Safety", "Code-first crisis check, care-first rule, a fixed crisis card"],
  ["Equity", "Newark and Camden resources, Spanish, online evenings, free first"],
  ["Privacy", "Student-visible, deletable memory; staff see groups of 10+ only"],
  ["Feasibility", "Live on AWS, fixtures fallback, works with AI switched off"],
];

export function Close() {
  const qr = useQr(`${window.location.origin}/tour`);
  return (
    <div className="grid h-full grid-cols-[1.2fr_1fr] gap-12 px-14 py-10">
      <div className="flex flex-col justify-center">
        <motion.p {...rise(0)} className="flex items-center gap-2 text-[15px] font-semibold uppercase tracking-[0.12em] text-scarlet-ink">
          <LogoMark size={20} /> Compass
        </motion.p>
        <motion.h1 {...rise(1)} className="display mt-3 text-[64px] leading-[1]">
          Ready for a spring pilot at Newark.
        </motion.h1>
        <motion.p {...rise(2)} className="mt-4 max-w-[40ch] text-[20px] leading-snug text-ink-2">
          One measure: the share of students who take one step within 14 days of getting their scores.
        </motion.p>
        <motion.ul {...rise(3)} className="mt-8 grid grid-cols-2 gap-x-8 gap-y-5">
          {NUMBERS.map(([n, l]) => (
            <li key={l}>
              <p className="text-[34px] font-semibold leading-none tracking-tight tabular">{n}</p>
              <p className="mt-1 text-[15px] leading-snug text-ink-2">{l}</p>
            </li>
          ))}
        </motion.ul>
      </div>
      <div className="flex flex-col justify-center gap-5">
        <motion.ul {...rise(4)} className="flex flex-col gap-2.5">
          {RUBRIC.map(([k, v]) => (
            <li key={k} className="grid grid-cols-[110px_1fr] gap-3 text-[15px] leading-snug">
              <span className="font-semibold text-scarlet-ink">{k}</span>
              <span>{v}</span>
            </li>
          ))}
        </motion.ul>
        <motion.div {...rise(5)} className="flex items-center gap-5 rounded-[20px] border border-line bg-surface p-4">
          {qr ? <img src={qr} alt="QR code to try Compass on your phone" className="h-[132px] w-[132px] rounded-lg" /> : <div className="h-[132px] w-[132px]" />}
          <div>
            <p className="text-[20px] font-semibold leading-tight">Try it on your phone</p>
            <p className="mt-1 text-[15px] text-ink-2">Five students and the staff view. A private copy each, about a minute per tour.</p>
            <p className="mt-2 text-[13px] text-ink-2">Synthetic students; sample events are labelled.</p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

export { useQr };
