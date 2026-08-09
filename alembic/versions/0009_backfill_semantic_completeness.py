"""Backfill semantic_completeness for existing entities."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from atlasdocs.services.completeness import CompletenessInput, calculate_completeness
from atlasdocs.services.entity_types import registry_code_for_ontology

revision: str = "0009_backfill_semantic_completeness"
down_revision: Union[str, None] = "0008_document_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    entities = conn.execute(
        sa.text(
            """
            SELECT e.id, e.entity_type, o.code AS ontology_code
            FROM entities e
            LEFT JOIN concepts c ON c.id = e.id
            LEFT JOIN ontologies o ON o.id = c.ontology_id
            """
        )
    ).mappings().all()
    if not entities:
        return

    rel_rows = conn.execute(
        sa.text(
            """
            SELECT r.source_entity_id, r.status, rt.code AS relationship_code
            FROM relationships r
            JOIN relationship_types rt ON rt.id = r.relationship_type_id
            """
        )
    ).mappings().all()
    by_source: dict[str, list[tuple[str, str]]] = {}
    for row in rel_rows:
        by_source.setdefault(str(row["source_entity_id"]), []).append(
            (str(row["status"]), str(row["relationship_code"]))
        )

    for entity in entities:
        entity_id = str(entity["id"])
        entity_type = str(entity["entity_type"])
        if entity_type == "document":
            registry_type = "document"
        else:
            registry_type = registry_code_for_ontology(entity["ontology_code"])
        rows = by_source.get(entity_id, [])
        confirmed = frozenset(
            code for status, code in rows if status == "confirmed"
        )
        has_suggested = any(status == "suggested" for status, _code in rows)
        state = calculate_completeness(
            CompletenessInput(
                registry_type=registry_type,
                confirmed_relationship_codes=confirmed,
                has_suggested_relationships=has_suggested,
            )
        )
        conn.execute(
            sa.text(
                "UPDATE entities SET semantic_completeness = :state WHERE id = :id"
            ),
            {"state": state, "id": entity["id"]},
        )


def downgrade() -> None:
    # Completeness values can be recomputed; leave stored values unchanged.
    pass
