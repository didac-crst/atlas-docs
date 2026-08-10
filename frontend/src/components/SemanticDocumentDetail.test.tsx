import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  documentContextLine,
  documentDisplayTitle,
  SemanticDocumentDetail,
} from "./SemanticDocumentDetail";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    deleteDocument: vi.fn(),
    removeRelationship: vi.fn(),
    fetchDocument: vi.fn(),
    replaceDocument: vi.fn(),
    fetchIngestJob: vi.fn(),
  };
});

import { deleteDocument } from "../api/client";

const baseDoc = {
  paperless_document_id: 184,
  entity_id: "entity-1",
  title: "Payslip Germany",
  created_date: "2024-01-15",
  correspondent: "Acme Payroll",
  document_type: "Payslip",
  open_url: null as string | null,
  lifecycle_category: "evidence" as const,
  relationships: [] as {
    id: string;
    type: string;
    target: string;
    target_entity_id: string | null;
    origin: string;
    status: string;
    source_entity_id: string | null;
  }[],
};

describe("SemanticDocumentDetail helpers", () => {
  it("falls back to Untitled document without Paperless id titles", () => {
    expect(documentDisplayTitle({ title: null })).toBe("Untitled document");
    expect(documentDisplayTitle({ title: "  " })).toBe("Untitled document");
    expect(documentDisplayTitle({ title: "Payslip" })).toBe("Payslip");
  });

  it("builds context from relationships and year", () => {
    expect(
      documentContextLine({
        ...baseDoc,
        relationships: [
          {
            id: "1",
            type: "source-country",
            target: "Germany",
            target_entity_id: "c1",
            origin: "human",
            status: "active",
            source_entity_id: "s1",
          },
          {
            id: "2",
            type: "document-type",
            target: "Payslip",
            target_entity_id: "c2",
            origin: "human",
            status: "active",
            source_entity_id: "s1",
          },
          {
            id: "3",
            type: "issued-by",
            target: "Airbus",
            target_entity_id: "c3",
            origin: "human",
            status: "active",
            source_entity_id: "s1",
          },
        ],
        created_date: "2026-07-01",
      }),
    ).toBe("Germany · Payslip · Airbus · 2026");
  });
});

describe("SemanticDocumentDetail document actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders workbench preview and primary actions without Paperless ids", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SemanticDocumentDetail
          document={{ ...baseDoc, open_url: "https://docs.example.test/documents/184/" }}
          csrfToken="csrf"
          onRemoved={vi.fn()}
          onError={vi.fn()}
        />
      </MemoryRouter>,
    );
    const frame = document.querySelector("iframe.doc-preview-frame");
    expect(frame).not.toBeNull();
    expect(frame).toHaveAttribute("src", "/ui/api/documents/184/preview");
    // Empty sandbox blocks the browser PDF viewer; same-origin BFF is intentional.
    expect(frame).not.toHaveAttribute("sandbox");

    expect(screen.getByRole("link", { name: /^Download$/i })).toHaveAttribute(
      "href",
      "/ui/api/documents/184/download",
    );
    expect(screen.getByRole("button", { name: /^Move to trash$/i })).toBeInTheDocument();
    expect(screen.getByText("Payslip · Acme Payroll · 2024")).toBeInTheDocument();
    expect(screen.queryByText(/^Document 184$/)).toBeNull();

    await user.click(screen.getByRole("button", { name: /More actions/i }));
    expect(screen.getByRole("link", { name: /Open preview in new tab/i })).toHaveAttribute(
      "href",
      "/ui/api/documents/184/preview",
    );
    expect(screen.getByRole("link", { name: /Download original/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Paperless/i })).toHaveAttribute(
      "href",
      "https://docs.example.test/documents/184/",
    );
    expect(screen.getByRole("button", { name: /Replace document/i })).toBeInTheDocument();
  });

  it("disables Paperless action when open_url is missing", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SemanticDocumentDetail
          document={{ ...baseDoc, open_url: null }}
          csrfToken="csrf"
          onRemoved={vi.fn()}
          onError={vi.fn()}
        />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /More actions/i }));
    expect(screen.getByRole("button", { name: /Open in Paperless/i })).toBeDisabled();
    expect(screen.getByRole("link", { name: /Open preview in new tab/i })).toBeInTheDocument();
  });

  it("keeps Paperless id in collapsed technical details only", () => {
    render(
      <MemoryRouter>
        <SemanticDocumentDetail
          document={{ ...baseDoc, title: null, open_url: null }}
          csrfToken="csrf"
          onRemoved={vi.fn()}
          onError={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Untitled document" })).toBeInTheDocument();
    expect(screen.getByText("184")).toBeInTheDocument();
    expect(screen.getByText("entity-1")).toBeInTheDocument();
  });

  it("requires confirmation dialog before moving a document to trash", async () => {
    const user = userEvent.setup();
    const onDocumentDeleted = vi.fn(async () => undefined);
    vi.mocked(deleteDocument).mockResolvedValue(undefined as never);

    render(
      <MemoryRouter>
        <SemanticDocumentDetail
          document={{ ...baseDoc, open_url: null }}
          csrfToken="csrf"
          onRemoved={vi.fn()}
          onDocumentDeleted={onDocumentDeleted}
          onError={vi.fn()}
        />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /^Move to trash$/i }));
    expect(deleteDocument).not.toHaveBeenCalled();
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByText(/Move this document to trash/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Confirm move to trash$/i }));
    expect(deleteDocument).toHaveBeenCalledWith(184, "csrf", {
      confirm: true,
      permanent: false,
    });
    expect(onDocumentDeleted).toHaveBeenCalled();
  });
});
