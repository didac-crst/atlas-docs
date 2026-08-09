import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConnectPage } from "../pages/ConnectPage";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    login: vi.fn(async () => ({ authenticated: true, csrf_token: "next-csrf" })),
    connect: vi.fn(async () => ({ authenticated: true, csrf_token: "next-csrf" })),
  };
});

import { connect, login } from "../api/client";

describe("ConnectPage", () => {
  it("presents AtlasDocs identity rather than a Paperless login title", () => {
    render(
      <ConnectPage
        session={{ authenticated: false, csrf_token: "csrf" }}
        onConnected={async () => undefined}
      />,
    );
    expect(screen.getByRole("heading", { name: /^AtlasDocs$/i })).toBeInTheDocument();
    expect(screen.getByText(/Where evidence becomes knowledge/i)).toBeInTheDocument();
    expect(screen.getByText(/Secure authentication powered by Paperless/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Connect to Paperless/i })).toBeNull();
  });

  it("submits username/password login and clears the password", async () => {
    const user = userEvent.setup();
    const onConnected = vi.fn(async () => undefined);
    const secret = "paperless-password-must-not-linger";

    render(
      <ConnectPage
        session={{ authenticated: false, csrf_token: "csrf" }}
        onConnected={onConnected}
      />,
    );

    await user.type(screen.getByLabelText(/^Username$/i), "ada");
    const password = screen.getByLabelText(/^Password$/i);
    expect(password).toHaveAttribute("type", "password");
    await user.clear(password);
    await user.type(password, secret);
    await user.click(screen.getByRole("button", { name: /^Sign in$/i }));

    expect(login).toHaveBeenCalledWith("ada", secret, "csrf");
    expect(onConnected).toHaveBeenCalled();
    expect(password).toHaveValue("");
    expect(screen.queryByDisplayValue(secret)).toBeNull();
    expect(document.body.textContent).not.toContain(secret);
  }, 15000);

  it("uses advanced token paste via connect()", async () => {
    const user = userEvent.setup();
    const onConnected = vi.fn(async () => undefined);
    const secret = "paperless-secret-must-not-linger";

    render(
      <ConnectPage
        session={{ authenticated: false, csrf_token: "csrf" }}
        onConnected={onConnected}
      />,
    );

    await user.click(screen.getByText(/Advanced: paste API token/i));
    const input = screen.getByLabelText(/API token/i);
    expect(input).toHaveAttribute("type", "password");
    await user.clear(input);
    await user.type(input, secret);
    await user.click(screen.getByRole("button", { name: /Connect with token/i }));

    expect(connect).toHaveBeenCalledWith(secret, "csrf");
    expect(onConnected).toHaveBeenCalled();
    expect(input).toHaveValue("");
    expect(screen.queryByDisplayValue(secret)).toBeNull();
    expect(document.body.textContent).not.toContain(secret);
  }, 15000);
});
