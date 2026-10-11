import { motion } from "motion/react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { LogoMark } from "../../ui/Logo";

const rise = (i: number) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.15 + i * 0.14, duration: 0.55, ease: [0.22, 1, 0.36, 1] as const },
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
    <div className="w-[min(360px,30vw)] rounded-[18px] border border-line bg-surface p-5 font-[system-ui] shadow-hero">
      <p className="text-[12px] uppercase tracking-wide text-ink-2">Illustration: results page today</p>
      <p className="mt-1 text-[17px] font-semibold">Your Wellness Inventory results</p>
      <ul className="mt-3 flex flex-col gap-1.5">
        {rows.map(([l, v]) => (
          <li key={l} className="grid grid-cols-[100px_1fr_28px] items-center gap-2 text-[13px]">
            <span className={l === "Social" ? "font-semibold text-scarlet-ink" : ""}>{l}</span>
            <span className="h-2 rounded-full bg-surface-2">
              <span
                className={`block h-2 rounded-full ${l === "Social" ? "bg-scarlet" : "bg-line-strong"}`}
                style={{ width: `${((v - 1) / 3) * 100}%` }}
              />
            </span>
            <span className="text-right tabular">{v.toFixed(1)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ColdOpen() {
  return (
    <div className="absolute inset-0 grid grid-cols-[1fr_auto] items-center gap-[6vw] px-[7vw]">
      <div>
        <motion.h1 {...rise(0)} className="display text-[clamp(56px,11vh,104px)] leading-[0.98]">
          1,505 students took the inventory.
        </motion.h1>
        <motion.p {...rise(1)} className="display mt-3 text-[clamp(56px,11vh,104px)] leading-[0.98] text-scarlet">
          Then what?
        </motion.p>
      </div>
      <motion.div {...rise(2)}>
        <ResultsToday />
      </motion.div>
    </div>
  );
}

const NUMBERS: [string, string][] = [
  ["0.22 s", "to rank a student's week, live on AWS"],
  ["61 / 61", "crisis test phrases caught by code, AI off"],
  ["0", "groups under 10 ever returned to staff"],
  ["190+", "real Rutgers events and services, hourly"],
];

export function Numbers() {
  return (
    <div className="absolute inset-0 flex flex-col justify-center px-[8vw]">
      <motion.p {...rise(0)} className="text-[clamp(13px,1.9vh,16px)] font-semibold uppercase tracking-[0.14em] text-scarlet-ink">
        In numbers
      </motion.p>
      <ul className="mt-[5vh] grid grid-cols-2 gap-x-[6vw] gap-y-[6vh]">
        {NUMBERS.map(([n, l], i) => (
          <motion.li key={l} {...rise(i + 1)}>
            <p className="text-[clamp(52px,10vh,96px)] font-semibold leading-none tracking-tight tabular">{n}</p>
            <p className="mt-2 max-w-[24ch] text-[clamp(16px,2.4vh,22px)] text-ink-2">{l}</p>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

export function useQr(url: string) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    QRCode.toDataURL(url, { margin: 1, width: 420, color: { dark: "#15171a", light: "#ffffff" } }).then(setSrc, () => setSrc(null));
  }, [url]);
  return src;
}

/** A phone in the audience can't open a localhost demo, so the QR only shows when the app is on a real host. */
const PUBLIC_HOST = !/^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname);

export function Close() {
  const qr = useQr(`${window.location.origin}/tour`);
  return (
    <div className="absolute inset-0 grid grid-cols-[1fr_auto] items-center gap-[6vw] px-[8vw]">
      <div>
        <motion.p
          {...rise(0)}
          className="flex items-center gap-2 text-[clamp(13px,1.9vh,16px)] font-semibold uppercase tracking-[0.14em] text-scarlet-ink"
        >
          <LogoMark size={20} /> Compass
        </motion.p>
        <motion.h1 {...rise(1)} className="display mt-4 text-[clamp(56px,11vh,104px)] leading-[0.98]">
          Ready for a spring pilot.
        </motion.h1>
        <motion.p {...rise(2)} className="mt-6 max-w-[30ch] text-[clamp(18px,2.8vh,26px)] leading-snug text-ink-2">
          One measure: students who take one step within 14 days of their scores.
        </motion.p>
      </div>
      <motion.div {...rise(3)} className="flex flex-col items-center gap-3">
        {qr && PUBLIC_HOST ? (
          <>
            <img src={qr} alt="QR code to try Compass on your phone" className="h-[min(260px,32vh)] w-[min(260px,32vh)] rounded-2xl" />
            <p className="text-[clamp(15px,2.2vh,19px)] font-medium">Try it on your phone</p>
          </>
        ) : (
          <p className="max-w-[16ch] text-center text-[clamp(18px,2.8vh,26px)] font-medium leading-snug">In myRutgers, next to ScarletWell</p>
        )}
      </motion.div>
    </div>
  );
}
