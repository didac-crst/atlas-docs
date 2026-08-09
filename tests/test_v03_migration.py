"""Alembic upgrade preserves v0.1/v0.2 semantic data into the v0.3 model."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_URL = os.environ.get("ATLASDOCS_TEST_DATABASE_URL", "").strip()


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _seed_v01_graph(engine: Engine) -> dict[str, str]:
    """Seed two Paperless docs (184, 197) with preserved entity/relationship ids."""
    ontology_id = str(uuid.uuid4())
    concept_id = str(uuid.uuid4())
    entity_184 = str(uuid.uuid4())
    entity_197 = str(uuid.uuid4())
    ref_184 = str(uuid.uuid4())
    ref_197 = str(uuid.uuid4())
    rel_type_id = str(uuid.uuid4())
    relationship_184 = str(uuid.uuid4())
    relationship_197 = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO ontologies (id, code, name) VALUES (:id, 'country', 'Country')"),
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
        for entity_id in (entity_184, entity_197):
            conn.execute(
                text("INSERT INTO entities (id, created_at) VALUES (:id, CURRENT_TIMESTAMP)"),
                {"id": entity_id},
            )
        conn.execute(
            text(
                """
                INSERT INTO document_references
                    (id, entity_id, paperless_document_id, created_at)
                VALUES
                    (:id_184, :entity_184, 184, CURRENT_TIMESTAMP),
                    (:id_197, :entity_197, 197, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id_184": ref_184,
                "entity_184": entity_184,
                "id_197": ref_197,
                "entity_197": entity_197,
            },
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
                ) VALUES
                    (:id_184, :entity_184, :type_id, :concept_id, 'rule', 'confirmed', CURRENT_TIMESTAMP),
                    (:id_197, :entity_197, :type_id, :concept_id, 'manual', 'confirmed', CURRENT_TIMESTAMP)
                """
            ),
            {
                "id_184": relationship_184,
                "entity_184": entity_184,
                "id_197": relationship_197,
                "entity_197": entity_197,
                "type_id": rel_type_id,
                "concept_id": concept_id,
            },
        )

    return {
        "ontology_id": ontology_id,
        "concept_id": concept_id,
        "entity_184": entity_184,
        "entity_197": entity_197,
        "ref_184": ref_184,
        "ref_197": ref_197,
        "rel_type_id": rel_type_id,
        "relationship_184": relationship_184,
        "relationship_197": relationship_197,
    }


def _assert_v03_preserved(engine: Engine, ids: dict[str, str]) -> None:
    with engine.connect() as conn:
        for entity_id, expected_type in (
            (ids["entity_184"], "document"),
            (ids["entity_197"], "document"),
            (ids["concept_id"], "concept"),
        ):
            assert (
                conn.execute(
                    text("SELECT entity_type FROM entities WHERE id = :id"),
                    {"id": entity_id},
                ).scalar_one()
                == expected_type
            )

        refs = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                text(
                    """
                    SELECT external_id, entity_id
                    FROM external_references
                    WHERE system = 'paperless'
                    ORDER BY external_id
                    """
                )
            )
        }
        assert refs == {
            "184": ids["entity_184"],
            "197": ids["entity_197"],
        }

        rel_184 = conn.execute(
            text(
                """
                SELECT source_entity_id, target_entity_id, origin
                FROM relationships WHERE id = :id
                """
            ),
            {"id": ids["relationship_184"]},
        ).one()
        assert (str(rel_184[0]), str(rel_184[1]), rel_184[2]) == (
            ids["entity_184"],
            ids["concept_id"],
            "deterministic-rule",
        )

        rel_197 = conn.execute(
            text(
                """
                SELECT source_entity_id, target_entity_id, origin
                FROM relationships WHERE id = :id
                """
            ),
            {"id": ids["relationship_197"]},
        ).one()
        assert (str(rel_197[0]), str(rel_197[1]), rel_197[2]) == (
            ids["entity_197"],
            ids["concept_id"],
            "manual",
        )

    tables = set(sa_inspect(engine).get_table_names())
    assert "external_references" in tables
    assert "document_references" not in tables


@pytest.fixture()
def sqlite_migration_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[str, Engine, Config]]:
    db_path = tmp_path / "migrate.db"
    db_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    monkeypatch.setenv("ATLASDOCS_SQLALCHEMY_URL", db_url)
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    engine = create_engine(db_url)
    cfg = _alembic_config(db_url)
    try:
        yield db_url, engine, cfg
    finally:
        engine.dispose()


def test_sqlite_upgrade_preserves_entities_and_references_184_197(
    sqlite_migration_env: tuple[str, Engine, Config],
) -> None:
    _db_url, engine, cfg = sqlite_migration_env
    command.upgrade(cfg, "0001_v01_semantic_core")
    ids = _seed_v01_graph(engine)
    command.upgrade(cfg, "head")
    _assert_v03_preserved(engine, ids)

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "0007_semantic_completeness_constraints"


def test_sqlite_downgrade_round_trips_when_safe(
    sqlite_migration_env: tuple[str, Engine, Config],
) -> None:
    _db_url, engine, cfg = sqlite_migration_env
    command.upgrade(cfg, "0001_v01_semantic_core")
    ids = _seed_v01_graph(engine)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001_v01_semantic_core")

    with engine.connect() as conn:
        paperless_ids = {
            int(row[0])
            for row in conn.execute(text("SELECT paperless_document_id FROM document_references"))
        }
        assert paperless_ids == {184, 197}
        assert (
            conn.execute(
                text("SELECT origin FROM relationships WHERE id = :id"),
                {"id": ids["relationship_184"]},
            ).scalar_one()
            == "rule"
        )
        assert (
            str(
                conn.execute(
                    text("SELECT target_concept_id FROM relationships WHERE id = :id"),
                    {"id": ids["relationship_197"]},
                ).scalar_one()
            )
            == ids["concept_id"]
        )


def test_sqlite_downgrade_fails_loudly_on_companion_edges(
    sqlite_migration_env: tuple[str, Engine, Config],
) -> None:
    _db_url, engine, cfg = sqlite_migration_env
    command.upgrade(cfg, "0001_v01_semantic_core")
    ids = _seed_v01_graph(engine)
    command.upgrade(cfg, "head")

    companion_type = str(uuid.uuid4())
    companion_rel = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO relationship_types (
                    id, code, name, target_ontology_id, directionality,
                    inverse_relationship_type_id
                ) VALUES (:id, 'answered-by', 'Answered By', NULL, 'directed', NULL)
                """
            ),
            {"id": companion_type},
        )
        conn.execute(
            text(
                """
                INSERT INTO relationships (
                    id, source_entity_id, relationship_type_id, target_entity_id,
                    origin, status, created_at
                ) VALUES (
                    :id, :source, :type_id, :target, 'manual', 'confirmed', CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": companion_rel,
                "source": ids["concept_id"],
                "type_id": companion_type,
                "target": ids["entity_184"],
            },
        )

    with pytest.raises(RuntimeError, match="Restore from a pre-upgrade database dump"):
        command.downgrade(cfg, "0001_v01_semantic_core")

    with engine.connect() as conn:
        # Semantic data must remain after the refused downgrade.
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM relationships WHERE id = :id"),
                {"id": companion_rel},
            ).scalar_one()
            == 1
        )
        assert (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0002_v03_entity_external_reference"
        )


def test_postgresql_compatible_backfill_sql_uses_set_based_insert() -> None:
    """Guard the PostgreSQL upgrade path without requiring a live server."""
    source = (
        REPO_ROOT / "alembic" / "versions" / "0002_v03_entity_external_reference.py"
    ).read_text(encoding="utf-8")
    assert "gen_random_uuid()" in source
    assert "paperless_document_id::text" in source
    assert "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)" in source
    assert 'if dialect == "postgresql"' in source
    assert 'if dialect == "sqlite"' in source
    assert "Refusing to downgrade" in source


@pytest.mark.skipif(not POSTGRES_URL, reason="ATLASDOCS_TEST_DATABASE_URL not set")
def test_postgres_upgrade_preserves_entities_and_references_184_197(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_url = POSTGRES_URL
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    monkeypatch.setenv("ATLASDOCS_SQLALCHEMY_URL", db_url)
    monkeypatch.setenv("SESSION_SECRET", "test-secret")

    engine = create_engine(db_url)
    cfg = _alembic_config(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

        command.upgrade(cfg, "0001_v01_semantic_core")
        ids = _seed_v01_graph(engine)
        command.upgrade(cfg, "head")
        _assert_v03_preserved(engine, ids)

        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            assert version == "0007_semantic_completeness_constraints"
            length = conn.execute(
                text(
                    """
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = 'alembic_version' AND column_name = 'version_num'
                    """
                )
            ).scalar_one()
            assert length == 64
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        engine.dispose()
