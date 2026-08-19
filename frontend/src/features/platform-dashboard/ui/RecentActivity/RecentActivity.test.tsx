import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PlatformActivity } from "../../model/dashboard";
import { RecentActivity } from "./RecentActivity";

const activity = (
  eventType: string,
  sequence: number,
  metadata: Record<string, unknown> = {},
): PlatformActivity => ({
  activity_id: `11111111-1111-4111-8111-11111111111${sequence}`,
  event_type: eventType,
  occurred_at: `2026-08-05T12:0${sequence}:00Z`,
  tenant: {
    tenant_id: "22222222-2222-4222-8222-222222222222",
    tenant_name: "Northstar",
  },
  metadata,
});

describe("RecentActivity", () => {
  it("renders offering activity with product-specific copy", () => {
    render(
      <RecentActivity activity={[
        activity("OFFERING_GRANTED", 1, {
          offering: { display_name: "Payroll" },
        }),
      ]} />,
    );

    expect(screen.getByText("Payroll granted to Northstar")).toBeVisible();
    expect(screen.getByText("Time-bound workspace access was granted.")).toBeVisible();
  });

  it("renders a safe label for future valid event codes", () => {
    render(<RecentActivity activity={[activity("SECURITY_POLICY_UPDATED", 2)]} />);

    expect(screen.getByText("Northstar: Security Policy Updated")).toBeVisible();
    expect(screen.getByText("A platform event was recorded.")).toBeVisible();
  });
});
