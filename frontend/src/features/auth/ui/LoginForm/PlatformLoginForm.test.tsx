import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { PlatformLoginForm } from "./PlatformLoginForm";

describe("PlatformLoginForm", () => {
  it("shows the restricted operator message and no registration", () => {
    render(
      <MemoryRouter
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <PlatformLoginForm onSubmit={vi.fn().mockResolvedValue(undefined)} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/authorized operators only/i)).toBeVisible();
    expect(screen.getByLabelText("Administrator email")).toBeVisible();
    expect(screen.queryByText(/create account/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to organization sign in/i }),
    ).toHaveAttribute("href", "/login");
  });
});
