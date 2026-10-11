import type { ReactNode } from "react";
import { useT } from "../i18n/useT";

type Tone = "neutral" | "amber" | "green" | "scarlet" | "ink";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-ink-2",
  amber: "bg-amber-tint text-amber",
  green: "bg-green-tint text-green",
  scarlet: "bg-scarlet-tint text-scarlet-ink",
  ink: "bg-ink text-bg",
};

export function Badge({ tone = "neutral", children, icon }: { tone?: Tone; children: ReactNode; icon?: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[13px] font-medium leading-5 ${tones[tone]}`}
    >
      {icon}
      {children}
    </span>
  );
}

/** "Sample" for synthetic items. Real items need no badge; their source shows under "Why this fits". */
export function SourceBadge({ synthetic }: { synthetic: boolean }) {
  const t = useT();
  if (!synthetic) return null;
  return <Badge tone="amber">{t("common.sample")}</Badge>;
}
