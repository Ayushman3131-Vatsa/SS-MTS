import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

import { ForbiddenPage } from "../../pages/ForbiddenPage/ForbiddenPage";
import { AllTenantsPage } from "../../pages/AllTenantsPage/AllTenantsPage";
import { LoginPage } from "../../pages/LoginPage/LoginPage";
import { PlatformLoginPage } from "../../pages/PlatformLoginPage/PlatformLoginPage";
import { PlatformShell } from "../../pages/PlatformShell/PlatformShell";
import { TenantDetailPage } from "../../pages/TenantDetailPage/TenantDetailPage";
import { TenantLandingPage } from "../../pages/TenantLandingPage/TenantLandingPage";
import { TenantModuleComingSoonPage } from "../../pages/TenantModuleComingSoonPage/TenantModuleComingSoonPage";
import { TenantRegistrationPage } from "../../pages/TenantRegistrationPage/TenantRegistrationPage";
import { TenantShell } from "../../pages/TenantShell/TenantShell";
import { RouteLoader } from "../../shared/ui/RouteLoader/RouteLoader";
import { NotFoundRoute, RootRoute } from "./redirect-routes";
import { ProtectedRoute, PublicOnlyRoute } from "./route-guards";

const PlatformDashboardPage = lazy(async () => {
  const page = await import(
    "../../pages/PlatformDashboardPage/PlatformDashboardPage"
  );
  return { default: page.PlatformDashboardPage };
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
            path: "tenants/:tenantId",
            element: <TenantDetailPage />,
          },
        ],
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
