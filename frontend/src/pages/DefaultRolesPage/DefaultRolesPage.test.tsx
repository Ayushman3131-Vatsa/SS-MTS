import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { DefaultRolesPage } from "./DefaultRolesPage";

const RolesTarget = () => {
  const location = useLocation();
  return <p>{location.pathname + location.search}</p>;
};

describe("DefaultRolesPage", () => {
  it("redirects workspace templates into Roles & Permissions", () => {
    render(
      <MemoryRouter initialEntries={["/platform/default-roles"]}>
        <Routes>
          <Route path="/platform/default-roles" element={<DefaultRolesPage />} />
          <Route path="/platform/roles" element={<RolesTarget />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("/platform/roles?type=tenant")).toBeVisible();
  });

  it("keeps an offering filter when redirecting", () => {
    render(
      <MemoryRouter initialEntries={["/platform/default-roles?offering_id=11111111-1111-4111-8111-111111111111"]}>
        <Routes>
          <Route path="/platform/default-roles" element={<DefaultRolesPage />} />
          <Route path="/platform/roles" element={<RolesTarget />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("/platform/roles?offering_id=11111111-1111-4111-8111-111111111111&type=tenant")).toBeVisible();
  });
});
