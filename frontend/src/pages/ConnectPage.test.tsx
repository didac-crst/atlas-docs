import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConnectPage } from "../pages/ConnectPage";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    connect: vi.fn(async () => ({ authenticated: true, csrf_token: "next-csrf" })),
  };
});

import { connect } from "../api/client";

describe("ConnectPage token handling", () => {
  it("uses a password field and clears the token after connect", async () => {
    const user = userEvent.setup();
    const onConnected = vi.fn(async () => undefined);
    const secret = "paperless-secret-must-not-linger";

    render(
      <ConnectPage
        session={{ authenticated: false, csrf_token: "csrf" }}
        onConnected={onConnected}
      />,
    );

    const input = screen.getByLabelText(/Paperless token/i);
    expect(input).toHaveAttribute("type", "password");
    await user.type(input, secret);
    await user.click(screen.getByRole("button", { name: /^Connect$/i }));

    expect(connect).toHaveBeenCalledWith(secret, "csrf");
    expect(onConnected).toHaveBeenCalled();
    expect(input).toHaveValue("");
    expect(screen.queryByDisplayValue(secret)).toBeNull();
    expect(document.body.textContent).not.toContain(secret);
  });
});
