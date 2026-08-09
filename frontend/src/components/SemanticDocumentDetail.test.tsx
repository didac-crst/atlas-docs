import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  documentContextLine,
  documentDisplayTitle,
  SemanticDocumentDetail,
} from "./SemanticDocumentDetail";

const baseDoc = {
  paperless_document_id: 184,
  entity_id: "entity-1",
  title: "Payslip Germany",
  created_date: "2024-01-15",
  correspondent: "Acme Payroll",
  document_type: "Payslip",
  open_url: null as string | null,
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
  it("renders preview, download, and advanced Paperless actions", () => {
    render(
      <SemanticDocumentDetail
        document={{ ...baseDoc, open_url: "https://docs.example.test/documents/184/" }}
        csrfToken="csrf"
        onRemoved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    const preview = screen.getByRole("link", { name: /^Preview$/i });
    expect(preview).toHaveAttribute("href", "/ui/api/documents/184/preview");
    expect(preview).toHaveAttribute("target", "_blank");
    expect(preview).toHaveAttribute("rel", expect.stringContaining("noopener"));

    const download = screen.getByRole("link", { name: /^Download$/i });
    expect(download).toHaveAttribute("href", "/ui/api/documents/184/download");

    const paperless = screen.getByRole("link", { name: /Open original in Paperless/i });
    expect(paperless).toHaveAttribute("href", "https://docs.example.test/documents/184/");
    expect(paperless).toHaveClass("btn-ghost");
    expect(screen.getByText("Payslip · Acme Payroll · 2024")).toBeInTheDocument();
    expect(screen.getByText(/Technical details/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Document 184$/)).toBeNull();
  });

  it("disables Paperless action when open_url is missing", () => {
    render(
      <SemanticDocumentDetail
        document={{ ...baseDoc, open_url: null }}
        csrfToken="csrf"
        onRemoved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: /Open original in Paperless/i });
    expect(button).toBeDisabled();
    expect(screen.queryByRole("link", { name: /Open original in Paperless/i })).toBeNull();
    expect(screen.getByRole("link", { name: /^Preview$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Download$/i })).toBeInTheDocument();
  });

  it("keeps Paperless id in collapsed technical details only", () => {
    render(
      <SemanticDocumentDetail
        document={{ ...baseDoc, title: null, open_url: null }}
        csrfToken="csrf"
        onRemoved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { name: "Untitled document" })).toBeInTheDocument();
    expect(screen.getByText("184")).toBeInTheDocument();
    expect(screen.getByText("entity-1")).toBeInTheDocument();
  });
});
