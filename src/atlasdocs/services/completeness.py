"""Explainable semantic completeness for AtlasDocs entities.

States (v0.6):
  empty         — no confirmed semantic relationships
  partial       — some confirmed semantics; configured minimum incomplete
  classified    — configured minimum semantics present
  needs_review  — suggested/unresolved review work present
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

COMPLETENESS_STATES = frozenset({"empty", "partial", "classified", "needs_review"})

# Minimum confirmed relationship-type groups for "classified".
# Each inner set is OR within the group; all groups must be satisfied (AND).
DOCUMENT_CLASSIFIED_REQUIREMENTS: tuple[frozenset[str], ...] = (
    frozenset({"document-type"}),
)

# Concept-backed types have no required relationships in v0.6.
CONCEPT_CLASSIFIED_REQUIREMENTS: tuple[frozenset[str], ...] = ()


@dataclass(frozen=True)
class CompletenessInput:
    registry_type: str
    confirmed_relationship_codes: frozenset[str]
    has_suggested_relationships: bool


def requirements_for_registry_type(registry_type: str) -> tuple[frozenset[str], ...]:
    if registry_type == "document":
        return DOCUMENT_CLASSIFIED_REQUIREMENTS
    return CONCEPT_CLASSIFIED_REQUIREMENTS


def meets_requirements(
    confirmed: Iterable[str],
    groups: tuple[frozenset[str], ...],
) -> bool:
    if not groups:
        return True
    confirmed_set = set(confirmed)
    return all(confirmed_set & group for group in groups)


def calculate_completeness(payload: CompletenessInput) -> str:
    if payload.has_suggested_relationships:
        return "needs_review"
    if not payload.confirmed_relationship_codes:
        return "empty"
    required = requirements_for_registry_type(payload.registry_type)
    if meets_requirements(payload.confirmed_relationship_codes, required):
        return "classified"
    return "partial"
