import { AtlasIcon, type AtlasIconName } from "./atlasIcons";

type Props = {
  icon: AtlasIconName;
  label: string;
  value: string;
  className?: string;
};

/** Glyph + value metadata row (no redundant text labels). */
export function DocumentMetaItem({ icon, label, value, className }: Props) {
  return (
    <span className={["doc-meta-item", className].filter(Boolean).join(" ")} title={label}>
      <AtlasIcon name={icon} size={14} />
      <span className="doc-meta-value">{value}</span>
    </span>
  );
}
