import { afterEach, describe, expect, it, vi } from "vitest";

import { InvalidApiResponseError } from "../../../shared/api/errors";
import { defaultTemplatesApi } from "./default-templates-api";

const offeringId = "11111111-1111-4111-8111-111111111111";
const categoryId = "22222222-2222-4222-8222-222222222222";
const templateId = "33333333-3333-4333-8333-333333333333";

const listItem = {
  template_id: templateId,
  offering_id: offeringId,
  offering_code: "CORE_HR",
  offering_name: "Core HR",
  category_id: categoryId,
  category_code: "corehr_email_templates",
  category_name: "Email Templates",
  code: "core_hr_welcome_email",
  name: "Welcome Email",
  description: "Sent to new employees.",
  type: "EMAIL",
  subject: "Welcome, {{employee_name}}",
  sort_order: 10,
  is_active: true,
  version: 3,
  created_at: "2026-08-06T00:00:00Z",
  updated_at: "2026-08-06T01:00:00Z",
  inheriting_tenant_count: 12,
  customized_tenant_count: 2,
};

const placeholder = {
  key: "employee_name",
  label: "Employee name",
  sample_value: "Ada Lovelace",
  required: true,
};

const detail = {
  ...listItem,
  body: "Hello {{employee_name}}",
  placeholders: [placeholder],
};

const response = (body: unknown) => new Response(JSON.stringify(body), {
  status: 200,
  headers: { "Content-Type": "application/json" },
});

describe("defaultTemplatesApi", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requests an offering-filtered catalog and validates the snake_case response", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response([listItem]));

    const result = await defaultTemplatesApi.list({ offeringId });

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(`/api/platform/default-templates?offering_id=${offeringId}`);
    expect(result[0]).toMatchObject({
      template_id: templateId,
      offering_name: "Core HR",
      category_name: "Email Templates",
      version: 3,
    });
  });

  it("rejects a malformed platform template response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response([{ ...listItem, version: 0 }]));

    await expect(defaultTemplatesApi.list({ offeringId })).rejects.toBeInstanceOf(InvalidApiResponseError);
  });

  it("sends the publish-on-create contract without client-owned status or category fields", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(detail));

    await defaultTemplatesApi.create({
      offering_id: offeringId,
      code: "core_hr_welcome_email",
      name: "Welcome Email",
      description: "Sent to new employees.",
      type: "EMAIL",
      subject: "Welcome, {{employee_name}}",
      body: "Hello {{employee_name}}",
      placeholders: [placeholder],
      sort_order: 10,
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    const payload = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(url).toBe("/api/platform/default-templates");
    expect(init?.method).toBe("POST");
    expect(payload).toMatchObject({ offering_id: offeringId, type: "EMAIL" });
    expect(payload).not.toHaveProperty("category_id");
    expect(payload).not.toHaveProperty("is_active");
  });

  it("uses expected_version for updates and includes the unsaved draft in previews", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response({ ...detail, version: 4, name: "Welcome Note" }))
      .mockResolvedValueOnce(response({ subject: "Welcome, Ada", rendered_body: "Hello Ada" }));

    await defaultTemplatesApi.update(templateId, {
      expected_version: 3,
      name: "Welcome Note",
    });
    await defaultTemplatesApi.preview({
      subject: "Welcome, {{employee_name}}",
      body: "Hello {{employee_name}}",
      placeholders: [placeholder],
      sample_data: { employee_name: "Ada" },
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      expected_version: 3,
      name: "Welcome Note",
    });
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("PATCH");
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe("/api/platform/default-templates/preview");
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toMatchObject({
      body: "Hello {{employee_name}}",
      placeholders: [placeholder],
      sample_data: { employee_name: "Ada" },
    });
  });
});
