/** Compass mark: a needle pointing one way. Scarlet north, ink south. */
export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <circle cx="16" cy="16" r="14.5" fill="none" stroke="currentColor" strokeOpacity="0.18" strokeWidth="1.5" />
      <path d="M16 4.5 L20 16 L16 14.2 L12 16 Z" fill="var(--scarlet)" />
      <path d="M16 27.5 L12 16 L16 17.8 L20 16 Z" fill="currentColor" />
      <circle cx="16" cy="16" r="1.6" fill="var(--bg)" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2 text-ink">
      <LogoMark size={26} />
      <span className="display text-[24px] leading-none">Compass</span>
    </span>
  );
}
