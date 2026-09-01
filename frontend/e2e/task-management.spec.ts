import { expect, test, type Page } from "@playwright/test";

import { installSessionApiMock, tenantPrincipal } from "./support/session-api-mock";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const ADMIN_ID = "22222222-2222-4222-8222-222222222222";
const MEMBER_ID = "33333333-3333-4333-8333-333333333333";
const PROJECT_ID = "44444444-4444-4444-8444-444444444444";
const MEMBERSHIP_ID = "55555555-5555-4555-8555-555555555555";
const TASK_ID = "66666666-6666-4666-8666-666666666666";

const effectivePrincipal = () => {
  const principal = tenantPrincipal("Tenant Admin");
  principal.tenant.offerings.push({
    offering_id: "77777777-7777-4777-8777-777777777777",
    code: "TASK_MANAGEMENT",
    display_name: "Task Management",
    description: "Plan and deliver work",
    icon_key: "clipboard-check",
    route_slug: "task-management",
    sort_order: 1,
  });
  return principal;
};

const project = {
  tenant_id: TENANT_ID, project_id: PROJECT_ID, project_key: "PAY", name: "Payments Platform", client_name: "Northstar", description: null,
  start_date: null, expected_end_date: null, status: "Not Started", priority: "Medium", pm_id: ADMIN_ID, dm_id: null, remarks: null,
  version: 1, created_at: "2026-08-11T10:00:00Z", updated_at: "2026-08-11T10:00:00Z", archived_at: null,
};
const task = {
  tenant_id: TENANT_ID, task_id: TASK_ID, project_id: PROJECT_ID, task_number: 1, display_key: "PAY-1", task_type: "TASK", parent_task_id: null,
  name: "Implement secure checkout", description: null, task_category: null, assignee_id: null, technical_lead_id: null, functional_lead_id: null,
  reporter_id: ADMIN_ID, created_by_user_id: ADMIN_ID, start_date: null, end_date: null, estimated_hours: 0, actual_hours: 0, priority: "Medium", status: "New",
  blocked_by_id: null, remarks: null, version: 1, created_at: "2026-08-11T10:10:00Z", updated_at: "2026-08-11T10:10:00Z", completed_at: null, archived_at: null,
};
const users = [
  { tenant_id: TENANT_ID, user_id: ADMIN_ID, name: "Taylor Admin", email: "admin@northstar.example", role: "Tenant Admin", status: "Active", version: 1, created_by_user_id: null, created_at: "2026-01-01T00:00:00Z" },
  { tenant_id: TENANT_ID, user_id: MEMBER_ID, name: "Morgan Manager", email: "manager@northstar.example", role: "Project Manager", status: "Active", version: 1, created_by_user_id: ADMIN_ID, created_at: "2026-01-01T00:00:00Z" },
];

