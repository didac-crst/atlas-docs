"""Alembic upgrade preserves v0.1/v0.2 semantic data into the v0.3 model."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_v03_migration_backfills_external_references_and_entity_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "migrate.db"
    db_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    monkeypatch.setenv("ATLASDOCS_SQLALCHEMY_URL", db_url)
    monkeypatch.setenv("SESSION_SECRET", "test-secret")

    cfg = _alembic_config(db_url)
    command.upgrade(cfg, "0001_v01_semantic_core")

    engine = create_engine(db_url)
    ontology_id = str(uuid.uuid4())
    concept_id = str(uuid.uuid4())
    entity_id = str(uuid.uuid4())
    doc_ref_id = str(uuid.uuid4())
    rel_type_id = str(uuid.uuid4())
    relationship_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ontologies (id, code, name) VALUES (:id, 'country', 'Country')"
            ),
            {"id": ontology_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO concepts (id, ontology_id, code, name)
                VALUES (:id, :ontology_id, 'germany', 'Germany')
                """
            ),
            {"id": concept_id, "ontology_id": ontology_id},
        )
        conn.execute(
            text("INSERT INTO entities (id, created_at) VALUES (:id, CURRENT_TIMESTAMP)"),
            {"id": entity_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO document_references
                    (id, entity_id, paperless_document_id, created_at)
                VALUES (:id, :entity_id, 184, CURRENT_TIMESTAMP)
                """
            ),
            {"id": doc_ref_id, "entity_id": entity_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO relationship_types (id, code, name, target_ontology_id)
                VALUES (:id, 'source-country', 'Source Country', :ontology_id)
                """
            ),
            {"id": rel_type_id, "ontology_id": ontology_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO relationships (
                    id, source_entity_id, relationship_type_id, target_concept_id,
                    origin, status, created_at
                ) VALUES (
                    :id, :source, :type_id, :target, 'rule', 'confirmed', CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": relationship_id,
                "source": entity_id,
                "type_id": rel_type_id,
                "target": concept_id,
            },
        )

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        entity_type = conn.execute(
            text("SELECT entity_type FROM entities WHERE id = :id"),
            {"id": entity_id},
        ).scalar_one()
        assert entity_type == "document"

        concept_entity = conn.execute(
            text("SELECT entity_type FROM entities WHERE id = :id"),
            {"id": concept_id},
        ).scalar_one()
        assert concept_entity == "concept"

        ext = conn.execute(
            text(
                """
                SELECT system, external_id, entity_id
                FROM external_references
                WHERE external_id = '184'
                """
            )
        ).one()
        assert ext == ("paperless", "184", entity_id)

        rel = conn.execute(
            text(
                """
                SELECT target_entity_id, origin, created_by, model, prompt_version, generated_at
                FROM relationships WHERE id = :id
                """
            ),
            {"id": relationship_id},
        ).one()
        assert rel[0] == concept_id
        assert rel[1] == "deterministic-rule"
        assert rel[2] is None
        assert rel[3] is None
        assert rel[4] is None
        assert rel[5] is None

        directionality = conn.execute(
            text("SELECT directionality FROM relationship_types WHERE id = :id"),
            {"id": rel_type_id},
        ).scalar_one()
        assert directionality == "directed"

        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        assert "external_references" in tables
        assert "document_references" not in tables

    # Downgrade restores Paperless-shaped tables without losing the document link.
    command.downgrade(cfg, "0001_v01_semantic_core")
    with engine.connect() as conn:
        paperless_id = conn.execute(
            text(
                "SELECT paperless_document_id FROM document_references WHERE entity_id = :id"
            ),
            {"id": entity_id},
        ).scalar_one()
        assert paperless_id == 184
        origin = conn.execute(
            text("SELECT origin FROM relationships WHERE id = :id"),
            {"id": relationship_id},
        ).scalar_one()
        assert origin == "rule"
        target = conn.execute(
            text("SELECT target_concept_id FROM relationships WHERE id = :id"),
            {"id": relationship_id},
        ).scalar_one()
        assert target == concept_id

    os.environ.pop("ATLASDOCS_SQLALCHEMY_URL", None)
