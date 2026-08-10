import type { ExploreResultItem } from "../api/client";

export type DocumentPresentation = {
  paperlessDocumentId: number | null;
  title: string;
  documentType: string | null;
  correspondent: string | null;
  createdDate: string | null;
  createdDateLabel: string | null;
  relationshipCount: number | null;
  knowledgeContext: string | null;
  semanticCompleteness: string;
  entityType: string;
  previewAvailable: boolean;
  downloadAvailable: boolean;
  thumbnailAvailable: boolean;
  openUrl: string | null;
  entityId: string | null;
};

/** Compact month+year when ISO-like; otherwise return the original string. */
export function formatDocumentDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  const match = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(trimmed);
  if (!match) return trimmed;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!year || month < 1 || month > 12) return trimmed;
  const label = new Date(Date.UTC(year, month - 1, 1)).toLocaleString("en-US", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  return label;
}

/**
 * Build a short knowledge line from confirmed relationship summaries.
 * Does not invent relationships — empty when none are useful.
 */
export function knowledgeContextFromSummary(summary: string[]): string | null {
  if (!summary.length) return null;
  const parts = summary
    .slice(0, 3)
    .map((row) => {
      const idx = row.indexOf(":");
      if (idx <= 0) return row.trim();
      const type = row.slice(0, idx).trim();
      const target = row.slice(idx + 1).trim();
      if (!type || !target) return row.trim();
      return `${type} → ${target}`;
    })
    .filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

export function toDocumentPresentation(item: ExploreResultItem): DocumentPresentation {
  return {
    paperlessDocumentId: item.paperless_document_id,
    title: item.label?.trim() || "Untitled",
    documentType: item.document_type,
    correspondent: item.correspondent,
    createdDate: item.created_date,
    createdDateLabel: formatDocumentDate(item.created_date),
    relationshipCount:
      item.relationship_count === null
        ? null
        : typeof item.relationship_count === "number"
          ? item.relationship_count
          : item.relationship_summary.length,
    knowledgeContext: knowledgeContextFromSummary(item.relationship_summary),
    semanticCompleteness: item.semantic_completeness,
    entityType: item.entity_type,
    previewAvailable: item.preview_available,
    downloadAvailable: item.download_available,
    // Dedicated raster thumbnail BFF is not available yet; never treat PDF preview as an image.
    thumbnailAvailable: false,
    openUrl: item.open_url,
    entityId: item.id,
  };
}
