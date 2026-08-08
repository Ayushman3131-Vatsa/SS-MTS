import { useEffect, useReducer } from "react";

/**
 * Returns a monotonically increasing key whenever the browser window regains
 * focus. Consumers can include the key in their data-loading effect's
 * dependency list to refresh server-backed state without adding a polling or
 * real-time dependency.
 */
export const useWindowFocusRefresh = (): number => {
  const [refreshKey, requestRefresh] = useReducer((value: number) => value + 1, 0);

  useEffect(() => {
    window.addEventListener("focus", requestRefresh);
    return () => window.removeEventListener("focus", requestRefresh);
  }, []);

  return refreshKey;
};
