import { afterEach, describe, expect, it, vi } from "vitest";

import { taskManagementApi } from "./task-management-api";

const page = { items: [], page: 2, page_size: 25, total: 0 };

describe("taskManagementApi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses only the canonical project endpoint and encodes filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await taskManagementApi.projects({ page: 2, page_size: 25, query: "pay roll", include_archived: true, sort: "project_key" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/task-management/projects?page=2&page_size=25&query=pay+roll&include_archived=true&sort=project_key");
  });

  it("rejects a malformed response instead of rendering an empty state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } })));
    await expect(taskManagementApi.tasks()).rejects.toMatchObject({ name: "InvalidApiResponseError" });
  });

  it("posts uploads as FormData without forcing a JSON content type", async () => {
    const attachment = { attachment_id: "11111111-1111-4111-8111-111111111111", task_id: "22222222-2222-4222-8222-222222222222", original_filename: "brief.pdf", media_type: "application/pdf", size_bytes: 4, uploaded_by_user_id: "33333333-3333-4333-8333-333333333333", created_at: "2026-08-11T12:00:00Z" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(attachment), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await taskManagementApi.uploadAttachment(attachment.task_id, new File(["test"], "brief.pdf", { type: "application/pdf" }));
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.headers as Headers).has("Content-Type")).toBe(false);
  });
});

