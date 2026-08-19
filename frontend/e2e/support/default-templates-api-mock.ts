import type { Page, Request } from "@playwright/test";

import type { ApiCall } from "./session-api-mock";

const JSON_HEADERS = {
  "Cache-Control": "private, no-store",
  "Content-Type": "application/json",
};

const CORE_HR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const TASK_MANAGEMENT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const WELCOME_TEMPLATE_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const TASK_TEMPLATE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
export const CREATED_TEMPLATE_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";

export const DEFAULT_TEMPLATE_E2E_IDS = {
  coreHrOffering: CORE_HR_ID,
  taskManagementOffering: TASK_MANAGEMENT_ID,
  welcomeTemplate: WELCOME_TEMPLATE_ID,
  taskTemplate: TASK_TEMPLATE_ID,
} as const;

type TemplateType = "EMAIL" | "LETTER" | "NOTIFICATION" | "OTHER";

interface Placeholder {
  key: string;
  label: string;
  sample_value: string;
  required: boolean;
}

interface TemplateDetail {
  template_id: string;
  offering_id: string;
  offering_code: string;
  offering_name: string;
  category_id: string;
  category_code: string;
  category_name: string;
  code: string;
  name: string;
  description: string;
  type: TemplateType;
  subject: string | null;
  body: string;
  placeholders: Placeholder[];
  sort_order: number;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  inheriting_tenant_count: number;
  customized_tenant_count: number;
}

interface CreatePayload {
  offering_id: string;
  code: string;
  name: string;
  description: string;
  type: TemplateType;
  subject: string | null;
  body: string;
  placeholders: Placeholder[];
  sort_order: number;
}

interface PreviewPayload {
  subject: string | null;
  body: string;
  placeholders: Placeholder[];
  sample_data: Record<string, string>;
}

const offerings = [
  {
    offering_id: CORE_HR_ID,
    code: "COREHR",
    display_name: "Core HR",
    description: "People operations and employee lifecycle workflows.",
    icon_key: "users",
    route_slug: "core-hr",
    sort_order: 10,
    status: "ACTIVE",
    tenant_entitlement_count: 14,
    configuration_category_count: 2,
  },
  {
    offering_id: TASK_MANAGEMENT_ID,
    code: "TASKMGMT",
    display_name: "Task Management",
    description: "Assignments, reminders, and project delivery.",
    icon_key: "list-checks",
    route_slug: "task-management",
    sort_order: 20,
    status: "INACTIVE",
    tenant_entitlement_count: 4,
    configuration_category_count: 1,
  },
] as const;

const initialTemplates = (): TemplateDetail[] => [
  {
    template_id: WELCOME_TEMPLATE_ID,
    offering_id: CORE_HR_ID,
    offering_code: "COREHR",
    offering_name: "Core HR",
    category_id: "11111111-aaaa-4aaa-8aaa-111111111111",
    category_code: "corehr_email_templates",
    category_name: "Email Templates",
    code: "corehr_employee_welcome",
    name: "Employee welcome",
    description: "Welcomes a new employee to their organization.",
    type: "EMAIL",
    subject: "Welcome, {{employee_name}}",
    body: "Hello {{employee_name}}, welcome to the team.",
    placeholders: [
      {
        key: "employee_name",
        label: "Employee name",
        sample_value: "Ada Lovelace",
        required: true,
      },
    ],
    sort_order: 10,
    is_active: true,
    version: 3,
    created_at: "2026-07-20T09:00:00Z",
    updated_at: "2026-08-05T12:00:00Z",
    inheriting_tenant_count: 11,
    customized_tenant_count: 3,
  },
  {
    template_id: TASK_TEMPLATE_ID,
    offering_id: TASK_MANAGEMENT_ID,
    offering_code: "TASKMGMT",
    offering_name: "Task Management",
    category_id: "22222222-bbbb-4bbb-8bbb-222222222222",
    category_code: "taskmgmt_notification_templates",
    category_name: "Notification Templates",
    code: "taskmgmt_assignment_due",
    name: "Assignment due",
    description: "Notifies an assignee that work is due soon.",
    type: "NOTIFICATION",
    subject: null,
    body: "{{task_name}} is due soon.",
    placeholders: [
      {
        key: "task_name",
        label: "Task name",
        sample_value: "Prepare launch notes",
        required: true,
      },
    ],
    sort_order: 20,
    is_active: true,
    version: 1,
    created_at: "2026-08-01T09:00:00Z",
    updated_at: "2026-08-01T09:00:00Z",
    inheriting_tenant_count: 4,
    customized_tenant_count: 0,
  },
];

