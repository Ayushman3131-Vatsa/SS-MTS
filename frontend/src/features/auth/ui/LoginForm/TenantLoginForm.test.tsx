import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { TenantLoginForm } from "./TenantLoginForm";

const renderForm = (onSubmit = vi.fn().mockResolvedValue(undefined)) => {
  render(
    <MemoryRouter
      future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
    >
      <TenantLoginForm onSubmit={onSubmit} />
    </MemoryRouter>,
  );
  return onSubmit;
};

describe("TenantLoginForm", () => {
  it("renders email/password fields and no registration or role selector", () => {
    renderForm();

    expect(screen.queryByLabelText("Workspace")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Work email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.queryByText(/create account/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/forgot password/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/role/i)).not.toBeInTheDocument();
  });

  it("announces validation errors and does not submit invalid values", async () => {
    const user = userEvent.setup();
    const onSubmit = renderForm();

    await user.click(
      screen.getByRole("button", { name: "Sign in" }),
    );

    expect(screen.getByText(/enter your work email/i)).toBeVisible();
    expect(screen.getByText(/enter your password/i)).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("toggles password visibility accessibly", async () => {
    const user = userEvent.setup();
    renderForm();
    const password = screen.getByLabelText("Password");

    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    expect(
      screen.getByRole("button", { name: "Hide password" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("normalizes email but preserves the password", async () => {
    const user = userEvent.setup();
    const onSubmit = renderForm();

    await user.type(screen.getByLabelText("Work email"), "Avery@Example.COM");
    await user.type(screen.getByLabelText("Password"), " keep spaces ");
    await user.click(
      screen.getByRole("button", { name: "Sign in" }),
    );

    expect(onSubmit).toHaveBeenCalledWith(
      {
        email: "Avery@Example.COM",
        password: " keep spaces ",
      },
      expect.anything(),
    );
  });
});
