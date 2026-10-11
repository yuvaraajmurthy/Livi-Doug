import { MapPin } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

const TILE = 256;
const ZOOM = 16;
const HEIGHT = 160;
const url = (x: number, y: number) => `https://tile.openstreetmap.org/${ZOOM}/${x}/${y}.png`;

/** Web-Mercator pixel position at ZOOM. */
function project(lat: number, lon: number) {
  const n = TILE * 2 ** ZOOM;
  const s = Math.sin((lat * Math.PI) / 180);
  return { x: ((lon + 180) / 360) * n, y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n };
}

/** A static map from OpenStreetMap raster tiles (desaturated to sit quietly in the palette) with one scarlet pin. No WebGL, no SDK:
 *  it renders anywhere, and falls back to the address if tiles can't load. Tapping opens directions. */
export function EventMap({ lat, lon, label, href }: { lat: number; lon: number; label: string; href?: string }) {
  const box = useRef<HTMLAnchorElement>(null);
  const [w, setW] = useState(0);
  const [failed, setFailed] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    setW(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const p = project(lat, lon);
  const left = p.x - w / 2;
  const top = p.y - HEIGHT / 2;
  const tiles: { x: number; y: number }[] = [];
  if (w) {
    for (let tx = Math.floor(left / TILE); tx <= Math.floor((left + w) / TILE); tx++)
      for (let ty = Math.floor(top / TILE); ty <= Math.floor((top + HEIGHT) / TILE); ty++) tiles.push({ x: tx, y: ty });
  }

  if (failed > 2) {
    return (
      <div className="flex h-[88px] items-center gap-3 rounded-2xl bg-surface-2 px-4 text-[15px] text-ink-2">
        <MapPin size={22} className="shrink-0 text-scarlet-ink" aria-hidden />
        {label}
      </div>
    );
  }
  return (
    <a
      ref={box}
      href={href}
      target="_blank"
      rel="noreferrer"
      aria-label={`Map: ${label}. Open directions`}
      data-tour="event-map"
      className="relative block h-[160px] overflow-hidden rounded-2xl bg-surface-2"
    >
      {tiles.map(t => (
        <img
          key={`${t.x}-${t.y}`}
          src={url(t.x, t.y)}
          alt=""
          width={TILE}
          height={TILE}
          draggable={false}
          onError={() => setFailed(f => f + 1)}
          referrerPolicy="strict-origin-when-cross-origin"
          className="absolute max-w-none select-none [filter:grayscale(1)_contrast(0.92)_brightness(1.06)]"
          style={{ left: t.x * TILE - left, top: t.y * TILE - top, width: TILE, height: TILE }}
        />
      ))}
      <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-full drop-shadow-[0_2px_3px_rgba(0,0,0,0.3)]" aria-hidden>
        <svg width="30" height="40" viewBox="0 0 30 40">
          <path d="M15 0C6.7 0 0 6.5 0 14.6 0 25.5 15 40 15 40s15-14.5 15-25.4C30 6.5 23.3 0 15 0z" fill="#CC0033" />
          <circle cx="15" cy="14.5" r="5.5" fill="#fff" />
        </svg>
      </span>
      <span className="absolute bottom-1 right-1.5 rounded bg-white/80 px-1 text-[10px] text-[#444]">© OpenStreetMap</span>
    </a>
  );
}
