import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { DocumentQueue } from "../components/DocumentQueue";

function renderQueue(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("DocumentQueue", () => {
  it("shows empty state with pagination", () => {
    renderQueue(
      <DocumentQueue
        queue={{
          items: [],
          page: 2,
          page_size: 25,
          paperless_count: 40,
          has_next: false,
          has_previous: true,
          next_page: null,
        }}
        selectedId={null}
        page={2}
        onSelect={() => undefined}
      />,
    );
    expect(screen.getByText(/No unclassified documents/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Previous/i })).toHaveAttribute("href", "/?page=1");
    expect(screen.getByText(/^Next$/i)).toBeInTheDocument();
  });

  it("renders queue items", () => {
    renderQueue(
      <DocumentQueue
        queue={{
          items: [
            {
              paperless_document_id: 184,
              title: "Payslip Germany",
              created_date: "2024-01-15",
              correspondent: "Acme Payroll",
              document_type: "Payslip",
            },
          ],
          page: 1,
          page_size: 25,
          paperless_count: 1,
          has_next: false,
          has_previous: false,
          next_page: null,
        }}
        selectedId={184}
        page={1}
        onSelect={() => undefined}
      />,
    );
    expect(screen.getByRole("button", { name: /Payslip Germany/i })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });
});
