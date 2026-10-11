import { X } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useT } from "../i18n/useT";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Visually hide the title (still labels the dialog). */
  hideTitle?: boolean;
  tone?: "default" | "plain";
};

/** Bottom sheet on phones, centred dialog from 768px. Traps focus, closes on Escape/scrim, returns focus. */
export function Sheet({ open, onClose, title, children, footer, hideTitle }: Props) {
  const t = useT();
  const id = useId();
  const panel = useRef<HTMLDivElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    returnTo.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusFirst = () => {
      const nodes = panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      (nodes && nodes.length > 1 ? nodes[1] : nodes?.[0])?.focus(); // [0] is the close button
    };
    const raf = requestAnimationFrame(focusFirst);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !panel.current) return;
      const nodes = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      } else if (!panel.current.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("keydown", onKey, true);
      document.body.style.overflow = prevOverflow;
      const el = returnTo.current;
      if (el && document.contains(el)) el.focus();
    };
  }, [open]);

  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center">
          <motion.div
            className="absolute inset-0 bg-[var(--scrim)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.16 } }}
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={id}
            className="relative flex max-h-[88dvh] w-full max-w-[480px] flex-col rounded-t-[28px] bg-surface shadow-float md:rounded-[28px]"
            initial={{ y: "100%", opacity: 0.6 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: "100%", opacity: 0.6, transition: { duration: 0.18, ease: [0.4, 0, 1, 1] } }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
          >
            <div className="mx-auto mt-2.5 h-1.5 w-10 shrink-0 rounded-full bg-line md:hidden" aria-hidden="true" />
            <div className="flex items-start justify-between gap-3 px-6 pb-2 pt-4">
              <h2 id={id} className={hideTitle ? "sr-only" : "text-[22px] font-semibold leading-7 tracking-tight"}>
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("common.close")}
                className="-mr-2 -mt-1 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink-2 hover:bg-surface-2 cursor-pointer"
              >
                <X size={20} aria-hidden />
              </button>
            </div>
            <div className="overflow-y-auto overscroll-contain px-6 pb-6">{children}</div>
            {footer ? <div className="border-t border-line px-6 pb-[calc(16px+env(safe-area-inset-bottom))] pt-4">{footer}</div> : null}
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