const installTaskApi = async (page: Page) => {
  let hasProject = false;
  let hasTask = false;
  let hasMember = true;
  const calls: string[] = [];
  const emptyPage = (url: URL) => ({ items: [], page: Number(url.searchParams.get("page") ?? 1), page_size: Number(url.searchParams.get("page_size") ?? 25), total: 0 });
  await page.route(/\/api\/users(?:\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(users) }));
  await page.route(/\/api\/task-management(?:\/.*)?$/, async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname; const method = request.method(); calls.push(`${method} ${path}`);
    const json = async (value: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
    if (path === "/api/task-management/projects" && method === "GET") return json(hasProject ? { ...emptyPage(url), items: [project], total: 1 } : emptyPage(url));
    if (path === "/api/task-management/projects" && method === "POST") { hasProject = true; return json(project, 201); }
    if (path === `/api/task-management/projects/${PROJECT_ID}` && method === "GET") return json(project);
    if (path === `/api/task-management/projects/${PROJECT_ID}/members` && method === "GET") return json({ ...emptyPage(url), items: hasMember ? [{ membership_id: MEMBERSHIP_ID, tenant_id: TENANT_ID, project_id: PROJECT_ID, user_id: ADMIN_ID, role: "MANAGER", added_by_user_id: ADMIN_ID, created_at: "2026-08-11T10:00:00Z", updated_at: "2026-08-11T10:00:00Z" }] : [], total: hasMember ? 1 : 0 });
    if (path === `/api/task-management/projects/${PROJECT_ID}/members` && method === "POST") { hasMember = true; return json({ membership_id: "88888888-8888-4888-8888-888888888888", tenant_id: TENANT_ID, project_id: PROJECT_ID, user_id: MEMBER_ID, role: "MEMBER", added_by_user_id: ADMIN_ID, created_at: "2026-08-11T10:05:00Z", updated_at: "2026-08-11T10:05:00Z" }, 201); }
    if (path === `/api/task-management/projects/${PROJECT_ID}/tasks` && method === "POST") { hasTask = true; return json(task, 201); }
    if (path === "/api/task-management/tasks" && method === "GET") return json(hasTask ? { ...emptyPage(url), items: [task].filter((item) => !url.searchParams.get("status") || item.status === url.searchParams.get("status")), total: !url.searchParams.get("status") || task.status === url.searchParams.get("status") ? 1 : 0 } : emptyPage(url));
    if (path === `/api/task-management/tasks/${TASK_ID}` && method === "GET") return json(task);
    if (path === `/api/task-management/tasks/${TASK_ID}/comments` && method === "GET") return json(emptyPage(url));
    if (path === `/api/task-management/tasks/${TASK_ID}/comments` && method === "POST") return json({ comment_id: "99999999-9999-4999-8999-999999999999", task_id: TASK_ID, commented_by_user_id: ADMIN_ID, comment_text: "Ready for review", version: 1, created_at: "2026-08-11T10:20:00Z", updated_at: "2026-08-11T10:20:00Z", deleted_at: null }, 201);
    if (["time-entries", "attachments", "links", "activity"].some((segment) => path === `/api/task-management/tasks/${TASK_ID}/${segment}`) && method === "GET") return json(emptyPage(url));
    return json({ detail: `Unhandled mock route: ${method} ${path}` }, 404);
  });
  return { calls };
};

test.describe("Task Management workspace", () => {
  test("hides navigation and guards direct URLs without entitlement", async ({ page }) => {
    await installSessionApiMock(page, { initialPrincipal: tenantPrincipal("Tenant Admin") });
    await page.goto("/app/task-management");
    await expect(page).toHaveURL("/t/NORTHSTAR/app/overview");
    await expect(page.getByRole("button", { name: "Task Management" })).toHaveCount(0);
  });

  test("creates a project and task, manages membership, and collaborates", async ({ page }) => {
    await installSessionApiMock(page, { initialPrincipal: effectivePrincipal() });
    const api = await installTaskApi(page);
    await page.goto("/t/NORTHSTAR/app/task-management");
    await expect(page.getByRole("heading", { name: "Work overview" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Task Management" })).toHaveAttribute("aria-expanded", "true");
    await page.getByRole("link", { name: "Projects", exact: true }).click();
    await page.getByRole("button", { name: "New project" }).click();
    await page.getByRole("textbox", { name: "Project name" }).fill("Payments Platform");
    await page.getByRole("dialog", { name: "Create project" }).getByRole("button", { name: "Create project", exact: true }).click();
    await expect(page).toHaveURL(`/t/NORTHSTAR/app/task-management/projects/${PROJECT_ID}/board`);
    await expect(page.getByRole("heading", { name: "Payments Platform" })).toBeVisible({ timeout: 30_000 });

    await page.getByRole("link", { name: /Members/ }).click();
    await page.getByLabel("User").selectOption(MEMBER_ID);
    await page.getByLabel("Project role").selectOption("MEMBER");
    await page.getByRole("button", { name: "Add member" }).click();
    await expect.poll(() => api.calls.filter((call) => call === `POST /api/task-management/projects/${PROJECT_ID}/members`).length).toBe(1);

    await page.getByRole("button", { name: "Create task" }).click();
    await page.getByRole("textbox", { name: "Summary" }).fill("Implement secure checkout");
    await page.getByRole("dialog", { name: "Create task" }).getByRole("button", { name: "Create task", exact: true }).click();
    await expect(page.getByRole("dialog", { name: /PAY-1/ })).toBeVisible();
    await page.getByRole("button", { name: "Comments" }).click();
    await page.getByRole("textbox", { name: "Comment" }).fill("Ready for review");
    await page.getByRole("button", { name: "Comment", exact: true }).click();
    await expect.poll(() => api.calls.filter((call) => call === `POST /api/task-management/tasks/${TASK_ID}/comments`).length).toBe(1);
  });
});
