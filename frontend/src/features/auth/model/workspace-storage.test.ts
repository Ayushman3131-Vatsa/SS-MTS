import { describe, expect, it } from "vitest";

import {
  getRememberedWorkspace,
  setRememberedWorkspace,
} from "./workspace-storage";

describe("remembered workspace storage", () => {
  it("stores only the validated workspace slug", () => {
    setRememberedWorkspace("northstar-labs");

    expect(getRememberedWorkspace()).toBe("northstar-labs");
    expect(Object.keys(window.localStorage)).toEqual([
      "workspace.remembered-slug",
    ]);
  });

  it("removes the workspace when remembrance is disabled", () => {
    setRememberedWorkspace("northstar-labs");
    setRememberedWorkspace(null);

    expect(getRememberedWorkspace()).toBe("");
  });

  it("does not restore an invalid value", () => {
    window.localStorage.setItem("workspace.remembered-slug", "Other_Tenant");
    expect(getRememberedWorkspace()).toBe("");
  });
});
