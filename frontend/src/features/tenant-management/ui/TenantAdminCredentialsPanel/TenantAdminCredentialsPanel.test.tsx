import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TenantAdminCredentialsPanel } from "./TenantAdminCredentialsPanel";

describe("TenantAdminCredentialsPanel", () => {
  it("shows work email, username, and password without login url", () => {
    render(
      <TenantAdminCredentialsPanel
        access={{
          email: "admin@example.com",
          username: "tenant.admin",
          temporary_password: "TempPass1!",
          login_path: "/login/acme",
          password_change_required: true,
        }}
      />,
    );

    expect(screen.getByText("Work email")).toBeVisible();
    expect(screen.getByText("admin@example.com")).toBeVisible();
    expect(screen.getByText("tenant.admin")).toBeVisible();
    expect(screen.getByText("TempPass1!")).toBeVisible();
    expect(screen.queryByText("Login URL")).not.toBeInTheDocument();
    expect(screen.queryByText("/login/acme")).not.toBeInTheDocument();
    expect(screen.getByText(/Sign in with work email or username/i)).toBeVisible();
  });

  it("hides synthetic placeholder emails", () => {
    render(
      <TenantAdminCredentialsPanel
        access={{
          email: "tenant.admin@accounts.local",
          username: "tenant.admin",
          temporary_password: "TempPass1!",
          login_path: "/login/acme",
          password_change_required: true,
        }}
      />,
    );

    expect(screen.queryByText("Work email")).not.toBeInTheDocument();
    expect(screen.queryByText("tenant.admin@accounts.local")).not.toBeInTheDocument();
    expect(screen.getByText(/Sign in with username/i)).toBeVisible();
  });

  it("copies credential values", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(
      <TenantAdminCredentialsPanel
        access={{
          email: "admin@example.com",
          temporary_password: "TempPass1!",
          login_path: "/login/acme",
          password_change_required: true,
        }}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Copy" })[1]);
    expect(writeText).toHaveBeenCalledWith("TempPass1!");
  });
});
