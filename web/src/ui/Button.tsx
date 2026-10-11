import { motion, type HTMLMotionProps } from "motion/react";
import { forwardRef, type ReactNode } from "react";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "quiet";
type Size = "lg" | "md" | "sm";

export type ButtonProps = Omit<HTMLMotionProps<"button">, "children"> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
  icon?: ReactNode;
  children?: ReactNode;
};

const base =
  "relative inline-flex items-center justify-center gap-2 font-medium select-none cursor-pointer " +
  "transition-[background-color,color,border-color,opacity] duration-150 disabled:cursor-not-allowed";

const variants: Record<Variant, string> = {
  primary: "bg-scarlet text-on-scarlet hover:brightness-[1.06] disabled:opacity-50",
  secondary: "bg-surface text-ink border border-line-strong hover:bg-surface-2 disabled:opacity-50",
  ghost: "bg-transparent text-ink hover:bg-surface-2 disabled:opacity-50",
  quiet: "bg-surface-2 text-ink hover:brightness-[0.97] disabled:opacity-50",
  danger: "bg-transparent text-scarlet-ink border border-scarlet/50 hover:bg-scarlet-tint disabled:opacity-50",
};

const sizes: Record<Size, string> = {
  lg: "h-14 px-6 text-[17px] rounded-2xl",
  md: "h-12 px-5 text-[16px] rounded-[14px]",
  sm: "h-11 px-4 text-[15px] rounded-xl",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "lg", loading, block, icon, children, className = "", disabled, type, ...rest },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <motion.button
      ref={ref}
      type={type ?? "button"}
      whileTap={isDisabled ? undefined : { scale: 0.97 }}
      transition={{ type: "spring", stiffness: 600, damping: 35 }}
      disabled={isDisabled}
      aria-busy={loading ? true : undefined}
      className={`${base} ${variants[variant]} ${sizes[size]} ${block ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {loading ? <Spinner className="absolute" /> : null}
      <span className={`inline-flex items-center gap-2 ${loading ? "invisible" : ""}`}>
        {icon}
        {children}
      </span>
    </motion.button>
  );
});
