import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EntityDetailPage } from "../pages/EntityDetailPage";

const fetchEntity = vi.fn();

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    fetchEntity: (...args: unknown[]) => fetchEntity(...args),
  };
});

describe("EntityDetailPage", () => {
  beforeEach(() => {
    fetchEntity.mockReset();
  });

  it("shows identity, related documents, and backlinks", async () => {
    fetchEntity.mockResolvedValue({
      id: "person-1",
      entity_type: "concept",
      label: "Alice",
      paperless_document_id: null,
      title: "Alice",
      created_date: null,
      correspondent: null,
      document_type: null,
      open_url: null,
      relationships: [],
      display_type: "person",
      semantic_completeness: "empty",
      backlinks: [
        {
          id: "bl-1",
          type: "concerns-person",
          source: "Payslip Germany",
          source_entity_id: "doc-ent",
          origin: "manual",
          status: "confirmed",
          source_paperless_document_id: 184,
        },
      ],
      related_documents: [
        {
          paperless_document_id: 184,
          entity_id: "doc-ent",
          label: "Payslip Germany",
          created_date: "2024-01-15",
          relationship_type: "concerns-person",
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/entities/person-1"]}>
        <Routes>
          <Route
            path="/entities/:entityId"
            element={<EntityDetailPage session={{ authenticated: true, csrf_token: "csrf" }} />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: /^Alice$/i })).toBeInTheDocument();
    expect(screen.getByText(/Semantic completeness: Empty/i)).toBeInTheDocument();
    const docLinks = screen.getAllByRole("link", { name: /Payslip Germany/i });
    expect(docLinks.length).toBeGreaterThanOrEqual(1);
    expect(docLinks[0]).toHaveAttribute("href", "/documents/184");
    expect(screen.getAllByText(/concerns-person/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Provenance: manual/i).length).toBeGreaterThanOrEqual(1);
  });
});
