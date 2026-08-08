"""Deterministic Paperless ↔ AtlasDocs reconciliation (no automatic deletes)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from atlasdocs.db.models import EXTERNAL_SYSTEM_PAPERLESS
from atlasdocs.services.documents import DocumentService
from atlasdocs.services.paperless import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessNotFoundError,
    PaperlessUnavailableError,
)


@dataclass
class ReconcileSummary:
    dry_run: bool
    limit: int | None
    paperless_documents_seen: int = 0
    created: list[int] = field(default_factory=list)
    already_present: list[int] = field(default_factory=list)
    missing_in_paperless: list[int] = field(default_factory=list)
    inaccessible_in_paperless: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def already_present_count(self) -> int:
        return len(self.already_present)

    def to_dict(self) -> dict:
        return asdict(self)

    def human_summary(self) -> str:
        mode = "dry-run" if self.dry_run else "apply"
        lines = [
            f"AtlasDocs reconcile ({mode})",
            f"  Paperless documents seen: {self.paperless_documents_seen}",
            f"  Created references: {self.created_count}",
            f"  Already present: {self.already_present_count}",
            f"  Missing in Paperless: {len(self.missing_in_paperless)}",
            f"  Inaccessible in Paperless: {len(self.inaccessible_in_paperless)}",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
        lines.append("  Semantic data was not deleted.")
        return "\n".join(lines)


class ReconcileService:
    """Reusable reconciliation abstraction for CLI and future webhook callers."""

    def __init__(self, session: Session, paperless: PaperlessClient) -> None:
        self._session = session
        self._paperless = paperless
        self._documents = DocumentService(session, paperless)

    def reconcile(
        self,
        token: str,
        *,
        dry_run: bool = False,
        limit: int | None = None,
        page_size: int = 100,
    ) -> ReconcileSummary:
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1")

        summary = ReconcileSummary(dry_run=dry_run, limit=limit)
        seen_ids: set[int] = set()

        try:
            for doc in self._paperless.iter_all_documents(
                token, page_size=page_size, limit=limit
            ):
                summary.paperless_documents_seen += 1
                seen_ids.add(doc.id)
                existing = self._documents.get_external_reference(doc.id)
                if existing is not None:
                    summary.already_present.append(doc.id)
                    continue
                if dry_run:
                    summary.created.append(doc.id)
                    continue
                self._documents.get_or_create_document_entity(doc.id)
                summary.created.append(doc.id)
            if not dry_run:
                self._session.flush()
        except (PaperlessAuthError, PaperlessNotFoundError, PaperlessUnavailableError) as exc:
            summary.errors.append(str(exc))
            return summary

        refs = self._documents.list_paperless_external_references()
        for ref in refs:
            try:
                paperless_id = int(ref.external_id)
            except ValueError:
                summary.errors.append(
                    f"Non-integer Paperless external_id on entity {ref.entity_id}"
                )
                continue
            if paperless_id in seen_ids:
                # Already confirmed via the listing scan; avoid a second GET.
                continue
            if limit is not None:
                # Limited runs only create/scan; orphan verification needs a full pass.
                continue
            try:
                self._paperless.assert_accessible(paperless_id, token=token)
            except PaperlessNotFoundError:
                summary.missing_in_paperless.append(paperless_id)
            except PaperlessAuthError:
                summary.inaccessible_in_paperless.append(paperless_id)
            except PaperlessUnavailableError as exc:
                summary.errors.append(f"Paperless {paperless_id}: {exc}")

        summary.missing_in_paperless.sort()
        summary.inaccessible_in_paperless.sort()
        summary.created.sort()
        summary.already_present.sort()
        return summary
