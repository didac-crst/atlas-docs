"""Central entity display-type registry for Explore and relationship constraints.

Person/Organization/Country/Case remain concept entities in the database; the
registry maps them to product-facing browse types without expanding EntityType.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityTypeInfo:
    code: str
    label: str
    icon: str
    searchable: bool
    valid_relationship_target: bool
    has_dedicated_page: bool
    """Ontology code when this display type is backed by concepts; None for documents."""
    ontology_code: str | None = None


ENTITY_TYPE_REGISTRY: tuple[EntityTypeInfo, ...] = (
    EntityTypeInfo(
        code="document",
        label="Document",
        icon="file-text",
        searchable=True,
        valid_relationship_target=True,
        has_dedicated_page=True,
        ontology_code=None,
    ),
    EntityTypeInfo(
        code="person",
        label="Person",
        icon="user",
        searchable=True,
        valid_relationship_target=True,
        has_dedicated_page=True,
        ontology_code="person",
    ),
    EntityTypeInfo(
        code="organization",
        label="Organization",
        icon="building",
        searchable=True,
        valid_relationship_target=True,
        has_dedicated_page=True,
        ontology_code="organization",
    ),
    EntityTypeInfo(
        code="country",
        label="Country",
        icon="globe",
        searchable=True,
        valid_relationship_target=True,
        has_dedicated_page=True,
        ontology_code="country",
    ),
    EntityTypeInfo(
        code="case",
        label="Case",
        icon="briefcase",
        searchable=True,
        valid_relationship_target=True,
        has_dedicated_page=True,
        ontology_code="case",
    ),
    EntityTypeInfo(
        code="concept",
        label="Concept",
        icon="tag",
        searchable=True,
        valid_relationship_target=True,
        has_dedicated_page=True,
        ontology_code=None,
    ),
)

_BY_CODE: dict[str, EntityTypeInfo] = {item.code: item for item in ENTITY_TYPE_REGISTRY}

# Ontology codes that map to a dedicated registry type (not generic "concept").
_ONTOLOGY_TO_REGISTRY: dict[str, str] = {
    item.ontology_code: item.code
    for item in ENTITY_TYPE_REGISTRY
    if item.ontology_code is not None
}

REGISTRY_TYPE_CODES: frozenset[str] = frozenset(_BY_CODE)
EXPLORE_MODE_CODES: frozenset[str] = frozenset({"all", *REGISTRY_TYPE_CODES})


def get_entity_type(code: str) -> EntityTypeInfo | None:
    return _BY_CODE.get((code or "").strip().lower())


def list_entity_types() -> list[EntityTypeInfo]:
    return list(ENTITY_TYPE_REGISTRY)


def registry_code_for_ontology(ontology_code: str | None) -> str:
    if not ontology_code:
        return "concept"
    return _ONTOLOGY_TO_REGISTRY.get(ontology_code, "concept")


def ontology_for_registry_code(code: str) -> str | None:
    info = get_entity_type(code)
    if info is None:
        return None
    return info.ontology_code
