export function Spinner({ className = "", label }: { className?: string; label?: string }) {
  return (
    <span className={`inline-flex ${className}`} role={label ? "status" : undefined} aria-label={label}>
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" className="animate-spin">
        <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" />
        <path d="M18 10a8 8 0 0 0-8-8" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
    </span>
  );
}
