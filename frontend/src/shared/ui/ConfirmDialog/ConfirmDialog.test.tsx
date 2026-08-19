import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("requires a destructive-action reason before confirming", () => {
    const onConfirm = vi.fn();

    const TestDialog = () => {
      const [reason, setReason] = useState("");

      return (
        <ConfirmDialog
          open
          title="Deactivate offering?"
          description="This is permanent."
          confirmLabel="Deactivate"
          reason={reason}
          reasonRequired
          onReasonChange={setReason}
          onCancel={vi.fn()}
          onConfirm={onConfirm}
        />
      );
    };

    render(<TestDialog />);

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByText("A reason is required.")).toBeVisible();

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Contract ended" } });
    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("closes through the reusable cancel action", () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Suspend tenant?"
        description="Tenant access will be blocked."
        confirmLabel="Suspend"
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
