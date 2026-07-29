const REMEMBERED_WORKSPACE_KEY = "workspace.remembered-slug";
const VALID_WORKSPACE_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export const getRememberedWorkspace = (): string => {
  try {
    const value = window.localStorage.getItem(REMEMBERED_WORKSPACE_KEY) || "";
    return value.length >= 3 &&
      value.length <= 63 &&
      VALID_WORKSPACE_SLUG.test(value)
      ? value
      : "";
  } catch {
    return "";
  }
};

export const setRememberedWorkspace = (
  workspaceSlug: string | null,
): void => {
  try {
    if (workspaceSlug) {
      window.localStorage.setItem(REMEMBERED_WORKSPACE_KEY, workspaceSlug);
    } else {
      window.localStorage.removeItem(REMEMBERED_WORKSPACE_KEY);
    }
  } catch {
    // Storage can be unavailable in private modes; sign-in must still work.
  }
};
