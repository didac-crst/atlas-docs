import type { ReactNode } from "react";

export type LayoutWidth = "narrow" | "standard" | "wide";

type Props = {
  width: LayoutWidth;
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
};

/** Centered page containers: narrow ~750px, standard ~1150px, wide ~1600px / 95vw. */
export function PageLayout({ width, children, className, as: Tag = "div" }: Props) {
  const classes = ["page-layout", `page-layout-${width}`, className].filter(Boolean).join(" ");
  return <Tag className={classes}>{children}</Tag>;
}
