import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SemanticDocumentDetail } from "./SemanticDocumentDetail";

const baseDoc = {
  paperless_document_id: 184,
  entity_id: "entity-1",
  title: "Payslip Germany",
  created_date: "2024-01-15",
  correspondent: "Acme Payroll",
  document_type: "Payslip",
  relationships: [],
};

describe("SemanticDocumentDetail Open in Paperless", () => {
  it("renders an external link when open_url is present", () => {
    render(
      <SemanticDocumentDetail
        document={{ ...baseDoc, open_url: "https://docs.example.test/documents/184/" }}
        csrfToken="csrf"
        onRemoved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    const link = screen.getByRole("link", { name: /Open in Paperless/i });
    expect(link).toHaveAttribute("href", "https://docs.example.test/documents/184/");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("disables the action when open_url is missing", () => {
    render(
      <SemanticDocumentDetail
        document={{ ...baseDoc, open_url: null }}
        csrfToken="csrf"
        onRemoved={vi.fn()}
        onError={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: /Open in Paperless/i });
    expect(button).toBeDisabled();
    expect(screen.queryByRole("link", { name: /Open in Paperless/i })).toBeNull();
  });
});
