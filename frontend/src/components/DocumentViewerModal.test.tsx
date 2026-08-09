import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DocumentViewerModal } from "./DocumentViewerModal";

describe("DocumentViewerModal", () => {
  it("shows loading then ready iframe for PDF preview", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => "application/pdf" },
      }),
    );
    const onClose = vi.fn();
    render(
      <DocumentViewerModal paperlessDocumentId={184} title="Payslip" onClose={onClose} />,
    );
    expect(screen.getByText(/Loading preview/i)).toBeInTheDocument();
    expect(await screen.findByTitle(/Preview of Payslip/i)).toHaveAttribute(
      "src",
      "/ui/api/documents/184/preview",
    );
    await userEvent.click(screen.getByRole("button", { name: /^Close$/i }));
    expect(onClose).toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("shows an error state when preview fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        headers: { get: () => "application/json" },
      }),
    );
    render(
      <DocumentViewerModal paperlessDocumentId={999} title="Missing" onClose={() => undefined} />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/Preview is unavailable/i);
    vi.unstubAllGlobals();
  });
});
