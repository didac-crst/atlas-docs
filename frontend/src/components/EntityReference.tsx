import { Link } from "react-router-dom";

type Props = {
  label: string;
  relationshipType: string;
  entityId?: string | null;
  paperlessDocumentId?: number | null;
};

function kindFromRelationship(relationshipType: string): string {
  if (relationshipType.includes("person")) return "person";
  if (relationshipType.includes("issued") || relationshipType.includes("organization")) {
    return "organization";
  }
  if (relationshipType.includes("country")) return "country";
  if (relationshipType.includes("case") || relationshipType.includes("belongs")) return "case";
  if (relationshipType.includes("derived") || relationshipType.includes("related") || relationshipType.includes("replies")) {
    return "document";
  }
  return "concept";
}

export function EntityReference({
  label,
  relationshipType,
  entityId,
  paperlessDocumentId,
}: Props) {
  const kind = kindFromRelationship(relationshipType);
  const href =
    paperlessDocumentId != null
      ? `/documents/${paperlessDocumentId}`
      : entityId
        ? `/entities/${entityId}`
        : null;
  const chip = (
    <span className="entity-chip" data-kind={kind}>
      <span className="sr-only">{kind}: </span>
      {label}
    </span>
  );
  if (!href) return chip;
  return (
    <Link to={href} className="entity-reference-link">
      {chip}
    </Link>
  );
}
