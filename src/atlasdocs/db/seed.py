"""Idempotent seed loader for AtlasDocs ontologies and relationship types."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlasdocs.config import get_settings
from atlasdocs.db.models import (
    Concept,
    Entity,
    EntityType,
    Ontology,
    RelationshipDirectionality,
    RelationshipType,
)
from atlasdocs.db.session import get_engine, get_session_factory
from atlasdocs.services.entity_types import (
    lifecycle_category_for_registry_code,
    registry_code_for_ontology,
)


def load_seed_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Seed file must be a mapping: {path}")
    return data


def _directionality(value: str | None) -> RelationshipDirectionality:
    if value is None:
        return RelationshipDirectionality.directed
    return RelationshipDirectionality(value)


def _entity_type_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"entity type list must be a list, got {type(value).__name__}")
    codes = [str(item).strip().lower() for item in value if str(item).strip()]
    return codes or None


def apply_seed(session: Session, data: dict) -> None:
    ontology_by_code: dict[str, Ontology] = {}

    for item in data.get("ontologies", []):
        ontology = session.scalar(select(Ontology).where(Ontology.code == item["code"]))
        if ontology is None:
            ontology = Ontology(code=item["code"], name=item["name"])
            session.add(ontology)
            session.flush()
        else:
            ontology.name = item["name"]
        ontology_by_code[ontology.code] = ontology

        for concept_item in item.get("concepts", []):
            concept = session.scalar(
                select(Concept).where(
                    Concept.ontology_id == ontology.id,
                    Concept.code == concept_item["code"],
                )
            )
            if concept is None:
                entity = Entity(
                    id=uuid.uuid4(),
                    entity_type=EntityType.concept,
                    semantic_completeness="empty",
                    lifecycle_category=lifecycle_category_for_registry_code(
                        registry_code_for_ontology(ontology.code)
                    ),
                )
                session.add(entity)
                session.flush()
                session.add(
                    Concept(
                        id=entity.id,
                        ontology_id=ontology.id,
                        code=concept_item["code"],
                        name=concept_item["name"],
                    )
                )
            else:
                concept.name = concept_item["name"]

    session.flush()

    rel_types: dict[str, RelationshipType] = {}
    for item in data.get("relationship_types", []):
        target_code = item.get("target_ontology")
        target_ontology_id = None
        if target_code:
            target = ontology_by_code.get(target_code) or session.scalar(
                select(Ontology).where(Ontology.code == target_code)
            )
            if target is None:
                raise ValueError(f"Unknown target ontology '{target_code}' for {item['code']}")
            target_ontology_id = target.id

        rel_type = session.scalar(
            select(RelationshipType).where(RelationshipType.code == item["code"])
        )
        directionality = _directionality(item.get("directionality"))
        source_types = _entity_type_list(item.get("source_entity_types"))
        target_types = _entity_type_list(item.get("target_entity_types"))
        if rel_type is None:
            rel_type = RelationshipType(
                code=item["code"],
                name=item["name"],
                target_ontology_id=target_ontology_id,
                directionality=directionality,
                source_entity_types=source_types,
                target_entity_types=target_types,
            )
            session.add(rel_type)
            session.flush()
        else:
            rel_type.name = item["name"]
            rel_type.target_ontology_id = target_ontology_id
            rel_type.directionality = directionality
            rel_type.source_entity_types = source_types
            rel_type.target_entity_types = target_types
        rel_types[rel_type.code] = rel_type

    session.flush()

    for item in data.get("relationship_types", []):
        inverse_code = item.get("inverse")
        rel_type = rel_types[item["code"]]
        if not inverse_code:
            rel_type.inverse_relationship_type_id = None
            continue
        if rel_type.directionality == RelationshipDirectionality.symmetric:
            raise ValueError(
                f"Symmetric relationship type '{item['code']}' must not declare an inverse"
            )
        inverse = rel_types.get(inverse_code) or session.scalar(
            select(RelationshipType).where(RelationshipType.code == inverse_code)
        )
        if inverse is None:
            raise ValueError(f"Unknown inverse relationship type '{inverse_code}'")
        if inverse.code == rel_type.code:
            raise ValueError(
                f"Relationship type '{item['code']}' must not be its own inverse"
            )
        rel_type.inverse_relationship_type_id = inverse.id

    session.flush()
    for rel_type in rel_types.values():
        if rel_type.inverse_relationship_type_id is None:
            continue
        partner = session.get(RelationshipType, rel_type.inverse_relationship_type_id)
        if partner is None or partner.inverse_relationship_type_id != rel_type.id:
            raise ValueError(
                f"Inverse of '{rel_type.code}' must declare '{rel_type.code}' as its inverse"
            )


def seed_from_path(session: Session, path: Path) -> None:
    apply_seed(session, load_seed_file(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load AtlasDocs seed data")
    parser.add_argument(
        "--seed",
        type=Path,
        default=None,
        help="Path to seed YAML (default: settings.seed_path)",
    )
    args = parser.parse_args()
    settings = get_settings()
    seed_path = args.seed or Path(settings.seed_path)
    get_engine()
    session = get_session_factory()()
    try:
        seed_from_path(session, seed_path)
        session.commit()
        print(f"Seeded from {seed_path}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
