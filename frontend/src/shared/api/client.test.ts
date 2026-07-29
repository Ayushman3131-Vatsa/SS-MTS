import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "./client";
import { SESSION_EXPIRED_EVENT } from "./session-events";

const jsonResponse = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("apiRequest", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = "mt_csrf=; Max-Age=0; Path=/";
  });

  it("always includes browser credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/health");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
  });

  it("adds the CSRF header to unsafe requests but not safe requests", async () => {
    document.cookie = "mt_csrf=secure-token; Path=/";
    const fetchMock = vi
      .fn()
      .mockImplementation(() => Promise.resolve(jsonResponse({ ok: true })));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/resource", { method: "POST", body: { value: 1 } });
    await apiRequest("/resource");

    const postHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
    const getHeaders = fetchMock.mock.calls[1]?.[1]?.headers as Headers;
    expect(postHeaders.get("X-CSRF-Token")).toBe("secure-token");
    expect(getHeaders.has("X-CSRF-Token")).toBe(false);
  });

  it("announces a protected-request 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { detail: "Invalid or expired session" },
          { status: 401 },
        ),
      ),
    );
    const listener = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, listener);

    await expect(apiRequest("/protected")).rejects.toMatchObject({
      status: 401,
    });
    expect(listener).toHaveBeenCalledOnce();

    window.removeEventListener(SESSION_EXPIRED_EVENT, listener);
  });

  it("can suppress expiry announcements for an invalid login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "Invalid credentials" }, { status: 401 }),
      ),
    );
    const listener = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, listener);

    await expect(
      apiRequest("/auth/session/tenant", {
        method: "POST",
        body: {},
        notifyOnUnauthorized: false,
      }),
    ).rejects.toMatchObject({ status: 401 });
    expect(listener).not.toHaveBeenCalled();

    window.removeEventListener(SESSION_EXPIRED_EVENT, listener);
  });

  it("returns useful field messages from validation responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: [
              {
                type: "value_error",
                loc: ["body", "tenant_admin_password"],
                msg: "Value error, Password must include a special character.",
              },
            ],
          },
          { status: 422, statusText: "Unprocessable Entity" },
        ),
      ),
    );

    await expect(apiRequest("/tenants", { method: "POST" })).rejects.toMatchObject({
      message:
        "Tenant admin password: Password must include a special character.",
      status: 422,
    });
  });
});
