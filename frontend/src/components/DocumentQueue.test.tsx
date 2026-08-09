import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ClassifyBatchBar } from "./ClassifyBatchBar";
import { DocumentCard } from "./DocumentCard";
import type { ExploreResultItem } from "../api/client";

function renderWithRouter(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const sampleItem: ExploreResultItem = {
  id: null,
  label: "Payslip Germany",
  entity_type: "document",
  semantic_completeness: "empty",
  subtitle: null,
  paperless_document_id: 184,
  open_url: null,
  preview_available: true,
  download_available: true,
  relationship_summary: [],
  created_date: "2024-01-15",
  correspondent: "Acme Payroll",
  document_type: "Payslip",
  thumbnail_available: true,
  relationship_count: 0,
};

describe("Classify collection primitives", () => {
  it("shows batch bar only when selection is non-empty", async () => {
    const onClear = vi.fn();
    const onAdd = vi.fn();
    const { rerender } = render(
      <ClassifyBatchBar selectedCount={0} onClear={onClear} onAddRelationship={onAdd} />,
    );
    expect(screen.queryByRole("region", { name: /Batch actions/i })).not.toBeInTheDocument();

    rerender(
      <ClassifyBatchBar selectedCount={3} onClear={onClear} onAddRelationship={onAdd} />,
    );
    expect(screen.getByRole("region", { name: /Batch actions/i })).toHaveTextContent(/3\s*selected/i);
    await userEvent.click(screen.getByRole("button", { name: /Add relationship/i }));
    expect(onAdd).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Clear selection/i }));
    expect(onClear).toHaveBeenCalled();
  });

  it("renders selectable document cards without Paperless ids as labels", async () => {
    const onPreview = vi.fn();
    const onToggle = vi.fn();
    renderWithRouter(
      <DocumentCard
        item={sampleItem}
        view="list"
        onPreview={onPreview}
        selectable
        selected={false}
        onToggleSelect={onToggle}
      />,
    );
    expect(screen.getByRole("button", { name: /^Payslip Germany$/i })).toBeInTheDocument();
    expect(screen.queryByText(/^184$/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /Select Payslip Germany/i }));
    expect(onToggle).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /^Preview$/i }));
    expect(onPreview).toHaveBeenCalledWith(184, "Payslip Germany");
  });
});
