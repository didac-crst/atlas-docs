import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AboutPage } from "./AboutPage";
import { PRODUCT_SLOGAN } from "../brand";

describe("AboutPage", () => {
  it("shows product identity, stack, and editorial manifesto without Back to Home", () => {
    render(
      <MemoryRouter>
        <AboutPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /^AtlasDocs$/i })).toBeInTheDocument();
    expect(screen.getAllByText(PRODUCT_SLOGAN).length).toBeGreaterThan(0);
    expect(screen.getByText(/transforms document archives into connected knowledge/i)).toBeInTheDocument();
    expect(screen.getByText(/Paperless-ngx/i)).toBeInTheDocument();
    expect(screen.getByText(/PostgreSQL/i)).toBeInTheDocument();
    expect(screen.getByText(/Valkey/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Product manifesto/i })).toBeInTheDocument();
    expect(screen.getByText(/Documents are static/i)).toBeInTheDocument();
    expect(screen.getByText(/Knowledge is connected/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Back to Home/i })).not.toBeInTheDocument();
  });
});
