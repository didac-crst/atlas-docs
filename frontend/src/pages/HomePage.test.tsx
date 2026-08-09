import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    fetchHome: vi.fn(async () => ({
      needs_classification: { count: 1, capped: false, unavailable: false },
      needs_review: { count: 0, capped: false, unavailable: false },
      failed_ingestion: { count: 0, capped: false, unavailable: false },
      reconciliation_issues: { count: 2, capped: false, unavailable: false },
      recent_documents: [],
      recent_knowledge: [],
    })),
  };
});

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

describe("HomePage", () => {
  it("sends global search to Explore with q", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route
            path="/"
            element={<HomePage session={{ authenticated: true, csrf_token: "csrf" }} />}
          />
          <Route path="/explore" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: /^Work areas$/i })).toBeInTheDocument();
    expect(screen.getByText(/Where evidence becomes knowledge/i)).toBeInTheDocument();
    const input = screen.getByLabelText(/Search anything/i);
    fireEvent.change(input, { target: { value: "Alice" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/explore?q=Alice");
    });
  });
});
