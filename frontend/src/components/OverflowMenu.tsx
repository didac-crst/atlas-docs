import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";

type Props = {
  label?: string;
  children: ReactNode;
};

/** Compact overflow / “more” menu for secondary document actions. */
export function OverflowMenu({ label = "More actions", children }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="overflow-menu" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className="btn btn-ghost overflow-menu-trigger"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={menuId}
        aria-label={label}
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontal size={16} aria-hidden />
        <span className="overflow-menu-label">{label}</span>
      </button>
      {open ? (
        <div
          className="overflow-menu-panel"
          id={menuId}
          role="menu"
          aria-label={label}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
