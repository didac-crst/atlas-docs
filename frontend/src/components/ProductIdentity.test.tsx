import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppFooter } from "./AppFooter";
import { ProductIdentity } from "./ProductIdentity";
import { PRODUCT_SLOGAN } from "../brand";

describe("ProductIdentity", () => {
  it("renders AtlasDocs name and slogan", () => {
    render(<ProductIdentity titleId="identity-title" />);
    expect(screen.getByRole("heading", { name: /^AtlasDocs$/i })).toHaveAttribute(
      "id",
      "identity-title",
    );
    expect(screen.getByText(PRODUCT_SLOGAN)).toBeInTheDocument();
  });

  it("can show a connecting status without internal service names", () => {
    render(<ProductIdentity status="Connecting…" />);
    expect(screen.getByText(/Connecting…/i)).toBeInTheDocument();
    expect(screen.queryByText(/paperless/i)).toBeNull();
    expect(screen.queryByText(/docker/i)).toBeNull();
  });
});

describe("AppFooter", () => {
  it("keeps Paperless acknowledgement secondary", () => {
    render(
      <MemoryRouter>
        <AppFooter />
      </MemoryRouter>,
    );
    expect(screen.getByText(/^AtlasDocs$/i)).toBeInTheDocument();
    expect(screen.getByText(PRODUCT_SLOGAN)).toBeInTheDocument();
    expect(screen.getByText(/Powered by Paperless-ngx/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^About$/i })).toHaveAttribute("href", "/about");
  });
});
