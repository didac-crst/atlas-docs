import type { DocumentDetail } from "../api/client";

const CONTEXT_RELATIONSHIP_PRIORITY = ["source-country", "document-type", "issued-by"] as const;

export function documentDisplayTitle(document: Pick<DocumentDetail, "title">): string {
  const title = document.title?.trim();
  return title || "Untitled document";
}

export function documentContextLine(document: DocumentDetail): string {
  const parts: string[] = [];
  const used = new Set<string>();

  for (const code of CONTEXT_RELATIONSHIP_PRIORITY) {
    const rel = document.relationships.find((item) => item.type === code);
    if (rel?.target) {
      parts.push(rel.target);
      used.add(code);
    }
  }

  if (!used.has("document-type") && document.document_type) {
    parts.push(document.document_type);
  }
  if (!used.has("issued-by") && document.correspondent) {
    parts.push(document.correspondent);
  }

  if (document.created_date) {
    const year = document.created_date.slice(0, 4);
    if (/^\d{4}$/.test(year)) parts.push(year);
  }

  return parts.join(" · ");
}
