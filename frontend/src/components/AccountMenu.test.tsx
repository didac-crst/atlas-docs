import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AccountMenu } from "./AccountMenu";

describe("AccountMenu", () => {
  it("exposes Reconcile and Disconnect outside primary product labels until opened", async () => {
    const user = userEvent.setup();
    const onDisconnect = vi.fn();

    render(
      <MemoryRouter>
        <AccountMenu usernameLabel="ada" onDisconnect={onDisconnect} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: /^ada$/i })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: /Reconcile/i })).toBeNull();

    await user.click(screen.getByRole("button", { name: /^ada$/i }));
    expect(screen.getByRole("menuitem", { name: /Reconcile/i })).toHaveAttribute(
      "href",
      "/reconcile",
    );

    await user.click(screen.getByRole("menuitem", { name: /Disconnect/i }));
    expect(onDisconnect).toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <AccountMenu onDisconnect={() => undefined} />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /^Account$/i }));
    expect(screen.getByRole("menu", { name: /Account/i })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu", { name: /Account/i })).toBeNull();
  });
});
