import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DocumentQueue } from "../components/DocumentQueue";

function renderQueue(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const defaultFilters = {
  q: "",
  classification: "unclassified" as const,
  sort: "created" as const,
  order: "desc" as const,
  created_gte: "",
  created_lte: "",
  correspondent: "",
  document_type: "",
  tag: "",
  completeness: "any" as const,
};

const baseProps = {
  selectedId: null as number | null,
  page: 2,
  filters: defaultFilters,
  types: [],
  csrfToken: "csrf",
  pageHref: (p: number) => `/classify?page=${p}`,
  onSelect: () => undefined,
  onFiltersChange: () => undefined,
  onBulkDone: async () => undefined,
  onError: () => undefined,
};

describe("DocumentQueue", () => {
  it("shows empty state with pagination under /classify", () => {
    renderQueue(
      <DocumentQueue
        {...baseProps}
        queue={{
          items: [],
          page: 2,
          page_size: 25,
          paperless_count: 40,
          has_next: false,
          has_previous: true,
          next_page: null,
        }}
      />,
    );
    expect(screen.getByText(/No unclassified documents/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Previous/i })).toHaveAttribute(
      "href",
      "/classify?page=1",
    );
    expect(screen.getByText(/^Next$/i)).toBeInTheDocument();
  });

  it("renders queue items and filter controls without Paperless ids as labels", () => {
    renderQueue(
      <DocumentQueue
        {...baseProps}
        page={1}
        pageHref={(p) => `/classify?page=${p}`}
        selectedId={184}
        queue={{
          items: [
            {
              paperless_document_id: 184,
              title: "Payslip Germany",
              created_date: "2024-01-15",
              correspondent: "Acme Payroll",
              document_type: "Payslip",
            },
            {
              paperless_document_id: 185,
              title: null,
              created_date: null,
              correspondent: null,
              document_type: null,
            },
          ],
          page: 1,
          page_size: 25,
          paperless_count: 2,
          has_next: false,
          has_previous: false,
          next_page: null,
        }}
      />,
    );
    expect(screen.getByRole("button", { name: /Payslip Germany/i })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByRole("button", { name: /Untitled document/i })).toBeInTheDocument();
    expect(screen.queryByText(/Document 185/i)).toBeNull();
    expect(screen.queryByText(/Paperless #/i)).toBeNull();
    expect(screen.getByLabelText(/^Search$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Date from$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Date to$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Correspondent$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Document type$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Tag$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Classification$/i)).toHaveValue("unclassified");
    expect(screen.getByLabelText(/^Completeness$/i)).toHaveValue("any");
    expect(screen.getByLabelText(/^Sort$/i)).toHaveValue("newest");
  });

  it("notifies parent when classification filter changes", async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();
    renderQueue(
      <DocumentQueue
        {...baseProps}
        page={1}
        onFiltersChange={onFiltersChange}
        queue={{
          items: [],
          page: 1,
          page_size: 25,
          paperless_count: 0,
          has_next: false,
          has_previous: false,
          next_page: null,
        }}
      />,
    );
    await user.selectOptions(screen.getByLabelText(/^Classification$/i), "any");
    expect(onFiltersChange).toHaveBeenCalledWith({ classification: "any", page: 1 });
  });

  it("maps sort presets to sort and order", async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();
    renderQueue(
      <DocumentQueue
        {...baseProps}
        page={1}
        onFiltersChange={onFiltersChange}
        queue={{
          items: [],
          page: 1,
          page_size: 25,
          paperless_count: 0,
          has_next: false,
          has_previous: false,
          next_page: null,
        }}
      />,
    );
    await user.selectOptions(screen.getByLabelText(/^Sort$/i), "correspondent");
    expect(onFiltersChange).toHaveBeenCalledWith({
      sort: "correspondent",
      order: "asc",
      page: 1,
    });
  });
});
