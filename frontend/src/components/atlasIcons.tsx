import {
  Briefcase,
  Building2,
  Calendar,
  Check,
  Copy,
  Download,
  ExternalLink,
  Eye,
  FileSearch,
  FileText,
  Globe2,
  Lightbulb,
  ListFilter,
  MoreHorizontal,
  Network,
  Search,
  Share2,
  Tag,
  Tags,
  Trash2,
  User,
  type LucideIcon,
} from "lucide-react";

/**
 * Canonical AtlasDocs glyph map — same concept → same icon everywhere.
 * Do not pick ad-hoc icons inside individual screens.
 */
export const atlasIcons = {
  document: FileText,
  details: FileSearch,
  preview: Eye,
  external: ExternalLink,
  download: Download,
  relationship: Share2,
  knowledge: Network,
  organization: Building2,
  person: User,
  country: Globe2,
  case: Briefcase,
  concept: Lightbulb,
  date: Calendar,
  tag: Tag,
  tags: Tags,
  search: Search,
  classification: Tags,
  more: MoreHorizontal,
  trash: Trash2,
  select: Check,
  pages: Copy,
  filters: ListFilter,
} as const satisfies Record<string, LucideIcon>;

export type AtlasIconName = keyof typeof atlasIcons;

type AtlasIconProps = {
  name: AtlasIconName;
  size?: number;
  className?: string;
  "aria-hidden"?: boolean | "true" | "false";
};

export function AtlasIcon({
  name,
  size = 16,
  className,
  "aria-hidden": ariaHidden = true,
}: AtlasIconProps) {
  const Icon = atlasIcons[name];
  return <Icon size={size} className={className} aria-hidden={ariaHidden} />;
}
