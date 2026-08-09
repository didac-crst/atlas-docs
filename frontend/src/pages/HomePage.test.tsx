import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    const user = userEvent.setup();

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

    await screen.findByRole("heading", { name: /^Work areas$/i });
    await user.type(screen.getByLabelText(/Search documents and concepts/i), "Alice");
    await user.click(screen.getByRole("button", { name: /^Search$/i }));
    expect(screen.getByTestId("location")).toHaveTextContent("/explore?q=Alice");
  });
});
