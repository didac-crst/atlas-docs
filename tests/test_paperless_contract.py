"""Contract tests pinning FakePaperless shapes for token / post_document / tasks."""

from __future__ import annotations

import io

import pytest

from atlasdocs.services.paperless import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessDuplicateError,
    PaperlessUnavailableError,
    _filename_from_content_disposition,
)
from tests.fakes import FakePaperlessTransport


@pytest.fixture()
def transport() -> FakePaperlessTransport:
    return FakePaperlessTransport()


@pytest.fixture()
def client(transport: FakePaperlessTransport) -> PaperlessClient:
    return PaperlessClient(base_url="http://paperless.test", transport=transport)


def test_filename_from_content_disposition_rfc5987() -> None:
    assert (
        _filename_from_content_disposition("attachment; filename*=UTF-8''rapport%20final.pdf")
        == "rapport final.pdf"
    )
    assert (
        _filename_from_content_disposition('attachment; filename="plain.pdf"') == "plain.pdf"
    )


def test_token_exchange_success_shape(client: PaperlessClient, transport: FakePaperlessTransport) -> None:
    transport.next_token = "contract-token-abc"
    token = client.exchange_password("ada", "correct-horse")
    assert token == "contract-token-abc"
    assert any("/api/token/" in call or "/api/token?" in call for call in transport.calls)
    post_calls = [c for c in transport.calls if "POST" in c and "token" in c]
    assert post_calls


def test_token_exchange_invalid_credentials(client: PaperlessClient) -> None:
    with pytest.raises(PaperlessAuthError):
        client.exchange_password("ada", "wrong")


def test_post_document_returns_task_id(client: PaperlessClient, transport: FakePaperlessTransport) -> None:
    task_id = client.post_document(
        "Token test",
        filename="payslip.pdf",
        content=io.BytesIO(b"%PDF-1.4 sample"),
        content_type="application/pdf",
    )
    assert task_id
    assert task_id in transport.tasks
    assert transport.uploaded_files
    assert transport.uploaded_files[-1]["filename"] == "payslip.pdf"


def test_post_document_duplicate_maps_error(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.post_document_duplicate = True
    with pytest.raises(PaperlessDuplicateError):
        client.post_document("Token test", filename="dup.pdf", content=b"same")


def test_post_document_server_error(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.post_document_server_error = True
    with pytest.raises(PaperlessUnavailableError):
        client.post_document("Token test", filename="x.pdf", content=b"x")


def test_get_task_success_payload(client: PaperlessClient, transport: FakePaperlessTransport) -> None:
    task_id = client.post_document("Token test", filename="a.pdf", content=b"abc")
    status = client.get_task(task_id, "Token test")
    assert status.task_id == task_id
    assert status.status == "SUCCESS"
    assert status.related_document_id is not None
    assert status.related_document_id in transport.documents


def test_get_task_pending(client: PaperlessClient, transport: FakePaperlessTransport) -> None:
    transport.task_auto_succeed = False
    task_id = client.post_document("Token test", filename="a.pdf", content=b"abc")
    status = client.get_task(task_id, "Token test")
    assert status.status == "PENDING"
    assert status.related_document_id is None


def test_get_task_result_data_document_id(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.success_document_id_in_result_data = True
    task_id = client.post_document("Token test", filename="a.pdf", content=b"abc")
    status = client.get_task(task_id, "Token test")
    assert status.status == "SUCCESS"
    assert status.related_document_id is not None
    assert status.result_data == {"document_id": status.related_document_id}


def test_get_task_related_document_ids(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.success_via_related_document_ids = True
    task_id = client.post_document("Token test", filename="a.pdf", content=b"abc")
    status = client.get_task(task_id, "Token test")
    assert status.status == "SUCCESS"
    assert status.related_document_ids
    assert PaperlessClient.primary_document_id(status) == status.related_document_ids[0]


def test_get_task_json_result_document_id(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.success_via_json_result = True
    task_id = client.post_document("Token test", filename="a.pdf", content=b"abc")
    status = client.get_task(task_id, "Token test")
    assert status.status == "SUCCESS"
    assert PaperlessClient.primary_document_id(status) is not None


def test_get_task_success_without_document_id(
    client: PaperlessClient, transport: FakePaperlessTransport
) -> None:
    transport.omit_related_document_on_success = True
    task_id = client.post_document("Token test", filename="a.pdf", content=b"abc")
    status = client.get_task(task_id, "Token test")
    assert status.status == "SUCCESS"
    assert PaperlessClient.primary_document_id(status) is None
