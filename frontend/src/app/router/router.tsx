import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";

import { ForbiddenPage } from "../../pages/ForbiddenPage/ForbiddenPage";
import { AllTenantsPage } from "../../pages/AllTenantsPage/AllTenantsPage";
import { LoginPage } from "../../pages/LoginPage/LoginPage";
import { OfferingsPage } from "../../pages/OfferingsPage/OfferingsPage";
import { PlatformLoginPage } from "../../pages/PlatformLoginPage/PlatformLoginPage";
import { PlatformShell } from "../../pages/PlatformShell/PlatformShell";
import { TenantDetailPage } from "../../pages/TenantDetailPage/TenantDetailPage";
import { TenantLandingPage } from "../../pages/TenantLandingPage/TenantLandingPage";
import { TenantModuleComingSoonPage } from "../../pages/TenantModuleComingSoonPage/TenantModuleComingSoonPage";
import { TenantRegistrationPage } from "../../pages/TenantRegistrationPage/TenantRegistrationPage";
import { TenantShell } from "../../pages/TenantShell/TenantShell";
import { SuspendedTenantPage } from "../../pages/SuspendedTenantPage/SuspendedTenantPage";
import { ForcedPasswordChangePage } from "../../pages/ForcedPasswordChangePage/ForcedPasswordChangePage";
import { RouteLoader } from "../../shared/ui/RouteLoader/RouteLoader";
import { NotFoundRoute, RootRoute } from "./redirect-routes";
import { OfferingRoute, ProtectedRoute, PublicOnlyRoute } from "./route-guards";

const PlatformDashboardPage = lazy(async () => {
  const page = await import(
    "../../pages/PlatformDashboardPage/PlatformDashboardPage"
  );
  return { default: page.PlatformDashboardPage };
});

const ConfigurationsPage = lazy(async () => {
  const page = await import(
    "../../pages/ConfigurationsPage/ConfigurationsPage"
  );
  return { default: page.ConfigurationsPage };
});

const ConfigTemplateEditorPage = lazy(async () => {
  const page = await import(
    "../../pages/ConfigTemplateEditorPage/ConfigTemplateEditorPage"
  );
  return { default: page.ConfigTemplateEditorPage };
});

const DefaultTemplatesPage = lazy(async () => {
  const page = await import(
    "../../pages/DefaultTemplatesPage/DefaultTemplatesPage"
  );
  return { default: page.DefaultTemplatesPage };
});

const DefaultTemplateEditorPage = lazy(async () => {
  const page = await import(
    "../../pages/DefaultTemplateEditorPage/DefaultTemplateEditorPage"
  );
  return { default: page.DefaultTemplateEditorPage };
});

const TaskManagementLayout = lazy(async () => {
  const page = await import("../../features/task-management/ui/TaskManagementLayout/TaskManagementLayout");
  return { default: page.TaskManagementLayout };
});

const TaskManagementOverviewPage = lazy(async () => {
  const page = await import("../../pages/TaskManagementOverviewPage/TaskManagementOverviewPage");
  return { default: page.TaskManagementOverviewPage };
});

const TaskProjectsPage = lazy(async () => {
  const page = await import("../../pages/TaskProjectsPage/TaskProjectsPage");
  return { default: page.TaskProjectsPage };
});

const TaskProjectPage = lazy(async () => {
  const page = await import("../../pages/TaskProjectPage/TaskProjectPage");
  return { default: page.TaskProjectPage };
});

const TaskListPage = lazy(async () => {
  const page = await import("../../pages/TaskListPage/TaskListPage");
  return { default: page.TaskListPage };
});

