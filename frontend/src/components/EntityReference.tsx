type Props = {
  label: string;
  relationshipType: string;
};

function kindFromRelationship(relationshipType: string): string {
  if (relationshipType.includes("person")) return "person";
  if (relationshipType.includes("issued") || relationshipType.includes("organization")) {
    return "organization";
  }
  if (relationshipType.includes("country")) return "country";
  if (relationshipType.includes("derived") || relationshipType.includes("related")) {
    return "document";
  }
  return "concept";
}

export function EntityReference({ label, relationshipType }: Props) {
  const kind = kindFromRelationship(relationshipType);
  return (
    <span className="entity-chip" data-kind={kind}>
      <span className="sr-only">{kind}: </span>
      {label}
    </span>
  );
}
