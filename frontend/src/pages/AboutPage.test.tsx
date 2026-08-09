import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AboutPage } from "./AboutPage";
import { PRODUCT_SLOGAN } from "../brand";

describe("AboutPage", () => {
  it("shows product identity, stack, and optional manifesto", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AboutPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /^AtlasDocs$/i })).toBeInTheDocument();
    expect(screen.getByText(PRODUCT_SLOGAN)).toBeInTheDocument();
    expect(screen.getByText(/transforms document archives into connected knowledge/i)).toBeInTheDocument();
    expect(screen.getByText(/Paperless-ngx/i)).toBeInTheDocument();
    expect(screen.getByText(/PostgreSQL/i)).toBeInTheDocument();
    expect(screen.getByText(/Valkey/i)).toBeInTheDocument();

    await user.click(screen.getByText(/Product manifesto/i));
    expect(screen.getByText(/Documents are static/i)).toBeInTheDocument();
    expect(screen.getByText(/Knowledge is connected/i)).toBeInTheDocument();
  });
});