const withoutEditorFields = (template: TemplateDetail) => {
  const summary: Partial<TemplateDetail> = { ...template };
  delete summary.body;
  delete summary.placeholders;
  return summary;
};

const requestPayload = (pageRequest: Request) => {
  const postData = pageRequest.postData();
  return postData ? pageRequest.postDataJSON() : null;
};

const render = (value: string, payload: PreviewPayload) => value.replace(
  /\{\{([a-z][a-z0-9_]*)\}\}/g,
  (_token, key: string) => payload.sample_data[key]
    ?? payload.placeholders.find((placeholder) => placeholder.key === key)?.sample_value
    ?? "",
);

export const installDefaultTemplatesApiMock = async (page: Page) => {
  const calls: ApiCall[] = [];
  const templates = initialTemplates();

  await page.route(/\/api\/offerings(?:\?.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload: null,
      search: url.search,
    });
    await route.fulfill({ status: 200, headers: JSON_HEADERS, json: offerings });
  });

  await page.route(/\/api\/platform\/default-templates\/preview$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const payload = requestPayload(request) as PreviewPayload;
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload,
    });
    await route.fulfill({
      status: 200,
      headers: JSON_HEADERS,
      json: {
        subject: payload.subject === null ? null : render(payload.subject, payload),
        rendered_body: render(payload.body, payload),
      },
    });
  });

  await page.route(/\/api\/platform\/default-templates\/[0-9a-f-]+$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const templateId = url.pathname.split("/").at(-1);
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload: requestPayload(request),
    });
    const template = templates.find((item) => item.template_id === templateId);
    await route.fulfill(template
      ? { status: 200, headers: JSON_HEADERS, json: template }
      : { status: 404, headers: JSON_HEADERS, json: { detail: "Template not found" } });
  });

  await page.route(/\/api\/platform\/default-templates(?:\?.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const payload = requestPayload(request);
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload,
      search: url.search,
    });

    if (request.method() === "GET") {
      const offeringId = url.searchParams.get("offering_id");
      await route.fulfill({
        status: 200,
        headers: JSON_HEADERS,
        json: templates.filter((template) => template.offering_id === offeringId).map(withoutEditorFields),
      });
      return;
    }

    if (request.method() === "POST") {
      const createPayload = payload as CreatePayload;
      const offering = offerings.find((item) => item.offering_id === createPayload.offering_id);
      const categoryNames: Record<TemplateType, string> = {
        EMAIL: "Email Templates",
        LETTER: "Letter Templates",
        NOTIFICATION: "Notification Templates",
        OTHER: "Other Templates",
      };
      const created: TemplateDetail = {
        ...createPayload,
        template_id: CREATED_TEMPLATE_ID,
        offering_code: offering?.code ?? "UNKNOWN",
        offering_name: offering?.display_name ?? "Unknown offering",
        category_id: "33333333-eeee-4eee-8eee-333333333333",
        category_code: `${(offering?.code ?? "unknown").toLowerCase()}_${createPayload.type.toLowerCase()}_templates`,
        category_name: categoryNames[createPayload.type],
        is_active: true,
        version: 1,
        created_at: "2026-08-06T14:00:00Z",
        updated_at: "2026-08-06T14:00:00Z",
        inheriting_tenant_count: 14,
        customized_tenant_count: 0,
      };
      templates.push(created);
      await route.fulfill({ status: 201, headers: JSON_HEADERS, json: created });
      return;
    }

    await route.fulfill({
      status: 405,
      headers: JSON_HEADERS,
      json: { detail: "Method not allowed" },
    });
  });

  return { calls, templates };
};