const taskRoute = (element: ReactNode) => (
  <Suspense fallback={<RouteLoader label="Loading Task Management…" />}>{element}</Suspense>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootRoute />,
  },
  {
    element: <PublicOnlyRoute />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/login/platform", element: <PlatformLoginPage /> },
    ],
  },
  {
    element: <ProtectedRoute area="platform" />,
    children: [
      {
        path: "/platform",
        element: <PlatformShell />,
        children: [
          {
            index: true,
            element: (
              <Suspense
                fallback={<RouteLoader label="Loading platform dashboard…" />}
              >
                <PlatformDashboardPage />
              </Suspense>
            ),
          },
          {
            path: "tenants",
            element: <AllTenantsPage />,
          },
          {
            path: "tenants/register",
            element: <TenantRegistrationPage />,
          },
          {
            path: "offerings",
            element: <OfferingsPage />,
          },
          {
            path: "default-templates",
            element: (
              <Suspense fallback={<RouteLoader label="Loading default templates&hellip;" />}>
                <DefaultTemplatesPage />
              </Suspense>
            ),
          },
          {
            path: "default-templates/new",
            element: (
              <Suspense fallback={<RouteLoader label="Loading template editor&hellip;" />}>
                <DefaultTemplateEditorPage />
              </Suspense>
            ),
          },
          {
            path: "default-templates/:templateId",
            element: (
              <Suspense fallback={<RouteLoader label="Loading template editor&hellip;" />}>
                <DefaultTemplateEditorPage />
              </Suspense>
            ),
          },
          {
            path: "tenants/:tenantId",
            element: <TenantDetailPage />,
          },
        ],
      },
    ],
  },
  {
    element: (
      <ProtectedRoute
        area="tenant"
        allowSuspendedTenant
        allowPasswordChangeRequired
      />
    ),
    children: [
      {
        path: "/account/change-password",
        element: <ForcedPasswordChangePage />,
      },
    ],
  },
  {
    element: <ProtectedRoute area="tenant" allowSuspendedTenant />,
    children: [
      {
        path: "/app/suspended",
        element: <SuspendedTenantPage />,
      },
    ],
  },
  {
    element: <ProtectedRoute area="tenant" />,
    children: [
      {
        path: "/app",
        element: <TenantShell />,
        children: [
          {
            element: (
              <ProtectedRoute roles={["Tenant Admin", "Project Manager"]} />
            ),
            children: [
              {
                path: "overview",
                element: <TenantLandingPage variant="overview" />,
              },
            ],
          },
          {
            element: <ProtectedRoute roles={["Tenant Admin"]} />,
            children: [
              {
                path: "configurations",
                element: (
                  <Suspense fallback={<RouteLoader label="Loading configurations…" />}>
                    <ConfigurationsPage />
                  </Suspense>
                ),
              },
              {
                path: "configurations/templates/:templateId",
                element: (
                  <Suspense fallback={<RouteLoader label="Loading template editor…" />}>
                    <ConfigTemplateEditorPage />
                  </Suspense>
                ),
              },
            ],
          },
          {
            element: <ProtectedRoute roles={["Employee"]} />,
            children: [
              {
                path: "my-work",
                element: <TenantLandingPage variant="my-work" />,
              },
            ],
          },
          {
            element: <OfferingRoute code="TASK_MANAGEMENT" />,
            children: [
              { path: "modules/task-management", element: <Navigate to="/app/task-management" replace /> },
              {
                path: "task-management",
                element: taskRoute(<TaskManagementLayout />),
                children: [
                  { index: true, element: taskRoute(<TaskManagementOverviewPage />) },
                  { path: "projects", element: taskRoute(<TaskProjectsPage />) },
                  { path: "projects/:projectId/board", element: taskRoute(<TaskProjectPage view="board" />) },
                  { path: "projects/:projectId/list", element: taskRoute(<TaskProjectPage view="list" />) },
                  { path: "projects/:projectId/members", element: taskRoute(<TaskProjectPage view="members" />) },
                  { path: "projects/:projectId/settings", element: taskRoute(<TaskProjectPage view="settings" />) },
                  { path: "my-work", element: taskRoute(<TaskListPage mode="mine" />) },
                  { path: "tasks", element: taskRoute(<TaskListPage mode="all" />) },
                ],
              },
            ],
          },
          {
            path: "modules/:moduleSlug",
            element: <TenantModuleComingSoonPage />,
          },
        ],
      },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [{ path: "/forbidden", element: <ForbiddenPage /> }],
  },
  {
    path: "*",
    element: <NotFoundRoute />,
  },
]);
