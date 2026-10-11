import { MapPin } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

const STYLE = "https://tiles.openfreemap.org/styles/positron";

/** Small map with one scarlet pin. MapLibre loads lazily; any failure (no WebGL, tiles blocked, offline) falls back
 *  to the address so the card never shows a broken box. Still until tapped, then it can be panned and zoomed. */
export function EventMap({ lat, lon, label }: { lat: number; lon: number; label: string }) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ dragPan: { enable(): void }; touchZoomRotate: { enable(): void }; scrollZoom: { enable(): void }; remove(): void } | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => !cancelled && setState(s => (s === "loading" ? "failed" : s)), 4000);
    (async () => {
      try {
        const ml = (await import("maplibre-gl")).default as unknown as typeof import("maplibre-gl");
        await import("maplibre-gl/dist/maplibre-gl.css");
        if (cancelled || !box.current) return;
        const map = new ml.Map({
          container: box.current,
          style: STYLE,
          center: [lon, lat],
          zoom: 15.4,
          interactive: true,
          attributionControl: { compact: true },
        });
        map.dragPan.disable();
        map.scrollZoom.disable();
        map.touchZoomRotate.disable();
        map.doubleClickZoom.disable();
        map.keyboard.disable();
        new ml.Marker({ color: "#CC0033" }).setLngLat([lon, lat]).addTo(map);
        map.on("load", () => !cancelled && setState("ready"));
        map.on("error", () => !cancelled && setState(s => (s === "ready" ? s : "failed")));
        mapRef.current = map as unknown as typeof mapRef.current;
      } catch {
        if (!cancelled) setState("failed");
      }
    })();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [lat, lon]);

  if (state === "failed") {
    return (
      <div className="flex h-[88px] items-center gap-3 rounded-2xl bg-surface-2 px-4 text-[15px] text-ink-2">
        <MapPin size={22} className="shrink-0 text-scarlet-ink" aria-hidden />
        {label}
      </div>
    );
  }
  return (
    <div className="relative h-[160px] overflow-hidden rounded-2xl bg-surface-2" data-tour="event-map">
      <div ref={box} className="absolute inset-0" role="img" aria-label={`Map: ${label}`} />
      {!live && state === "ready" ? (
        <button
          type="button"
          onClick={() => {
            const m = mapRef.current;
            m?.dragPan.enable();
            m?.touchZoomRotate.enable();
            m?.scrollZoom.enable();
            setLive(true);
          }}
          className="absolute inset-0 cursor-pointer"
          aria-label="Explore the map"
        />
      ) : null}
    </div>
  );
}
