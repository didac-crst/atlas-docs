"""Correlation title_search and documented task id field contract tests."""

from __future__ import annotations

import json

import pytest

from atlasdocs.services.paperless import (
    PaperlessClient,
    _extract_document_ids_from_task_row,
)
from tests.fakes import FakePaperlessTransport


@pytest.fixture()
def transport() -> FakePaperlessTransport:
    return FakePaperlessTransport()


@pytest.fixture()
def client(transport: FakePaperlessTransport) -> PaperlessClient:
    return PaperlessClient(base_url="http://paperless.test", transport=transport)


def test_extract_document_ids_from_v10_task_shapes() -> None:
    assert _extract_document_ids_from_task_row(
        {
            "status": "success",
            "related_document_ids": [42],
            "result_data": {"document_id": 42},
        }
    ) == [42]
    assert _extract_document_ids_from_task_row(
        {"related_document": 7, "related_document_ids": [7, 8]}
    ) == [7, 8]
    assert _extract_document_ids_from_task_row(
        {"result_data": {"duplicate_of": 99}}
    ) == [99]
    assert _extract_document_ids_from_task_row(
        {"result": json.dumps({"document_id": 12})}
    ) == [12]
    assert _extract_document_ids_from_task_row({"result": "55"}) == [55]
    assert _extract_document_ids_from_task_row(
        {"status": "SUCCESS", "related_document_ids": [], "result_data": None}
    ) == []


def test_title_search_correlation_exact_one(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.documents[901] = {"id": 901, "title": "atlasdocs:job-1"}
    transport.documents[902] = {"id": 902, "title": "other atlasdocs:job-1 noise"}
    found = client.find_document_id_by_correlation_title("Token t", "atlasdocs:job-1")
    assert found == 901


def test_title_search_zero_matches(client: PaperlessClient) -> None:
    assert client.find_document_id_by_correlation_title("Token t", "atlasdocs:missing") is None


def test_title_search_multiple_exact_matches_returns_none(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.documents[901] = {"id": 901, "title": "atlasdocs:dup"}
    transport.documents[902] = {"id": 902, "title": "atlasdocs:dup"}
    assert client.find_document_id_by_correlation_title("Token t", "atlasdocs:dup") is None


def test_title_search_mismatched_substring_only_returns_none(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    # title_search may return substring hits; exact title must still match.
    transport.documents[901] = {"id": 901, "title": "prefix-atlasdocs:job-1-suffix"}
    assert client.find_document_id_by_correlation_title("Token t", "atlasdocs:job-1") is None


def test_title_search_cross_page_duplicate_exact_titles_returns_none(
    client: PaperlessClient, transport: FakePaperlessTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    import atlasdocs.services.paperless as paperless_mod

    monkeypatch.setattr(paperless_mod, "_TITLE_SEARCH_PAGE_SIZE", 1)
    transport.documents[901] = {"id": 901, "title": "atlasdocs:paged"}
    transport.documents[902] = {"id": 902, "title": "atlasdocs:paged"}
    assert client.find_document_id_by_correlation_title("Token t", "atlasdocs:paged") is None


def test_title_search_exact_match_on_second_page(
    client: PaperlessClient, transport: FakePaperlessTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    import atlasdocs.services.paperless as paperless_mod

    monkeypatch.setattr(paperless_mod, "_TITLE_SEARCH_PAGE_SIZE", 1)
    # Substring-only hit on page 1, exact correlation on page 2.
    transport.documents[901] = {"id": 901, "title": "noise-atlasdocs:paged-ok"}
    transport.documents[902] = {"id": 902, "title": "atlasdocs:paged-ok"}
    assert client.find_document_id_by_correlation_title("Token t", "atlasdocs:paged-ok") == 902
