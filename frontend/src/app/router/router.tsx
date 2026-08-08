import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

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
import { RouteLoader } from "../../shared/ui/RouteLoader/RouteLoader";
import { NotFoundRoute, RootRoute } from "./redirect-routes";
import { ProtectedRoute, PublicOnlyRoute } from "./route-guards";

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
