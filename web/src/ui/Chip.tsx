import { Check } from "@phosphor-icons/react";
import { motion } from "motion/react";
import type { ReactNode } from "react";

type Props = {
  selected?: boolean;
  onClick?: () => void;
  children: ReactNode;
  icon?: ReactNode;
  hint?: boolean; // softly highlighted suggestion (not selected)
  disabled?: boolean;
  "data-tour"?: string;
};

export function Chip({ selected = false, onClick, children, icon, hint, disabled, ...rest }: Props) {
  return (
    <motion.button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onClick}
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", stiffness: 600, damping: 35 }}
      data-tour={rest["data-tour"]}
      className={
        "inline-flex min-h-11 items-center gap-2 rounded-full border px-4 py-2 text-[15px] font-medium cursor-pointer " +
        "transition-colors duration-150 text-left " +
        (selected
          ? "border-ink bg-ink text-bg"
          : hint
            ? "border-scarlet/40 bg-scarlet-tint text-ink hover:border-scarlet/70"
            : "border-line-strong/60 bg-surface text-ink hover:bg-surface-2")
      }
    >
      {selected ? <Check size={16} weight="bold" aria-hidden /> : icon}
      <span>{children}</span>
    </motion.button>
  );
}
