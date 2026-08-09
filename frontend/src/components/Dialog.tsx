import { useEffect, useId, useRef, type ReactNode } from "react";

type Props = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Full-viewport overlay on small screens (document viewer). */
  fullScreenMobile?: boolean;
  className?: string;
  role?: "dialog" | "alertdialog";
};

export function Dialog({
  title,
  onClose,
  children,
  fullScreenMobile = false,
  className,
  role = "dialog",
}: Props) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="dialog-root" role="presentation">
      <button type="button" className="dialog-backdrop" aria-label="Close dialog" onClick={onClose} />
      <div
        className={[
          "dialog-panel",
          fullScreenMobile ? "dialog-panel-mobile-full" : "",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="dialog-header">
          <h2 id={titleId} className="dialog-title">
            {title}
          </h2>
          <button
            ref={closeRef}
            type="button"
            className="btn btn-ghost dialog-close"
            onClick={onClose}
          >
            Close
          </button>
        </header>
        <div className="dialog-body">{children}</div>
      </div>
    </div>
  );
}
