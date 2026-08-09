import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ExploreResultCard } from "./ExploreResultCard";

const docItem = {
  id: "ent-1",
  label: "Payslip Germany",
  entity_type: "document",
  semantic_completeness: "partial",
  subtitle: "2024-01-15 · Acme Payroll",
  paperless_document_id: 184,
  open_url: null,
  preview_available: true,
  download_available: true,
  relationship_summary: ["document-type: Payslip"],
  created_date: "2024-01-15",
  correspondent: "Acme Payroll",
  document_type: "Payslip",
};

describe("ExploreResultCard", () => {
  it("links documents to detail and exposes preview/download", () => {
    render(
      <MemoryRouter>
        <ExploreResultCard item={docItem} view="list" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: /Payslip Germany/i })).toHaveAttribute(
      "href",
      "/documents/184",
    );
    expect(screen.getByRole("link", { name: /^Preview$/i })).toHaveAttribute(
      "href",
      "/ui/api/documents/184/preview",
    );
    expect(screen.getByRole("link", { name: /^Download$/i })).toHaveAttribute(
      "href",
      "/ui/api/documents/184/download",
    );
    expect(screen.getByText(/document-type: Payslip/i)).toBeInTheDocument();
    expect(screen.queryByText("184")).toBeNull();
  });

  it("renders non-document entities without detail link", () => {
    render(
      <MemoryRouter>
        <ExploreResultCard
          item={{
            ...docItem,
            id: "person-1",
            label: "Alice",
            entity_type: "person",
            paperless_document_id: null,
            preview_available: false,
            download_available: false,
            relationship_summary: [],
            subtitle: "person",
          }}
          view="grid"
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Alice/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^Preview$/i })).toBeNull();
  });
});
