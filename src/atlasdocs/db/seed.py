"""Idempotent seed loader for AtlasDocs v0.1 ontologies and relationship types."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlasdocs.config import get_settings
from atlasdocs.db.models import Concept, Ontology, RelationshipType
from atlasdocs.db.session import get_engine, get_session_factory


def load_seed_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Seed file must be a mapping: {path}")
    return data


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
                session.add(
                    Concept(
                        ontology_id=ontology.id,
                        code=concept_item["code"],
                        name=concept_item["name"],
                    )
                )
            else:
                concept.name = concept_item["name"]

    session.flush()

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
        if rel_type is None:
            session.add(
                RelationshipType(
                    code=item["code"],
                    name=item["name"],
                    target_ontology_id=target_ontology_id,
                )
            )
        else:
            rel_type.name = item["name"]
            rel_type.target_ontology_id = target_ontology_id


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
